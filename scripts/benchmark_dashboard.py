"""Live, same-frame pipeline benchmark; sequential trials, concurrent YOLO/VLM."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import statistics
import time
import httpx

root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--phase',required=True)
p.add_argument('--runs',type=int,default=3)
p.add_argument('--url',default='http://127.0.0.1:8003')
p.add_argument('--warmup-models',action='store_true')
args=p.parse_args()
image=root/'results/furniture_dashboard_20261022/Table-dashboard-input.jpg'
data=image.read_bytes()
out=root/'results/optimization_20261022'
out.mkdir(exist_ok=True)
report={'phase':args.phase,'image_sha256':hashlib.sha256(data).hexdigest(),'runs':[]}
with httpx.Client(base_url=args.url,timeout=240) as client:
    def post(endpoint,**kwargs):
        t=time.perf_counter()
        r=client.post(endpoint,**kwargs)
        r.raise_for_status()
        return r.json(),time.perf_counter()-t
    if args.warmup_models:
        # Different frame loads the models without caching the measured table frame.
        warmup=(root/'results/furniture_dashboard_20261022/Sofa-dashboard-input.jpg').read_bytes()
        with ThreadPoolExecutor(2) as pool:
            futures=[pool.submit(post,endpoint,content=warmup,headers={'Content-Type':'image/jpeg'}) for endpoint in ['/api/yolo-detect','/api/vlm-describe']]
            for future in futures:future.result()
    for i in range(args.runs):
        t=time.perf_counter()
        with ThreadPoolExecutor(2) as pool:
            yf=pool.submit(post,'/api/yolo-detect',content=data,headers={'Content-Type':'image/jpeg'})
            vf=pool.submit(post,'/api/vlm-describe',content=data,headers={'Content-Type':'image/jpeg'})
            y,yt=yf.result(); v,vt=vf.result()
        summary=y['analysis']['summary']
        body={'prompt':'어떤 가구가 몇 개 보여? YOLO 개수와 VLM 장면 설명을 참고해서 한국어로 알려줘.',
              'yolo_summary':summary,'vlm_description':v['description'],'gesture_direction':'none','history':[]}
        l,lt=post('/api/llm-answer',json=body)
        row={'run':i+1,'yolo_seconds':yt,'vlm_seconds':vt,'llm_seconds':lt,'total_seconds':time.perf_counter()-t,
             'yolo':y,'vlm':v,'answer':l}
        report['runs'].append(row)
        (out/(args.phase+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:row[k] for k in ['run','yolo_seconds','vlm_seconds','llm_seconds','total_seconds']}),flush=True)
report['median_seconds']={key:statistics.median(r[key] for r in report['runs']) for key in ['yolo_seconds','vlm_seconds','llm_seconds','total_seconds']}
(out/(args.phase+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report['median_seconds']),flush=True)
