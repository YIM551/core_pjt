// Build the submission deck from actual run records with editable text and tables.
import fs from 'node:fs/promises';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';

const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const runtime = path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies');
const modules = path.join(runtime, 'node/node_modules');
process.env.RUNTIME_NODE_MODULES = modules;
const entry = require.resolve('@oai/artifact-tool', {paths: [path.join(runtime, 'node')]});
const {Presentation, PresentationFile} = await import(pathToFileURL(entry).href);
const skill = path.join(process.env.USERPROFILE,
  '.codex/plugins/cache/openai-primary-runtime/presentations/26.1020.11127/skills/presentations');
const {finalizePresentation} = await import(pathToFileURL(path.join(skill, 'container_tools/artifact_tool_utils.mjs')).href);
const build = path.join(root, '.backup/spec_presentation');
const output = path.join(root, 'output/submission');
await fs.mkdir(build, {recursive: true});
await fs.mkdir(path.join(build, 'previews'), {recursive: true});
await fs.mkdir(output, {recursive: true});
try { await fs.symlink(modules, path.join(build, 'node_modules'), 'junction'); }
catch (error) { if (error.code !== 'EEXIST') throw error; }
const json = async rel => JSON.parse(await fs.readFile(path.join(root, rel), 'utf8'));
const base = 'results/spec_workflow_20261022';
const before = await json(`${base}/spec1/before_coco_metrics.json`);
const after = await json(`${base}/spec1/after_finetune_metrics.json`);
const vlm = await json(`${base}/spec1/vlm_prompt_comparison.json`);
const browser = await json(`${base}/spec3/browser_validation.json`);
const gesture = await json(`${base}/spec2/gesture_validation.json`);
const sim = browser.cases.find(c => c.stage === 'spec3').simulator;
const presentation = Presentation.create({slideSize: {width: 1280, height: 720}});
const colors = {bg: '#F7F7F2', ink: '#142B32', teal: '#087F7D', gray: '#52656B', rule: '#D5DFDE'};
const font = 'Malgun Gothic';
const pct = v => (100*v).toFixed(1)+'%';
const nativeTableSlides = [];

function text(slide, value, x, y, w, h, size=28, bold=false, color=colors.ink) {
  const shape = slide.shapes.add({geometry: 'textbox', position: {left:x, top:y, width:w, height:h},
    fill:'none', line:{fill:'none',width:0}});
  shape.text = value;
  shape.text.style = {typeface:font,fontSize:size,bold,color,verticalAlignment:'top',wrap:'square',insets:0};
  return shape;
}
function slide(title, notes='') {
  const s = presentation.slides.add();
  s.background.fill = colors.bg;
  text(s,title,72,45,1136,80,44,true);
  text(s,String(presentation.slides.items.length).padStart(2,'0'),1160,670,60,24,16,false,colors.gray);
  s.speakerNotes.text = notes;
  return s;
}
function table(s, values, y, height, widths, x=72, width=1136, size=24) {
  const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width,height,columnWidths:widths,values});
  for(let r=0;r<values.length;r++) for(let c=0;c<values[0].length;c++) {
    const cell=t.getCell(r,c);
    cell.fill=r===0 ? colors.teal : (r%2 ? '#FFFFFF' : '#EDF2EF');
    cell.text.style={typeface:font,fontSize:size,bold:r===0,color:r===0?'#FFFFFF':colors.ink,
      verticalAlignment:'middle',insets:{top:8,bottom:8,left:14,right:12}};
  }
  t.borders.assign({fill:colors.rule,width:1,style:'solid'});
  nativeTableSlides.push(presentation.slides.items.indexOf(s)+1);
  return t;
}
function image(s, rel, x,y,w,h) {
  return s.images.add({blob:new Uint8Array(readFileSync(path.join(root,rel))),
    contentType:rel.endsWith('.png')?'image/png':'image/jpeg',
    alt:rel,fit:'contain',position:{left:x,top:y,width:w,height:h}});
}
function note(s,value,y=625) {text(s,value,72,y,1136,48,18,false,colors.gray);}

