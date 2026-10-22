"""Verify the real saved dashboard experiment and preserve its before/after comparison."""
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
out=root/'results/f206_20261022'
before=json.loads((out/'before.json').read_text(encoding='utf-8'))
after=json.loads((out/'after/validation.json').read_text(encoding='utf-8'))
b=next(c for c in before['cases'] if c['label']=='Table')
a=next(c for c in after['cases'] if c['label']=='Table')
def exchange(case, endpoint):
    return next(x for x in case['exchanges'] if x['endpoint']==endpoint)
by=exchange(b,'/api/yolo-detect'); ay=exchange(a,'/api/yolo-detect')
bv=exchange(b,'/api/vlm-describe'); av=exchange(a,'/api/vlm-describe')
bl=exchange(b,'/api/llm-answer'); al=exchange(a,'/api/llm-answer')
checks={
    'same_weights':before['weights_sha256']==after['weights_sha256'],
    'same_input_bytes':by['input_sha256']==ay['input_sha256'],
    'same_raw_yolo_detections':by['response']['objects']==ay['response']['objects'],
    'same_vlm_description':bv['response']==av['response'],
    'overlap_marked':bool(ay['response']['analysis']['cross_class_overlaps']),
    'no_certain_counts_for_ambiguous_region':ay['response']['analysis']['certain_counts']=={},
    'conflict_reported':al['response']['consistency']['has_conflict'],
    'source_citations_enforced':all(s in al['response']['message'] for s in ['[YOLO]','[VLM]']),
    'uncertainty_explicit':'미확정' in al['response']['message'],
    'no_false_sofa_count':'Sofa 1개' not in al['response']['message'] and '소파 1개' not in al['response']['message'],
    'integration_passed':all(a['checks'].values()),
}
report={'checks':checks, 'before_message':bl['response']['message'], 'after_message':al['response']['message'],
    'before_summary':bl['request']['yolo_summary'], 'after_summary':al['request']['yolo_summary'],
    'overlaps':ay['response']['analysis']['cross_class_overlaps'],
    'input_sha256':ay['input_sha256'],'weights_sha256':after['weights_sha256'],
    'scope':'Ambiguity reporting improves; raw model accuracy is unchanged. VLM non-mention is unknown, not zero.'}
(out/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'checks':checks,'passed':sum(checks.values()),'total':len(checks)}))
if not all(checks.values()):
    raise SystemExit('Comparison checks failed; inspect comparison.json')
