// Import and update the existing deck; preserve its styles and original slides.
import fs from 'node:fs/promises';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const runtime=path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies');
const skill=path.join(process.env.USERPROFILE,'.codex/plugins/cache/openai-primary-runtime/presentations/26.1017.22135/skills/presentations');
const require=createRequire(import.meta.url);
process.env.RUNTIME_NODE_MODULES=path.join(runtime,'node/node_modules');
const {PresentationFile,FileBlob}=await import(pathToFileURL(require.resolve('@oai/artifact-tool',{paths:[path.join(runtime,'node')]})).href);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const build=path.join(root,'.backup/submission_v2');
const output=path.join(root,'output/submission_v2');
await fs.mkdir(output,{recursive:true});await fs.mkdir(path.join(build,'after'),{recursive:true});
try{await fs.symlink(path.join(runtime,'node/node_modules'),path.join(build,'node_modules'),'junction');}catch(e){if(e.code!=='EEXIST')throw e;}
const source=path.join(root,'output/submission/AI 코어_2회차_집사형로봇_광주_5반_임나경_최종.pptx');
const p=await PresentationFile.importPptx(await FileBlob.load(source));
const original=[...p.slides.items];
const json=async name=>JSON.parse(await fs.readFile(path.join(root,name),'utf8'));
const finalTest=await json('results/furniture_final_test_20261022/comparison.json');
const latency=await json('results/optimization_20261022/comparison.json');
const study=await json('results/vlm_settings_20261022/comparison.json');
const f206=await json('results/f206_20261022/comparison.json');
const font='Malgun Gothic';const ink='#142B32',teal='#087F7D';
const percent=v=>(100*v).toFixed(2)+'%';
function text(s,value,x,y,w,h,size=28,bold=false,color=ink){
 const shape=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 shape.text=value;shape.text.style={typeface:font,fontSize:size,bold,color,verticalAlignment:'top',wrap:'square',insets:0};return shape;
}
function slide(title,notes){const s=p.slides.add();s.background.fill='#F7F7F2';text(s,title,72,45,1136,80,44,true);s.speakerNotes.text=notes;return s;}
function note(s,t){text(s,t,72,635,1136,55,18,false,'#52656B');}
function table(s,values,y,h,widths,size=25){
 const t=s.tables.add({rows:values.length,columns:values[0].length,left:72,top:y,width:1136,height:h,columnWidths:widths,values});
 for(let r=0;r<values.length;r++)for(let c=0;c<values[0].length;c++){
  const cell=t.getCell(r,c);cell.fill=r===0?teal:r%2?'#FFFFFF':'#EDF2EF';
  cell.text.style={typeface:font,fontSize:size,bold:r===0,color:r===0?'#FFFFFF':ink,verticalAlignment:'middle',
   insets:{top:8,bottom:8,left:14,right:12}};
 }t.borders.assign({fill:'#D5DFDE',width:1,style:'solid'});return t;
}
function image(s,rel,x,y,w,h){s.images.add({blob:new Uint8Array(readFileSync(path.join(root,rel))),contentType:'image/jpeg',alt:rel,fit:'contain',position:{left:x,top:y,width:w,height:h}});}
function replace(s,old,value){const shape=s.shapes.items.find(x=>String(x.text)===old);if(!shape)throw Error('Missing text: '+old);shape.text.replace(old,value);}
replace(original[0],'명세서 1 · 2 · 3 수행 결과','명세서 1 · 2 · 3 수행 결과 · 최신 v2');
replace(original[1],'의도와 동작\nLLM이 설명·이동·되묻기를 고르면 코드가 방향과 칸 수를 검증합니다.',
 '의도와 동작\n단순 장면 질문은 근거로 답하고, 이동·복합 질문은 LLM과 규칙으로 처리합니다.');
replace(original[3],'원본 파일 해시 보존 · 알려진 그룹 겹침 0건 · test는 이번 학습·평가에서 사용하지 않음',
 '원본·고정 분할 보존 · test 87장은 최종 평가에만 사용 · test 기반 튜닝 없음');
replace(original[5],'PoC 응답 시간과 병목','초기 PoC 응답 시간과 병목');
replace(original[6],'VLM 프롬프트와 출력 규격','초기 VLM 프롬프트와 출력 규격');
replace(original[7],'이미지에서 LLM 답변까지','Furniture 모델의 대시보드 연결');
replace(original[7],'예제·파일·웹캠 입력을 같은 처리 흐름으로 연결하고 출처별 결과를 따로 표시합니다.',
 'best.pt 연결 · 소파·의자·테이블 3종 검증 · YOLO/VLM 근거를 최종 답변에 전달');
