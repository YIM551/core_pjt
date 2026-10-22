// Record real browser workflows against the local server; no API responses are mocked.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';

const require = createRequire(import.meta.url);
const nodeModules = process.env.CORE_NODE_MODULES || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium} = require(path.join(nodeModules, 'playwright'));
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.join(root, 'results/spec_workflow_20261022');
const base = process.env.CORE_TEST_URL || 'http://127.0.0.1:8002';
const browser = await chromium.launch({channel: 'msedge', headless: true});
const report = {base_url: base, source: 'Actual local Edge browser, live YOLO/VLM/LLM and MediaPipe', cases: []};
const stages = new Set(process.argv.slice(2).length ? process.argv.slice(2) : ['spec1', 'spec2', 'spec3']);
if (process.argv.slice(2).length) {
  const previous = JSON.parse(await fs.readFile(path.join(output, 'spec3/browser_validation.json'), 'utf8'));
  report.cases = previous.cases.filter(item => !stages.has(item.stage));
}

async function context(stage) {
  const dir = path.join(output, stage);
  await fs.mkdir(path.join(dir, 'raw_video'), {recursive: true});
  const ctx = await browser.newContext({viewport: {width: 1440, height: 900},
    recordVideo: {dir: path.join(dir, 'raw_video'), size: {width: 1440, height: 900}}});
  const page = await ctx.newPage();
  page.setDefaultTimeout(180000);
  const entry = {stage, exchanges: [], errors: [], turns: []};
  const capturedQueues = {};
  await page.exposeBinding('__recordActualInput', async (_source, endpoint, values) => {
    const bytes = Buffer.from(values);
    const digest = createHash('sha256').update(bytes).digest('hex');
    const dir = path.join(output, 'captured_inputs');
    await fs.mkdir(dir, {recursive: true});
    const filename = path.join(dir, digest + '.jpg');
    await fs.writeFile(filename, bytes);
    (capturedQueues[endpoint] ||= []).push({digest, filename});
  });
  await page.addInitScript(() => {
    const originalFetch = window.fetch.bind(window);
    window.fetch = async (resource, options) => {
      const endpoint = new URL(typeof resource === 'string' ? resource : resource.url, location.href).pathname;
      if (options?.body instanceof Blob && ['/api/yolo-detect','/api/vlm-describe'].includes(endpoint)) {
        const bytes = new Uint8Array(await options.body.arrayBuffer());
        await window.__recordActualInput(endpoint, Array.from(bytes));
      }
      return originalFetch(resource, options);
    };
  });
  page.on('pageerror', error => entry.errors.push(String(error)));
  page.on('response', async response => {
    const endpoint = new URL(response.url()).pathname;
    if (!['/api/yolo-detect', '/api/vlm-describe', '/api/llm-answer'].includes(endpoint)) return;
    const bytes = response.request().postDataBuffer();
    const capture = endpoint !== '/api/llm-answer' ? capturedQueues[endpoint]?.shift() : null;
    const digest = capture?.digest || (bytes && createHash('sha256').update(bytes).digest('hex'));
    const captured = capture?.filename || null;
    entry.exchanges.push({endpoint, status: response.status(),
      input_sha256: digest, captured_input: captured,
      response: await response.json()});
  });
  await page.goto(base);
  await page.waitForFunction(() => typeof window.recognizeGesture === 'function');
  return {ctx, page, dir, entry};
}

async function submit(test, prompt) {
  const started = Date.now();
  const response = test.page.waitForResponse(r => new URL(r.url()).pathname === '/api/llm-answer');
  await test.page.locator('#subtab-local-pc .prompt-input').fill(prompt);
  await test.page.locator('#subtab-local-pc .prompt-send-btn').click();
  const result = await response;
  assert.equal(result.status(), 200);
  const body = await result.json();
  await test.page.waitForFunction(() => !document.querySelector('#subtab-local-pc .prompt-send-btn').disabled);
  const turn = {prompt, seconds: (Date.now()-started)/1000, response: body,
    yolo_display: await test.page.locator('#subtab-local-pc .yolo-result').innerText(),
    vlm_display: await test.page.locator('#subtab-local-pc .vlm-result').innerText(),
    gesture_display: await test.page.locator('#subtab-local-pc .mediapipe-result').innerText()};
  test.entry.turns.push(turn);
  await test.page.screenshot({path: path.join(test.dir, `turn_${test.entry.turns.length}.png`)});
  return body;
}

