import json
from pathlib import Path
import statistics

root=Path(__file__).resolve().parents[1]
out=root/'results/optimization_20261022'
before=json.loads((out/'before.json').read_text(encoding='utf-8'))
uncached=json.loads((out/'after_uncached.json').read_text(encoding='utf-8'))
cached=json.loads((out/'after_cached.json').read_text(encoding='utf-8'))
browser=json.loads((out/'browser/validation.json').read_text(encoding='utf-8'))
reference=before['runs'][0]
checks={}
for phase,data in [('uncached',uncached),('cached',cached)]:
    checks[phase+'_same_image']=data['image_sha256']==before['image_sha256']
    checks[phase+'_same_raw_detections']=all(r['yolo']['objects']==reference['yolo']['objects'] for r in data['runs'])
    checks[phase+'_same_vlm_description']=all(r['vlm']['description']==reference['vlm']['description'] for r in data['runs'])
    checks[phase+'_same_final_message']=all(r['answer']['message']==reference['answer']['message'] for r in data['runs'])
checks['uncached_not_using_cache']=all(not r['vlm']['cache_hit'] for r in uncached['runs'])
checks['cache_miss_then_hits']=[r['vlm']['cache_hit'] for r in cached['runs']]==[False,True,True]
checks['simple_scene_skips_llm']=all(r['answer']['inference_path']=='scene_evidence' for r in uncached['runs']+cached['runs'])
checks['browser_passed']=all(all(c['checks'].values()) for c in browser['cases'])
b=before['median_seconds']['total_seconds']; a=uncached['median_seconds']['total_seconds']
result={'checks':checks,'baseline_warm_api_median_seconds':b,'optimized_uncached_warm_api_median_seconds':a,
    'uncached_reduction_percent':100*(b-a)/b,
    'repeat_cache_hit_api_seconds':[r['total_seconds'] for r in cached['runs'] if r['vlm']['cache_hit']],
    'browser_first_turn_seconds':browser['cases'][0]['seconds'],
    'scope':'Three local warm-model API trials, one table image. Cache-hit results are repeat-input reuse, not faster fresh-frame VLM inference. Browser timing includes MediaPipe and UI; do not compare it directly with API timings.'}
(out/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
if not all(checks.values()):raise SystemExit('Optimization comparison failed')