original[7].images.items[0].replace({blob:new Uint8Array(readFileSync(path.join(root,'results/vlm_settings_20261022/browser/Sofa.png'))),contentType:'image/png',fit:'contain'});
original[7].speakerNotes.text='Evidence: results/furniture_dashboard_20261022/validation.json and results/vlm_settings_20261022/browser/validation.json. Latest real Edge screenshot with Furniture best.pt. All3 images passed HTTP/shared-frame/forwarding checks. Table has overlapping Sofa/Table raw detections, handled as ambiguity by F206. Simple scene questions take deterministic cited-response fast path rather than generating and discarding LLM output.';
original[12].tables.items[0].cells.set(1,1,'필수 기능·F206·VLM 최적화·test 평가');
original[12].speakerNotes.text='Latest scope: F206 overlap/count mismatch/source attribution implemented with bounded class/count patterns; F106 controlled resolution/token experiments complete on static images. Camera collection F105, personal captures F205 and live gesture sequence F305 remain unverified/partial. SmartThings is future work; no real device control. Existing completion.json is historical; current status is in latest_submission_status.json.';
const testSlide=slide('최종 test 87장 평가', '');
// Keep all visible text Korean and source all numbers from the locked evaluation.
testSlide.shapes.items[0].text='최종 test 87장 평가';
table(testSlide,[['지표','valid 85장','test 87장'],['mAP50',percent(finalTest.valid.map50),percent(finalTest.test.map50)],
 ['mAP50–95',percent(finalTest.valid.map50_95),percent(finalTest.test.map50_95)],
 ['Precision',percent(finalTest.valid.precision_at_conf025),percent(finalTest.test.precision_at_conf025)],
 ['Recall',percent(finalTest.valid.recall_at_conf025),percent(finalTest.test.recall_at_conf025)]],155,340,[520,308,308]);
text(testSlide,'conf 0.25 · IoU 0.5에서 TP 87 / FP 0 / FN 0',72,535,1136,60,30,true,teal);
note(testSlide,'가중치·평가 설정 고정 · valid 재현 확인 · test로 추가 학습·임계값 조정하지 않음');
testSlide.speakerNotes.text='Evidence: results/furniture_final_test_20261022/comparison.json, evaluation_lock.json, valid_vs_test.csv. imgsz320, conf floor.001, NMS IoU.7, CPU. P/R are macro at conf.25 and matching IoU.5. Valid reproduces original within1e-8. Test now consumed, never used for tuning. Frozen best.pt SHA256 recorded. Small curated single-object images; 100% P/R is not deployment perfection. Native AP interpolation can give .995 despite perfect operating-point matches.';
const localization=slide('박스 경계 정밀도와 해석','Evidence: results/furniture_final_test_20261022/localization_analysis.json and localization_examples.jpg. Lowest IoU per class, not cherry-picked failures. Green GT/red prediction. At conf.25, TP87 at IoU.75, TP73 at.9, TP38 at.95. Table test mAP50–95 .8290714 vs valid .9213572. Annotation boundary conventions also affect this metric.');
image(localization,'results/furniture_final_test_20261022/localization_examples.jpg',72,145,1136,385);
text(localization,'test mAP50–95: 의자 94.06% · 소파 91.53% · 테이블 82.91%',72,540,1136,60,27,true,teal);
note(localization,'초록: 주석 / 빨강: 예측 · 종류·개수 검출과 정밀한 박스 경계 일치는 별도 평가');
const speed=slide('사용하지 않는 생성과 대기 제거','Evidence: results/optimization_20261022/before.json, after_uncached.json, after_cached.json, comparison.json. Warm same-table API 3 trials per condition. No cache median9.7052→7.2724s. Simple full-match scene questions bypass discarded LLM generation; moves/complex prompts keep LLM/rules. Repeated exact-input cache hits .0395/.0473s are reuse, not faster new-frame inference. Max8/TTL60s. UI550ms waits removed. These experiments are distinct from later six-image VLM study; do not compound gains.');
table(speed,[['서버 API 중앙값','변경 전','변경 후'],['YOLO','0.050초','0.046초'],['VLM','7.082초','7.270초'],
 ['답변 구성','2.623초','0.002초'],['전체 (캐시 제외)',latency.baseline_warm_api_median_seconds.toFixed(3)+'초',latency.optimized_uncached_warm_api_median_seconds.toFixed(3)+'초']],145,350,[520,308,308]);
