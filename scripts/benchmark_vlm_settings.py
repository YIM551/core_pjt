"""Uncached real VLM factorial experiment, keeping prompt/format/retry policy fixed."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import sys
import time
from PIL import Image
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import main
p=argparse.ArgumentParser()
p.add_argument('--phase',choices=['screen','refine','confirm'],default='screen')
p.add_argument('--side',type=int)
p.add_argument('--tokens',type=int)
p.add_argument('--candidate-only',action='store_true')
p.add_argument('--report-name')
args=p.parse_args()
out=root/'results/vlm_settings_20261022'
out.mkdir(exist_ok=True)

class RecordingModel:
    def __init__(self,model):self.model=model; self.calls=[]
    def create_chat_completion(self,**kwargs):
        start=time.perf_counter()
        response=self.model.create_chat_completion(**kwargs)
        self.calls.append({'seconds':time.perf_counter()-start,'usage':response.get('usage'),
            'finish_reason':response['choices'][0].get('finish_reason'),
            'raw_text':response['choices'][0]['message']['content']})
        return response

model=main._load_vlm()
recorder=RecordingModel(model)
main._models['vlm']=recorder
samples=[]
if args.phase in ('screen','refine'):
    for label,word in [('Sofa','소파'),('Chair','의자'),('Table','테이블')]:
        samples.append({'label':label,'expected_words':[word] if label!='Table' else ['테이블','탁자','식탁'],
            'path':f'results/furniture_dashboard_20261022/{label}-dashboard-input.jpg'})
    configs=[(side,tokens) for side in ([448,336,224] if args.phase=='screen' else [392,420]) for tokens in [60,40]]
else:
    if not args.side or not args.tokens:raise SystemExit('Candidate required')
    manifest=json.loads((root/'datasets/roboflow/furniture/v2_curated_v2/split_manifest.json').read_text(encoding='utf-8'))
    for class_id,label,words in [(0,'Chair',['의자']),(1,'Sofa',['소파']),(2,'Table',['테이블','탁자','식탁','책상'])]:
        selected=[s for s in manifest if s['derived_split']=='valid' and s['class_id']==class_id][1]
        samples.append({'label':label,'expected_words':words,
            'path':'datasets/roboflow/furniture/v2_curated_v2/'+selected['image']})
    configs=[(args.side,args.tokens)] if args.candidate_only else [(448,60),(args.side,args.tokens)]
# Initialize inference separately; this warmup is excluded and not a measured image.
warm=Image.new('RGB',(224,224),'gray')
try:main.describe_scene(warm)
except ValueError:pass
rows=[]
trials=[(sample,side,tokens,repeat) for repeat in range(2 if args.phase=='confirm' else 1)
        for sample in samples for side,tokens in configs]
random.Random(206).shuffle(trials)
report={'phase':args.phase,'cache':'describe_scene called directly; model.reset before every trial; app result cache bypassed',
    'prompt':main.VLM_PROMPT,'temperature':0,'samples':samples,'rows':rows}
for sample,side,tokens,repeat in trials:
    main.VLM_MAX_SIDE=side; main.VLM_MAX_TOKENS=tokens
    image=Image.open(root/sample['path']).convert('RGB')
    model.reset()
    recorder.calls=[]
    start=time.perf_counter(); error=None; description=None
    try:description=main.describe_scene(image)
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    elapsed=time.perf_counter()-start
    row={'label':sample['label'],'path':sample['path'],'input_sha256':hashlib.sha256((root/sample['path']).read_bytes()).hexdigest(),
        'side':side,'max_tokens':tokens,'repeat':repeat,'seconds':elapsed,'description':description,
        'error':error,'calls':recorder.calls,'retry_count':max(0,len(recorder.calls)-1),
        'format_pass':bool(description) and all(ok for _,ok in main.check(description)),
        'target_mentioned':bool(description) and any(w in description for w in sample['expected_words'])}
    rows.append(row)
    report['summary']=[]
    for s,t in configs:
        group=[r for r in rows if r['side']==s and r['max_tokens']==t]
        if group:report['summary'].append({'side':s,'max_tokens':t,'trials':len(group),
            'median_seconds':statistics.median(r['seconds'] for r in group),
            'format_pass':sum(r['format_pass'] for r in group),
            'target_mentioned':sum(r['target_mentioned'] for r in group),
            'retries':sum(r['retry_count'] for r in group)})
    (out/((args.report_name or args.phase)+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:row[k] for k in ['label','side','max_tokens','seconds','description','format_pass','target_mentioned','retry_count']}),flush=True)
print(json.dumps(report['summary']),flush=True)
