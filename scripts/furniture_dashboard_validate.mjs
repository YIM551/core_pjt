// Real dashboard inputs and live model responses; no inference responses are mocked.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const {chromium} = require(path.join(process.env.CORE_NODE_MODULES || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'), 'playwright'));
const output = path.join(root, process.env.CORE_RESULT_DIR || 'results/furniture_dashboard_20261022');
await fs.mkdir(output, {recursive:true});
const dataset = path.join(root, 'datasets/roboflow/furniture/v2_curated_v2');
const manifest = JSON.parse(await fs.readFile(path.join(dataset, 'split_manifest.json'), 'utf8'));
const base = process.env.CORE_TEST_URL || 'http://127.0.0.1:8003';
const weights = 'source/2회차_day1/runs/furniture_spec1_20261022/weights/best.pt';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const report = {base_url:base, weights, weights_sha256:sha(await fs.readFile(path.join(root,weights))),
  selection:'First valid image per class in frozen manifest; no test images and no selection by prediction',
  cases:[], checks:[]};
const browser = await chromium.launch({channel:'msedge',headless:true});
try {
  report.health_before = await (await fetch(base+'/api/health')).json();
  assert.equal(report.health_before.yolo_model, 'best.pt');
  for (const [id,label,korean] of [[1,'Sofa','소파'],[0,'Chair','의자'],[2,'Table','테이블']]) {
    if(process.env.CORE_TEST_CLASS && label!==process.env.CORE_TEST_CLASS)continue;
    const selected = manifest.find(x=>x.derived_split==='valid' && x.class_id===id);
    assert.ok(selected);
    const bytes = await fs.readFile(path.join(dataset,selected.image));
    assert.equal(sha(bytes), selected.image_sha256);
    const entry = {label, sample:selected, exchanges:[], errors:[]};
    const ctx = await browser.newContext({viewport:{width:1440,height:1000}});
    const page = await ctx.newPage();
    page.setDefaultTimeout(240000);
    const captured = {};
    await page.exposeBinding('__recordFurnitureInput', async(_source,endpoint,values)=>{
      const body=Buffer.from(values), digest=sha(body);
      await fs.writeFile(path.join(output,`${label}-dashboard-input.jpg`), body);
      (captured[endpoint] ||= []).push(digest);
    });
    await page.addInitScript(()=>{
      const original=window.fetch.bind(window);
      window.fetch=async(resource,options)=>{
        const endpoint=new URL(typeof resource==='string'?resource:resource.url,location.href).pathname;
        if(options?.body instanceof Blob && ['/api/yolo-detect','/api/vlm-describe'].includes(endpoint))
          await window.__recordFurnitureInput(endpoint,Array.from(new Uint8Array(await options.body.arrayBuffer())));
        return original(resource,options);
      };
    });
    page.on('pageerror', e=>entry.errors.push(String(e)));
    const pending=[];
    page.on('response',r=>{
      const endpoint=new URL(r.url()).pathname;
      if(!['/api/yolo-detect','/api/vlm-describe','/api/llm-answer'].includes(endpoint))return;
      pending.push((async()=>{
        let request=null;
        if(endpoint==='/api/llm-answer')request=r.request().postDataJSON();
        entry.exchanges.push({endpoint,status:r.status(),input_sha256:captured[endpoint]?.shift(),request,response:await r.json()});
      })());
    });
    await page.goto(base);
    await page.waitForFunction(()=>typeof window.recognizeGesture==='function');
    await page.locator('#local-image-file').setInputFiles(path.join(dataset,selected.image));
    await page.waitForFunction(()=>!!document.querySelector('#subtab-local-pc')._inputImage);
    const prompt='어떤 가구가 몇 개 보여? YOLO 개수와 VLM 장면 설명을 참고해서 한국어로 알려줘.';
    const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/llm-answer');
    const started=Date.now();
    await page.locator('#subtab-local-pc .prompt-input').fill(prompt);
    await page.locator('#subtab-local-pc .prompt-send-btn').click();
    await response;
    await page.waitForFunction(()=>!document.querySelector('#subtab-local-pc .prompt-send-btn').disabled);
    await Promise.all(pending);
    entry.seconds=(Date.now()-started)/1000;
    entry.yolo_display=await page.locator('#subtab-local-pc .yolo-result').innerText();
    entry.vlm_display=await page.locator('#subtab-local-pc .vlm-result').innerText();
    await page.screenshot({path:path.join(output,`${label}.png`),fullPage:true});
    const y=entry.exchanges.find(x=>x.endpoint==='/api/yolo-detect');
    const v=entry.exchanges.find(x=>x.endpoint==='/api/vlm-describe');
    const l=entry.exchanges.find(x=>x.endpoint==='/api/llm-answer');
    const counts={};
    for(const object of y?.response.objects || []) counts[object.label]=(counts[object.label] || 0)+1;
    const expectedSummary=y?.response.analysis?.summary || Object.keys(counts).sort((a,b)=>counts[b]-counts[a]).map(key=>`${key} ${counts[key]}개`).join(', ') || '인식된 객체 없음';
    entry.expected_yolo_summary=expectedSummary;
    const annotation=(await fs.readFile(path.join(dataset,selected.label),'utf8')).trim().split(/\r?\n/).filter(Boolean);
    const annotatedCounts={};
    const classNames=['Chair','Sofa','Table'];
    for(const line of annotation){const key=classNames[Number(line.split(/\s+/)[0])];annotatedCounts[key]=(annotatedCounts[key] || 0)+1;}
    entry.recognition_assessment={annotated_counts:annotatedCounts, detected_counts:counts,
      counts_match_annotation:classNames.every(key=>(counts[key] || 0)===(annotatedCounts[key] || 0)),
      note:'Integration checks below validate transport and response structure, not full recognition or VLM factual accuracy.'};
    entry.checks={all_http_200:[y,v,l].every(x=>x?.status===200),
      same_yolo_vlm_frame:!!y?.input_sha256 && y.input_sha256===v?.input_sha256,
      expected_class_detected:y?.response.objects?.some(x=>x.label===label) || false,
      vlm_nonempty:!!v?.response.description,
      yolo_forwarded:l?.request?.yolo_summary===expectedSummary,
      vlm_forwarded:l?.request?.vlm_description===v?.response.description,
      describe_tool:l?.response.tool==='describe',
      korean_answer:/[가-힣]/.test(l?.response.message || ''),
      expected_furniture_in_answer:(l?.response.message || '').includes(korean),
      browser_no_errors:entry.errors.length===0};
    report.cases.push(entry);
    await fs.writeFile(path.join(output,'validation.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify({label,seconds:entry.seconds,checks:entry.checks,yolo:y?.response,vlm:v?.response,llm:l?.response.message}));
    await ctx.close();
  }
  report.health_after=await(await fetch(base+'/api/health')).json();
  report.checks=report.cases.map(x=>({label:x.label,...x.checks}));
  await fs.writeFile(path.join(output,'validation.json'),JSON.stringify(report,null,2));
  assert.ok(report.cases.every(x=>Object.values(x.checks).every(Boolean)),'Inspect validation.json for failed integration checks');
} finally {await browser.close();}