text(speed,'약 25% 단축 · 이동·복합 질문의 LLM 경로는 유지',72,535,1136,60,30,true,teal);
note(speed,'동일 이미지 캐시 적중은 0.04~0.05초 · 새 이미지 성능과 구분 · 화면 강제 대기도 제거');
const setting=slide('새 이미지의 VLM 추론 최적화','Evidence: results/vlm_settings_20261022/{screen,refine,confirm,confirm40,policy_validation,comparison,deployment_verification}.json. 60 measured inference trials on6 valid images; model warmup excluded, result cache bypassed and model.reset per trial. Params224/336/392/420/448 and40/60tokens. Manual source-image/text checks beyond class keywords. Adaptive performs extra live YOLO selection, whose time is included. All high confidence>=.8 Chair/Sofa/couch ->420; others448. Six-image paired average6.22276→5.39286 (-13.34%). Not a general quality guarantee; baseline desk unclear word persists.');
table(setting,[['비교 항목','결론'],['224·336·392px','배경·물체 설명 오류로 기본 설정 제외'],['420px','고확신 의자·소파에 적용'],
 ['테이블·혼동·미검출','기존 448px 유지'],['40 / 60 tokens','40의 이득 작음 → 60 유지']],145,330,[360,776],25);
text(setting,`캐시 없는 6장 평균 ${study.mean_before_seconds.toFixed(2)}초 → ${study.mean_after_seconds.toFixed(2)}초 (약 13% 단축)`,72,520,1136,65,32,true,teal);
note(setting,'작은 정지 이미지 실험의 결과 · 첫 모델 로딩 제외 · 모든 이미지의 품질을 보장하지 않음');
const conflict=slide('F206: 불일치를 확정된 사실로 답하지 않기','Evidence: results/f206_20261022/comparison.json and after/validation.json; latest browser/Table.png confirms retained behavior. Same weights/input/raw predictions/VLM description. Sofa confidence.676 vs Table.526, cross-class IoU.9369. No winning class selected by confidence. Count mismatch only for explicit supported numeric patterns; non-mentioned VLM count is unknown, not zero. Both source blocks enforced in describe responses. F2065tests, later optimization8tests and deployment10checks.');
table(conflict,[['항목','변경 전','변경 후'],['원시 검출','Sofa 67.6% + Table 52.6%','원본 검출 보존'],
 ['LLM 입력 개수','Sofa 1개, Table 1개','중복 후보 · 종류·개수 미확정'],
 ['최종 안내','소파 1개, 테이블 1개','출처 인용 · 불일치 · 재확인']],165,285,[250,435,451],24);
text(conflict,`박스 IoU ${f206.overlaps[0].iou}: 겹치는 후보를 별개 물체로 합산하지 않음`,72,490,1136,80,29,true,teal);
note(conflict,'명시 개수 차이도 검사 · VLM 미언급은 미상 · 오검출 자체를 고친 것으로 해석하지 않음');
const order=[...original.slice(0,5),testSlide,localization,...original.slice(5,7),speed,setting,original[7],conflict,...original.slice(8)];
order.forEach((s,i)=>s.moveTo(i));
for(let i=0;i<p.slides.items.length;i++){
 const s=p.slides.items[i];const number=s.shapes.items.find(x=>/^\d{2}$/.test(String(x.text)));
 if(number)number.text=String(i+1).padStart(2,'0');else text(s,String(i+1).padStart(2,'0'),1160,670,60,24,16,false,'#52656B');
}
const candidate=path.join(build,'candidate-v2-confirmed.pptx');
await(await PresentationFile.exportPptx(p)).save(candidate);
const owners=p.slides.items.map((s,i)=>s.tables.items.length?i+1:null).filter(Boolean);
const final=path.join(output,'AI 코어_2회차_집사형로봇_광주_5반_임나경_최신_v2_확정.pptx');
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:final,
 pythonExecutable:path.join(runtime,'python/python.exe'),
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',...owners.flatMap(n=>['--require-native-table-slide',String(n)])],
 explicitTotalSlideCount:18,requiredNativeTableOwnerSlides:owners,
 fontPolicy:{basis:'reference',families:[font],referencePath:source,referenceSha256:createHash('sha256').update(readFileSync(source)).digest('hex')},
 verifyArtifactToolImport:true,receiptPath:path.join(build,'validation-v2-confirmed.json')});
const saved=await PresentationFile.importPptx(await FileBlob.load(final));
for(let i=0;i<saved.slides.items.length;i++){
 const blob=await saved.export({slide:saved.slides.items[i],format:'png',scale:1});
 await fs.writeFile(path.join(build,'after',`${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await blob.arrayBuffer()));
}
console.log(JSON.stringify({final,slides:saved.slides.items.length,result}));