{
  const s=slide('', '제출자: 광주 5반 임나경. 2026-10-22. 명세서 16-C-2-01, 02, 03의 필수 기능을 순서대로 구현·검증한 결과. Ballie 및 SmartThings는 참고 콘셉트다. 실제 로봇·가전은 연결하지 않았다.');
  text(s,'가정용 집사 로봇',72,160,1136,105,68,true);
  text(s,'멀티모달 AI Workflow',72,280,1136,95,56,true,colors.teal);
  text(s,'Furniture 인식 · 장면 설명 · 의도 파악과 이동',76,410,1120,60,30);
  text(s,'명세서 1 · 2 · 3 수행 결과',76,500,1120,50,28);
  text(s,'광주 5반 임나경\n2026.10.22',76,580,900,70,24,false,colors.gray);
}
{
  const s=slide('집사형 로봇의 역할', 'Sources: Samsung 2025-04-09 Ballie announcement https://news.samsung.com/us/samsung-google-cloud-expand-partnership-bring-gemini-ballie-home-ai-companion-robot-by-samsung/ ; SmartThings device model https://developer.smartthings.com/docs/service-integrations/query-and-list-devices . Historical concept, not a claim of current Ballie availability.');
  text(s,'집 안의 상황을 보고 사용자의 요청에 답하는 로봇',72,155,1120,90,36,true,colors.teal);
  text(s,'인식\nYOLO가 가구를 검출하고 VLM이 거실의 맥락을 설명합니다.',72,280,1120,100,28);
  text(s,'의도와 동작\nLLM이 설명·이동·되묻기를 고르면 코드가 방향과 칸 수를 검증합니다.',72,410,1120,100,28);
  text(s,'가전 연동 확장\nSmartThings 상태 조회와 명령 API는 후속 연동 대상으로 설계합니다.',72,540,1120,90,28);
  note(s,'현재 동작 범위는 로컬 이미지와 격자 시뮬레이터입니다.',650);
}
{
  const s=slide('모델 선정', 'Sources: https://docs.ultralytics.com/models/yolo11/ ; https://docs.ultralytics.com/models/yolov8/ ; https://www.ultralytics.com/license ; https://huggingface.co/ggml-org/Qwen2.5-VL-3B-Instruct-GGUF ; https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct . Official detector numbers refer to 640px COCO/CPU ONNX. Alternative VLM 7B was not measured locally. YOLO license reference AGPL-3.0 or Enterprise; GGUF model card Apache-2.0.');
  table(s,[['검출 후보','파라미터','COCO mAP50–95','CPU ONNX 참고'],
    ['YOLOv8n','3.2M','37.3','80.4 ms'],['YOLO11n','2.6M','39.5','56.1 ms'],['YOLO11s','9.4M','47.0','90.0 ms']],155,270,[320,220,310,286]);
  text(s,'YOLO11n: 작은 모델로 CPU 추론과 전이학습을 함께 수행',72,460,1136,55,28,true,colors.teal);
  text(s,'VLM: Qwen2.5-VL-3B Q4_K_M + mmproj\n3B를 CPU에서 검증했고, 7B는 로컬 미측정 후보로 남겼습니다.',72,535,1136,85,26);
  note(s,'공식 참고 수치와 이 PC의 실측 속도는 측정 방식이 달라 직접 비교하지 않습니다.',640);
}
{
  const s=slide('Furniture 데이터 정비', 'Evidence: datasets/roboflow/furniture/v2_curated_v2/derivation.json and results/furniture_day1/data_audit/independent_verification.json. All 689 thumbnails reviewed, 125 originals additionally reviewed. Assistant visual screening is not exhaustive ground-truth certification. Raw source preserved.');
  text(s,'689장 중 565장 채택, 124장 추가 검수 대기',72,145,1136,70,34,true,colors.teal);
  table(s,[['분할','Chair','Sofa','Table','합계'],['train','156','113','124','393'],
    ['valid','34','24','27','85'],['test','34','24','29','87']],245,270,[280,210,210,210,226]);
  text(s,'같은 가구·촬영 공간을 한 분할에 묶고 seed 20261021로 고정',72,550,1136,50,26);
  note(s,'원본 파일 해시 보존 · 알려진 그룹 겹침 0건 · test는 이번 학습·평가에서 사용하지 않음',625);
}
{
  const s=slide('파인튜닝 전후 평가', 'Evidence: results/spec_workflow_20261022/spec1/finetune_compare.csv and *_metrics.json. 10 epochs, imgsz320, batch8, CPU. Same85 valid images, same custom evaluator and confidence/IoU settings. COCO chair56,couch57,dining table60 mapped to Furniture0,1,2. Broad Table and dining table are not identical semantic coverage. P/R are macro averages at conf.25 and IoU.5, mAP uses confidence floor.001. This is a small curated mainly-single-object dataset, not production room performance.');
  table(s,[['같은 valid 85장','COCO 대응 모델','Furniture 10 epoch'],
    ['mAP50',pct(before.map50),pct(after.map50)],['mAP50–95',pct(before.map50_95),pct(after.map50_95)],
    ['Precision (conf 0.25)',pct(before.precision_at_conf025),pct(after.precision_at_conf025)],
    ['Recall (conf 0.25)',pct(before.recall_at_conf025),pct(after.recall_at_conf025)]],150,350,[520,308,308]);
  text(s,'Chair·Sofa·Table로 클래스 번호를 명시적으로 대응시켜 비교',72,540,1136,50,28,true,colors.teal);
  note(s,'선별된 단일 가구 사진의 검증 성능입니다. 복잡한 실내 장면과 실물 운용은 별도 검증이 필요합니다.',620);
}
{
  const s=slide('PoC 응답 시간과 병목', 'Evidence: results/spec_workflow_20261022/spec1/poc_timing.csv and measurement.csv. One warm-up pair excluded, one sequential/parallel pair on same sofa JPEG. VLM max-side448,max_tokens80. This small timing sample does not support a statistically significant speedup claim.');
  table(s,[['호출 방식','전체 시간'],['순차','6.61초'],['병렬','6.57초']],180,230,[330,260],72,590,30);
  text(s,'VLM이 전체 응답 시간의 대부분을 차지',72,455,600,100,32,true,colors.teal);
  text(s,'입력 긴 변 448px\n출력 80 tokens 상한\n워밍업 후 같은 이미지로 측정',72,555,600,100,24);
  image(s,`${base}/spec1/sofa_after.jpg`,720,165,470,470);
}
{
  const s=slide('VLM 프롬프트와 출력 규격', 'Evidence: results/spec_workflow_20261022/spec1/vlm_prompt_comparison.json and vlm_measurement.csv. All four prompts same448px input, temperature0,max_tokens96. Free output hits token limit; counting repeats objects/mixes scripts; obstacle-only request echoes instruction. Regulated runs use main.py contract and both equal. Obstacle text is model output, not an independently verified safety label.');
  table(s,[['프롬프트','실측 시간','관찰 결과'],['자유 설명',vlm.runs[0].seconds.toFixed(2)+'초','96 tokens에서 잘림'],
    ['한국어 간결 설명',vlm.runs[1].seconds.toFixed(2)+'초','장면을 한국어로 설명'],
    ['개수 나열',vlm.runs[2].seconds.toFixed(2)+'초','중복 나열·한자 혼용'],
    ['장애물만 질문',vlm.runs[3].seconds.toFixed(2)+'초','질문을 되풀이함']],155,330,[360,210,566],72,1136,25);
  text(s,'규격 출력은 한국어 40자 이내와 장애물 표기를 검사',72,525,1136,55,28,true,colors.teal);
  text(s,vlm.regulated_runs[0].output,72,590,1136,60,24);
}
{
  const s=slide('이미지에서 LLM 답변까지', 'Evidence: actual browser screenshot results/spec_workflow_20261022/spec1/turn_1.png and spec3/browser_validation.json. Camera unavailable; user-selected local image is captured once and shared by all perception paths. Screenshot shows actual model outputs; pillow or other statements are not promoted to ground truth.');
  image(s,`${base}/spec1/turn_1.png`,72,135,1136,500);
  note(s,'예제·파일·웹캠 입력을 같은 처리 흐름으로 연결하고 출처별 결과를 따로 표시합니다.',646);
}
{
  const s=slide('손 방향과 손가락 개수 검증', 'Evidence: results/spec_workflow_20261022/spec2/gesture_validation.json. Supplied pointing_up/victory images at0,90,180,270 degrees, each with mirror false/true. 16 direction and16 finger count assertions pass,21landmarks observed. Not three personal live-capture images required by optional F205.');
  image(s,`${base}/spec2/pointing_up_rotations.png`,72,145,1136,300);
  table(s,[['검증 항목','결과'],['회전·좌우 반전 방향',`${gesture.directions_passed} / ${gesture.total}`],
    ['펼친 손가락 개수',`${gesture.finger_counts_passed} / ${gesture.total}`]],475,150,[760,376],72,1136,27);
  note(s,'제공된 정지 이미지로 검증했습니다. 실제 웹캠의 조명·흔들림 검증은 남아 있습니다.',650);
}
{
  const s=slide('도구 호출과 코드 규칙', 'Evidence: API_설계.md, main.py, scripts/spec3_rules_validate.py, results/spec_workflow_20261022/spec3/rule_regressions.json. Final API suite64/64.17 regression assertions verify R5 with all valid LLM tool choices, new scene questions remain describe, false direction words, overflow-safe steps, malformed JSON and preserving obstacle suffix.');
  table(s,[['규칙','코드가 보장하는 동작'],['R1·R2','도구 이름, 네 방향, 1~10칸 정수 보정'],
    ['R3','질문·이전 질문·손의 방향 근거가 없으면 되묻기'],['R4','ask일 때만 추가 정보 요청'],
    ['R5','방향만 답해도 이전에 요청한 칸 수로 이동']],160,325,[230,906],72,1136,26);
  text(s,'API 64/64 통과 · 규칙 회귀 검사 17/17 통과',72,535,1136,60,34,true,colors.teal);
  note(s,'추가 수정: “가위”의 방향 오인 방지, LLM이 describe로 오분류한 방향 답변 처리',625);
}
{
  const s=slide('되묻기 후 이동과 시뮬레이터', 'Evidence: results/spec_workflow_20261022/spec3/browser_validation.json and simulator.png. Actual Edge run: ask remembers2 steps, direction-only reply invokes move; wall/boundary result independently computed from observed DOM wall map and compared to actual position. Grid movement is not physical navigation.');
  image(s,`${base}/spec3/simulator.png`,72,135,900,510);
  text(s,'“저쪽으로 2칸 가”\n방향을 되묻기\n\n방향만 답변\n기억한 2칸 이동',990,175,240,270,25,true,colors.teal);
  note(s,`실제 좌표: 시작 (${sim.initial.join(',')}), 방향 답변 후 (${sim.after_followup.join(',')}), 위 이동 후 (${sim.after_boundary_or_wall.join(',')})`,648);
}
{
  const s=slide('인식 기록을 데이터 파이프라인으로 연결', 'Evidence: actual captured JPEG requests plus spec3/browser_validation.json, dataset split_manifest.json and spec1 CSV/JSON files. Workflow event records are derived from actual browser exchanges. A database or production streaming platform has not been deployed.');
  table(s,[['기록 단계','보관할 데이터'],['입력','실제 전송 JPEG와 SHA-256'],
    ['인식','YOLO 박스·confidence, VLM 문장, 손 방향'],['의도','질문, 대화 기록, 선택한 tool과 args'],
    ['검증','데이터셋 버전, 모델 파일, 평가 CSV, 이동 로그']],170,345,[330,806],72,1136,26);
  text(s,'같은 입력을 다시 재생하고 모델·데이터 버전별 결과를 비교',72,555,1136,65,30,true,colors.teal);
}
{
  const s=slide('현재 범위와 SmartThings 확장', 'Sources: https://developer.smartthings.com/docs/service-integrations/query-and-list-devices and https://developer.smartthings.com/docs/service-integrations/control-devices . SmartThings authorized status/command APIs are future work. No device writes or Ballie hardware integration were performed. Optional F105 camera-built dataset, F106 controlled three-setting comparison, F205 personal captures, F206 source-count conflict logic and F305 live gesture sequence remain unverified or unimplemented, as detailed in completion.json.');
  table(s,[['구분','내용'],['완료','명세서 1·2·3 필수 기능과 로컬 이미지 시연'],
    ['실물 검증 필요','웹캠 환경, 집 안 촬영·추가 라벨링, 실제 주행'],
    ['SmartThings 후속','인증된 기기의 상태 조회와 명령 실행 결과 확인']],180,280,[320,816],72,1136,26);
  text(s,'가구 검출만으로 안전한 이동 경로나 가전 상태를 판단하지 않습니다.',72,505,1136,90,30,true,colors.teal);
  note(s,'Ballie는 참고 콘셉트입니다. 심화 기능의 구현·미검증 항목은 제출 기록에 구분했습니다.',630);
}

const candidate = path.join(build, 'candidate.pptx');
await (await PresentationFile.exportPptx(presentation)).save(candidate);
console.log(`Draft exported: ${presentation.slides.items.length} slides`);
for(let i=0;i<presentation.slides.items.length;i++) {
  const png=await presentation.export({slide:presentation.slides.items[i],format:'png',scale:1});
  await fs.writeFile(path.join(build,`previews/slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));
  console.log('Rendered slide',i+1);
}
const final = path.join(output,'AI 코어_2회차_집사형로봇_광주_5반_임나경_최종.pptx');
const result = await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:final,
  pythonExecutable:path.join(runtime,'python/python.exe'),
  integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',
    ...nativeTableSlides.flatMap(n=>['--require-native-table-slide',String(n)])],
  explicitTotalSlideCount:13,requiredNativeTableOwnerSlides:nativeTableSlides,
  fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,
  receiptPath:path.join(build,'validation_final.json')});
console.log(JSON.stringify(result));
