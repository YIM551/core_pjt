"""Read-only localization diagnostics from frozen final predictions; never re-infer or tune."""
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from spec1_evaluate import match,NAMES
from ultralytics.utils.metrics import box_iou
import torch
root=Path(__file__).resolve().parents[1]
out=root/'results/furniture_final_test_20261022'
data=root/'datasets/roboflow/furniture/v2_curated_v2'
rows=json.loads((out/'test_final_predictions.json').read_text(encoding='utf-8'))
stats={str(t):{'tp':0,'fp':0,'fn':0} for t in [.5,.75,.9,.95]}
localized=[]
for r in rows:
    with Image.open(data/r['image']) as im:w,h=im.size
    gt=np.array([[(v[1]-v[3]/2)*w,(v[2]-v[4]/2)*h,(v[1]+v[3]/2)*w,(v[2]+v[4]/2)*h] for v in r['ground_truth']])
    gc=np.array([int(v[0]) for v in r['ground_truth']])
    keep=np.array(r['confidence'])>=.25
    boxes=np.array(r['boxes_xyxy']).reshape(-1,4)[keep];pc=np.array(r['mapped_class_ids'])[keep]
    for t in stats:
        correct=match(boxes,pc,gt,gc,[float(t)])[:,0]
        stats[t]['tp']+=int(correct.sum());stats[t]['fp']+=len(boxes)-int(correct.sum());stats[t]['fn']+=len(gt)-int(correct.sum())
    matrix=box_iou(torch.tensor(gt,dtype=torch.float32),torch.tensor(boxes,dtype=torch.float32)).numpy()
    for i,c in enumerate(gc):
        candidates=np.where(pc==c)[0]
        best=max(candidates,key=lambda j:matrix[i,j])
        localized.append({'id':r['id'],'image':r['image'],'class':NAMES[int(c)],'iou':float(matrix[i,best]),
                          'ground_truth_box':gt[i].tolist(),'prediction_box':boxes[best].tolist()})
chosen=[min((r for r in localized if r['class']==name),key=lambda r:r['iou']) for name in NAMES.values()]
sheet=Image.new('RGB',(1200,440),'white')
for n,r in enumerate(chosen):
    im=Image.open(data/r['image']).convert('RGB');w,h=im.size;im.thumbnail((390,390));sx=im.width/w;sy=im.height/h
    draw=ImageDraw.Draw(im)
    for key,color in [('ground_truth_box','lime'),('prediction_box','red')]:
        b=r[key];draw.rectangle([b[0]*sx,b[1]*sy,b[2]*sx,b[3]*sy],outline=color,width=3)
    sheet.paste(im,(n*400,35));ImageDraw.Draw(sheet).text((n*400+5,5),f"{r['class']} {r['id']} IoU={r['iou']:.3f}",fill='black')
sheet.save(out/'localization_examples.jpg')
report={'operating_conf':.25,'iou_threshold_counts':stats,'lowest_iou_per_class':chosen,
        'legend':'Green = supplied ground truth, red = model prediction; examples chosen by lowest IoU per class.'}
(out/'localization_analysis.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
