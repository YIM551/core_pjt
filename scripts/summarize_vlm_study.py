import csv
import json
from pathlib import Path
import statistics

root=Path(__file__).resolve().parents[1]
out=root/'results/vlm_settings_20261022'
phases={name:json.loads((out/(name+'.json')).read_text(encoding='utf-8'))
        for name in ['screen','refine','confirm','confirm40']}
rows=[]
for phase,data in phases.items():
    for row in data['rows']:
        rows.append({'phase':phase,'label':row['label'],'side':row['side'],'max_tokens':row['max_tokens'],
            'seconds':row['seconds'],'description':row['description'],'format_pass':row['format_pass'],
            'retry_count':row['retry_count'],
            'completion_tokens':sum(c.get('usage',{}).get('completion_tokens',0) for c in row['calls']),
            'finish_reasons':'/'.join(str(c['finish_reason']) for c in row['calls'])})
with (out/'measurements.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
policy=json.loads((out/'policy_validation.json').read_text(encoding='utf-8'))
pairs=[]
for sample in range(6):
    b=next(r for r in policy['rows'] if r['sample']==sample and r['mode']=='baseline')
    a=next(r for r in policy['rows'] if r['sample']==sample and r['mode']=='adaptive')
    pairs.append({'sample':sample,'label':a['label'],'input_sha256':a['input_sha256'],
        'side':a['side'],'before_seconds':b['seconds'],'after_seconds':a['seconds'],
        'before_description':b['description'],'after_description':a['description'],
        'same_input':a['input_sha256']==b['input_sha256'],
        'format_pass':a['format_pass'] and b['format_pass'],
        'table_baseline_preserved':a['label']!='Table' or (a['side']==448 and a['description']==b['description'])})
b=statistics.mean(p['before_seconds'] for p in pairs)
a=statistics.mean(p['after_seconds'] for p in pairs)
review={
    'method':'Visual inspection of all six source images and paired output text; class keywords/format are only screening proxies, not factual ground truth.',
    'rejected_settings':[
        {'side':224,'reason':'Chair invents bathroom context; Table renders cloth as an unsupported object/word.'},
        {'side':336,'reason':'Chair and Sofa invent bathroom context.'},
        {'side':392,'reason':'Sofa introduces a separate pillow claim unsupported by the visible image.'},
        {'side':420,'scope':'all-image fixed profile','reason':'Additional desk image retries and becomes slower; do not apply indiscriminately.'}],
    'selected_policy':'420px only for all high-confidence (>=0.8) Chair/Sofa/couch detections; otherwise448px. 60tokens retained.',
    'quality_limits':['Baseline additional desk contains the unclear word 쇼트; conservative policy preserves rather than fixes this pre-existing error.',
        'Obstacle statements are model quotes, not physical safety labels.',
        'Only six valid images and few repetitions; no test data used and no general quality guarantee.'],
    'token_finding':'40 token cap does not help normal short EOS outputs, and still requires a second generation for the desk; retain60 for headroom.'}
result={'quality_review':review,'pairs':pairs,'mean_before_seconds':b,'mean_after_seconds':a,
    'mean_reduction_percent':100*(b-a)/b,
    'all_pair_checks':all(p['same_input'] and p['format_pass'] and p['table_baseline_preserved'] for p in pairs),
    'phase_trial_counts':{k:len(v['rows']) for k,v in phases.items()},'policy_trials':len(policy['rows'])}
(out/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['mean_before_seconds','mean_after_seconds','mean_reduction_percent','all_pair_checks','phase_trial_counts','policy_trials']}))
if not result['all_pair_checks']:raise SystemExit('Paired verification failed')
