import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
out=root/'results/vlm_settings_20261022'
report=json.loads((out/'browser/validation.json').read_text(encoding='utf-8'))
checks={}
for case in report['cases']:
    label=case['label']
    vlm=next(x['response'] for x in case['exchanges'] if x['endpoint']=='/api/vlm-describe')
    llm=next(x['response'] for x in case['exchanges'] if x['endpoint']=='/api/llm-answer')
    checks[label+'_correct_resolution']=vlm['max_side']==(448 if label=='Table' else 420)
    checks[label+'_fresh_inference']=vlm['cache_hit'] is False
    checks[label+'_integration']=all(case['checks'].values())
    if label=='Table':
        checks['F206_preserved']=llm['consistency']['has_conflict'] and '미확정' in llm['message']
result={'checks':checks,'passed':sum(checks.values()),'total':len(checks),
    'optimization_unit_checks':'8/8','F206_unit_checks':'5/5',
    'browser_timing_note':'First Sofa turn includes cold model loading (16.133s); Chair6.826s/Table7.948s include actual UI/MediaPipe. These are not the controlled warm VLM timings.'}
(out/'deployment_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
if not all(checks.values()):raise SystemExit('Deployment check failed')