async function finish(test) {
  for (let i=0; i<test.entry.exchanges.length; i++) {
    const first = test.entry.exchanges[i];
    if (first.endpoint !== '/api/yolo-detect') continue;
    const following = test.entry.exchanges.slice(i+1).find(item => item.endpoint === '/api/vlm-describe');
    assert.match(first.input_sha256 || '', /^[a-f0-9]{64}$/, 'Actual image request bytes must be recorded');
    assert.ok(following, 'A VLM response must exist for every YOLO frame');
    assert.equal(first.input_sha256, following.input_sha256, 'YOLO and VLM must receive the same frame');
  }
  assert.equal(test.entry.errors.length, 0, 'Browser JavaScript errors');
  await test.page.waitForTimeout(1600);
  const video = test.page.video();
  await test.ctx.close();
  await video.saveAs(path.join(test.dir, 'demo.webm'));
  test.entry.video = path.join(test.dir, 'demo.webm');
  report.cases.push(test.entry);
  report.cases.sort((a,b) => a.stage.localeCompare(b.stage));
  await fs.writeFile(path.join(output, 'spec3/browser_validation.json'), JSON.stringify(report, null, 2));
}

function expectedMove(start, direction, steps, walls) {
  const delta = {up: [-1,0], down: [1,0], left: [0,-1], right: [0,1]}[direction];
  let [r,c] = start;
  for (let i=0; i<steps; i++) {
    const nr=r+delta[0], nc=c+delta[1];
    if(nr<1 || nr>8 || nc<1 || nc>8 || walls[(nr-1)*8+nc-1]) break;
    r=nr; c=nc;
  }
  return [r,c];
}

try {
  if (stages.has('spec1')) {
  const first = await context('spec1');
  await first.page.locator('#load-sofa-sample').click();
  await first.page.waitForFunction(() => !!document.querySelector('#subtab-local-pc')._inputImage);
  const description = await submit(first, '거실에 어떤 가구가 보여?');
  assert.equal(description.tool, 'describe');
  assert.match(first.entry.turns[0].gesture_display, /손을 인식하지 못/);
  await finish(first);
  console.log('PASS: Furniture image -> YOLO/VLM -> scene answer');
  }

  if (stages.has('spec2')) {
  const second = await context('spec2');
  await second.page.locator('#local-image-file').setInputFiles(path.join(root, 'samples/pointing_up.jpg'));
  await second.page.waitForFunction(() => !!document.querySelector('#subtab-local-pc')._inputImage);
  const pointed = await submit(second, '이쪽으로 2칸 가');
  assert.equal(pointed.tool, 'move');
  assert.deepEqual(pointed.args, {direction: 'up', steps: 2});
  assert.match(second.entry.turns[0].gesture_display, /손가락 1개/);
  await finish(second);
  console.log('PASS: supplied hand image -> real MediaPipe up -> move(up, 2)');
  }

  if (stages.has('spec3')) {
  const third = await context('spec3');
  await third.page.locator('#load-sofa-sample').click();
  await third.page.waitForFunction(() => !!document.querySelector('#subtab-local-pc')._inputImage);
  const walls = await third.page.locator('#sim-grid .sim-cell').evaluateAll(cells => cells.map(c => c.classList.contains('sim-wall')));
  const getPosition = async () => (await third.page.locator('#sim-current-coord').innerText()).match(/\d+/g).map(Number);
  const initial = await getPosition();
  const asked = await submit(third, '저쪽으로 2칸 가');
  assert.equal(asked.tool, 'ask');
  assert.deepEqual(asked.args, {steps: 2});
  assert.deepEqual(await getPosition(), initial);
  const direction = walls[1] ? 'down' : 'right';
  assert.equal(walls[direction === 'right' ? 1 : 8], false, 'Start must have an open neighbor');
  const moved = await submit(third, direction === 'right' ? '오른쪽' : '아래');
  assert.equal(moved.tool, 'move');
  assert.deepEqual(moved.args, {direction, steps: 2});
  const expected = expectedMove(initial, direction, 2, walls);
  assert.deepEqual(await getPosition(), expected);
  const stopped = await submit(third, '위로 10칸 가');
  assert.equal(stopped.tool, 'move');
  const finalExpected = expectedMove(expected, 'up', 10, walls);
  assert.deepEqual(await getPosition(), finalExpected);
  await third.page.locator('[data-tab="tab-simulator"]').click();
  await third.page.screenshot({path: path.join(third.dir, 'simulator.png')});
  third.entry.simulator = {walls, initial, after_followup: expected, after_boundary_or_wall: finalExpected,
    log: await third.page.locator('#sim-log-list').innerText()};
  await finish(third);
  console.log('PASS: ask -> remembered steps -> actual simulator move and boundary/wall stop');
  }
} finally {
  await browser.close();
}
