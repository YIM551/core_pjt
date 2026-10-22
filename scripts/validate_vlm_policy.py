"""Paired fresh-inference validation of the chosen conservative adaptive policy."""
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
out=root/'results/vlm_settings_20261022'
main.YOLO_MODEL_PATH=root/'source/2회차_day1/runs/furniture_spec1_20261022/weights/best.pt'
main.VLM_MAX_SIDE=420; main.VLM_DETAIL_SIDE=448; main.VLM_MAX_TOKENS=60
main.VLM_ADAPTIVE=True; main._vlm_result_cache.capacity=0
screen=json.loads((out/'screen.json').read_text(encoding='utf-8'))
confirm=json.loads((out/'confirm.json').read_text(encoding='utf-8'))
samples=screen['samples']+confirm['samples']
model=main._get('vlm',main._load_vlm)
try:main.describe_scene(Image.new('RGB',(224,224),'gray'),max_side=448)
except ValueError:pass
main.detect_objects(Image.open(root/samples[0]['path']).convert('RGB'))
trials=[(i,mode) for i in range(6) for mode in ['baseline','adaptive']]
random.Random(420).shuffle(trials)
rows=[]
for i,mode in trials:
    sample=samples[i]; image=Image.open(root/sample['path']).convert('RGB')
    model.reset(); start=time.perf_counter(); error=None; description=None; side=448
    try:
        if mode=='baseline':description=main.describe_scene(image,max_side=448)
        else:description,hit,side=main.describe_scene_cached(image)
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    row={'sample':i,'label':sample['label'],'path':sample['path'],'mode':mode,'side':side,
        'max_tokens':60,'seconds':time.perf_counter()-start,'description':description,'error':error,
        'format_pass':bool(description) and all(ok for _,ok in main.check(description)),
        'input_sha256':hashlib.sha256((root/sample['path']).read_bytes()).hexdigest()}
    rows.append(row)
    report={'cache':'disabled for every trial; model.reset before every trial; model warmup excluded',
        'weights':str(main.YOLO_MODEL_PATH.relative_to(root)), 'samples':samples,'rows':rows,
        'summary':{mode:{'n':len(group),'mean_seconds':statistics.mean(r['seconds'] for r in group),
             'median_seconds':statistics.median(r['seconds'] for r in group)}
             for mode in ['baseline','adaptive'] if (group:=[r for r in rows if r['mode']==mode])}}
    (out/'policy_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(row),flush=True)
if not all(r['format_pass'] for r in rows):raise SystemExit('Policy format failure')
