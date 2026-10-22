"""Package the reviewed v2 deck and latest evidence without rewriting historical artifacts."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[1]
output=root/'output/submission_v2'
deck=output/'AI 코어_2회차_집사형로봇_광주_5반_임나경_최신_v2_확정.pptx'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if (output/'submission_manifest_v2.json').exists():raise SystemExit('Preserve completed v2 package; use a new version for changes.')
if not deck.exists():raise SystemExit('Validated deck missing')
receipt=read(root/'.backup/submission_v2/validation-v2-confirmed.json')
if receipt['finalSha256']!=sha(deck):raise RuntimeError('Presentation validation receipt mismatch')
old=read(root/'output/submission/submission_manifest.json')
for record in [old['deck'],*old['archives']]:
    if sha(root/'output/submission'/record['name'])!=record['sha256']:raise RuntimeError('Historical submission changed')
test=read(root/'results/furniture_final_test_20261022/comparison.json')
lock=read(root/'results/furniture_final_test_20261022/evaluation_lock.json')
weights=root/'source/2회차_day1/runs/furniture_spec1_20261022/weights/best.pt'
if sha(weights)!=lock['weights_sha256']:raise RuntimeError('Frozen best.pt changed')
historical=read(root/'results/spec_workflow_20261022/completion.json')
status={'version':'v2','created_utc':datetime.now(timezone.utc).isoformat(),
 'code_base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
 'submitter':old['submitter'],'mandatory':historical['mandatory'],
 'optional':{**historical['optional'],
   'F106':{'status':'verified_static_experiments','evidence':'results/vlm_settings_20261022/','limits':'Six images,60 measured trials; no live-camera quality guarantee'},
   'F206':{'status':'implemented_and_verified','evidence':'results/f206_20261022/','limits':'Supported class/count patterns; ambiguity reporting does not repair detector accuracy'}},
 'test_status':'Final test87 evaluated; not used for tuning; no longer unused',
 'final_test':{'map50':test['test']['map50'],'map50_95':test['test']['map50_95'],
               'precision_at_conf025':test['test']['precision_at_conf025'],'recall_at_conf025':test['test']['recall_at_conf025']},
 'weights_sha256':sha(weights),
 'video_scope':'Original spec1/2/3 browser videos retained as historical demonstrations. Latest Furniture/F206/optimization states are screenshots and actual JSON/log evidence, not newly recorded videos.',
 'historical_record_notice':'results/spec_workflow_20261022/completion.json is the earlier snapshot. This status supersedes its F106/F206/test statements.',
 'limits':historical['limits'],
 'validation_receipt':'presentation_validation_v2.json'}
save(output/'latest_submission_status.json',status)
save(output/'presentation_validation_v2.json',receipt)
source_names=['main.py','index.html','inference_optimization.py','perception_consistency.py',
              'API_검증.py','API_설계.md','requirements.txt','README.md']
source_names += [p.relative_to(root).as_posix() for p in (root/'scripts').iterdir()
                 if p.is_file() and p.suffix in ('.py','.mjs','.ps1')]
common={}
def add(p,name=None):
    common[name or p.relative_to(root).as_posix()]=p
add(deck,'발표자료/'+deck.name)
add(output/'latest_submission_status.json')
add(output/'presentation_validation_v2.json')
for name in source_names:add(root/name,'updated_source/'+name)
for folder in ['furniture_dashboard_20261022','f206_20261022','optimization_20261022','vlm_settings_20261022','furniture_final_test_20261022']:
    for p in (root/'results'/folder).rglob('*'):
        if p.is_file() and 'raw_video' not in p.parts:add(p)
for p in weights.parent.parent.rglob('*'):
    if p.is_file():add(p)
for p in (root/'datasets/roboflow/furniture/v2_curated_v2').iterdir():
    if p.is_file() and p.suffix!='.cache':add(p)
for p in (root/'samples').glob('*'):
    if p.is_file():add(p)
base=root/'results/spec_workflow_20261022'
for name in ['environment.json','completion.json','workflow_events.jsonl','video_metadata.json']:add(base/name)
archives=[]
for stage in range(1,4):
    members=dict(common)
    for p in (base/f'spec{stage}').rglob('*'):
        if p.is_file() and 'raw_video' not in p.parts:members[p.relative_to(root).as_posix()]=p
    for p in (base/'captured_inputs').glob('*.jpg'):members[p.relative_to(root).as_posix()]=p
    filename=f'AI 코어_2회차_PJT0{stage}_동작시연영상_광주_5반_임나경_최신_v2.zip'
    destination=output/filename
    if destination.exists():raise RuntimeError('Do not overwrite archive')
    hashes={name:sha(p) for name,p in sorted(members.items())}
    instructions=f'''광주 5반 임나경 / 명세서 {stage} / 최신 v2

최신 PPT: 발표자료/{deck.name}
최신 상태: output/submission_v2/latest_submission_status.json
Furniture 연결·F206·VLM 최적화·최종 test 평가는 results의 각 최신 폴더에서 확인합니다.
test87장은 최종 평가에 사용했으며 이 결과로 가중치나 임계값을 조정하지 않았습니다.

시연 영상: results/spec_workflow_20261022/spec{stage}/demo.webm
이 영상은 초기 명세서 시연 당시 기록이며 최신 변경을 새로 촬영한 영상이 아닙니다.
최신 동작은 vlm_settings_20261022/browser 및 f206_20261022의 화면·실제 요청/응답을 참조하세요.
초기 completion.json의 F106/F206/test 미사용 표기는 과거 상태입니다. 최신 상태 JSON을 우선합니다.

실행: 기존 프로젝트에 updated_source/의 내용을 프로젝트 루트로 복사합니다.
ZIP의 source/, samples/, datasets/ 및 results/는 같은 상대 경로로 복원합니다.
가상환경과 대용량 VLM/LLM GGUF·MediaPipe 런타임 자산은 기존 환경 또는 README 설치/다운로드 절차로 준비합니다.
powershell -ExecutionPolicy Bypass -File scripts/start_furniture_dashboard.ps1
http://127.0.0.1:8003 에서 실행합니다.
GPU·웹캠·실물 로봇·SmartThings 기기 제어는 이번 검증 범위가 아닙니다.
파일 해시는 FILES_SHA256.json에서 확인합니다. 이전 제출 ZIP과 PPT는 수정하지 않았습니다.
'''
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in sorted(members.items()):z.write(p,name)
        z.writestr('제출_실행_안내.txt',instructions.encode('utf-8-sig'))
        z.writestr('FILES_SHA256.json',json.dumps(hashes,ensure_ascii=False,indent=2).encode('utf-8'))
    with zipfile.ZipFile(destination) as z:
        if z.testzip() or len(z.namelist())!=len(set(z.namelist())):raise RuntimeError('ZIP integrity failure')
        for name,digest in hashes.items():
            if hashlib.sha256(z.read(name)).hexdigest()!=digest:raise RuntimeError('ZIP member checksum mismatch: '+name)
    archives.append({'name':filename,'bytes':destination.stat().st_size,'sha256':sha(destination),'verified_members':len(hashes)})
manifest={'version':'v2','submitter':old['submitter'],'deck':{'name':deck.name,'bytes':deck.stat().st_size,'sha256':sha(deck),'slides':18},
          'archives':archives,'preserves_previous_submissions':True,'latest_video_recorded':False,
          'validation':'Every ZIP CRC, member uniqueness and all member SHA256 checked;18slides rendered and visually inspected.',
          'weights_sha256':sha(weights),'test_evaluation_reexecuted':False}
save(output/'submission_manifest_v2.json',manifest)
print(json.dumps(manifest,ensure_ascii=True),flush=True)
