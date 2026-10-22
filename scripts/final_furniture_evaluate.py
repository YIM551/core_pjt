"""Frozen best.pt final test evaluation, with same-evaluator valid reproducibility check."""
import csv
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
import numpy as np
from PIL import Image,ImageDraw
from spec1_evaluate import evaluate,match,NAMES

root=Path(__file__).resolve().parents[1]
data=root/'datasets/roboflow/furniture/v2_curated_v2'
weights=root/'source/2회차_day1/runs/furniture_spec1_20261022/weights/best.pt'
out=root/'results/furniture_final_test_20261022'
if out.exists():raise SystemExit('Final evaluation directory exists; preserve the recorded test evaluation.')
out.mkdir()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((data/'split_manifest.json').read_text(encoding='utf-8'))
frozen={str(weights):digest(weights),str(data/'split_manifest.json'):digest(data/'split_manifest.json')}
groups={s:{r['group_id'] for r in manifest if r['derived_split']==s} for s in ['train','valid','test']}
images={s:{r['image_sha256'] for r in manifest if r['derived_split']==s} for s in groups}
for i,s in enumerate(groups):
    for t in list(groups)[i+1:]:
        if groups[s]&groups[t] or images[s]&images[t]:raise RuntimeError('Split leakage')
for r in manifest:
    for key in ['image','label']:
        p=data/r[key]
        if digest(p)!=r[key+'_sha256']:raise RuntimeError('Frozen input changed: '+str(p))
if sum(r['derived_split']=='test' for r in manifest)!=87:raise RuntimeError('Unexpected test size')
lock={'started_utc':datetime.now(timezone.utc).isoformat(),'weights_sha256':digest(weights),
      'manifest_sha256':digest(data/'split_manifest.json'),'policy':'Final test reporting only; no training or threshold/model selection from test results.',
      'all_565_image_label_hashes_verified':True,'cross_split_group_and_exact_image_overlap':False,
      'imgsz':320,'conf_for_AP':.001,'nms_iou':.7,'operating_conf':.25,'matching_iou':.5}
(out/'evaluation_lock.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf-8')
valid=evaluate(weights,data,'valid_reproduced',out,'valid')
previous=json.loads((root/'results/spec_workflow_20261022/spec1/after_finetune_metrics.json').read_text(encoding='utf-8'))
keys=['map50','map50_95','precision_at_conf025','recall_at_conf025']
if not all(abs(valid[k]-previous[k])<1e-8 for k in keys):raise RuntimeError('Valid metrics differ; resolve evaluator reproducibility before test.')
test=evaluate(weights,data,'test_final',out,'test')
for p,sha in frozen.items():
    if digest(Path(p))!=sha:raise RuntimeError('Frozen artifact changed during evaluation')
comparison={'valid_reproduces_previous':True,'test_used_for_tuning':False,
    'valid':valid,'test':test,'test_minus_valid_percentage_points':{k:100*(test[k]-valid[k]) for k in keys}}
predictions=json.loads((out/'test_final_predictions.json').read_text(encoding='utf-8'))
errors=[]
for row in predictions:
    image=Image.open(data/row['image']); w,h=image.size
    labels=row['ground_truth']; gc=np.array([int(x[0]) for x in labels]);
    gt=np.array([[(v[1]-v[3]/2)*w,(v[2]-v[4]/2)*h,(v[1]+v[3]/2)*w,(v[2]+v[4]/2)*h] for v in labels])
    kept=np.array(row['confidence'])>=.25
    boxes=np.array(row['boxes_xyxy']).reshape(-1,4)[kept]
    pc=np.array(row['mapped_class_ids'])[kept]
    correct=match(boxes,pc,gt,gc,[.5])[:,0]
    fp=int(len(boxes)-sum(correct)); fn=int(len(gt)-sum(correct))
    if fp or fn:
        errors.append({'id':row['id'],'image':row['image'],'fp':fp,'fn':fn,
            'ground_truth_classes':[NAMES[int(c)] for c in gc],
            'predictions':[{'class':NAMES[int(c)],'confidence':float(conf),'box':box.tolist(),'matched':bool(ok)}
                for c,conf,box,ok in zip(pc,np.array(row['confidence'])[kept],boxes,correct)]})
comparison['test_images_with_operating_point_errors']=len(errors)
comparison['test_images_without_operating_point_errors']=87-len(errors)
(out/'comparison.json').write_text(json.dumps(comparison,indent=2)+'\n',encoding='utf-8')
(out/'test_errors.json').write_text(json.dumps(errors,indent=2)+'\n',encoding='utf-8')
with (out/'valid_vs_test.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=['split','images',*keys]);writer.writeheader()
    for r in [valid,test]:writer.writerow({k:r[k] for k in writer.fieldnames})
chosen=sorted(errors,key=lambda x:(-x['fp']-x['fn'],x['id']))[:9]
if chosen:
    sheet=Image.new('RGB',(1200,440*((len(chosen)+2)//3)),'white')
    for n,error in enumerate(chosen):
        image=Image.open(data/error['image']).convert('RGB');w,h=image.size
        image.thumbnail((390,390));sx=image.width/w;sy=image.height/h
        draw=ImageDraw.Draw(image)
        original=next(p for p in predictions if p['id']==error['id'])
        for v in original['ground_truth']:
            draw.rectangle([(v[1]-v[3]/2)*w*sx,(v[2]-v[4]/2)*h*sy,(v[1]+v[3]/2)*w*sx,(v[2]+v[4]/2)*h*sy],outline='lime',width=3)
        for p in error['predictions']:
            box=p['box'];draw.rectangle([box[0]*sx,box[1]*sy,box[2]*sx,box[3]*sy],outline='blue' if p['matched'] else 'red',width=2)
            draw.text((box[0]*sx,max(0,box[1]*sy-12)),p['class']+f" {p['confidence']:.2f}",fill='red')
        x,y=(n%3)*400,(n//3)*440
        sheet.paste(image,(x,y+35));ImageDraw.Draw(sheet).text((x+5,y+5),f"{error['id']} FP={error['fp']} FN={error['fn']} GT={','.join(error['ground_truth_classes'])}",fill='black')
    sheet.save(out/'test_error_examples.jpg')
print(json.dumps({'valid':{k:valid[k] for k in keys},'test':{k:test[k] for k in keys},
    'test_per_class':test['per_class'],'error_images':len(errors),'valid_reproduced':True}),flush=True)
