"""Conservative, deterministic evidence checks; never resolve ambiguity by confidence alone."""
import re

ALIASES = {'Chair': ('Chair', 'chair', '의자'), 'Sofa': ('Sofa', 'sofa', '소파'),
           'Table': ('Table', 'table', '테이블', '탁자', '식탁')}
NUMBERS = {'한': 1, '하나': 1, '두': 2, '둘': 2, '세': 3, '셋': 3, '네': 4, '넷': 4}


def iou(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    union = max(0, a[2]-a[0])*max(0, a[3]-a[1]) + max(0, b[2]-b[0])*max(0, b[3]-b[1]) - intersection
    return intersection/union if union else 0


def analyze_detections(objects):
    overlaps = []
    uncertain = set()
    for i, first in enumerate(objects):
        for j in range(i+1, len(objects)):
            second = objects[j]
            overlap = iou(first['box'], second['box'])
            if first['label'] != second['label'] and overlap >= 0.8:
                uncertain.update((i, j))
                overlaps.append({'indices': [i, j], 'labels': [first['label'], second['label']],
                                 'iou': round(overlap, 4)})
    counts = {}
    for i, obj in enumerate(objects):
        if i not in uncertain:
            counts[obj['label']] = counts.get(obj['label'], 0)+1
    summary = ', '.join(f'{key} {value}개' for key, value in counts.items())
    if overlaps:
        candidates = '/'.join(sorted({objects[i]['label'] for i in uncertain}))
        summary = (summary + '; ' if summary else '') + f'중복 후보: {candidates} (종류·개수 미확정)'
    return {'summary': summary or '인식된 객체 없음', 'certain_counts': counts,
            'ambiguous_indices': sorted(uncertain), 'cross_class_overlaps': overlaps,
            'policy': 'Different labels with IoU >= 0.8 are ambiguous; raw detections retained, no class chosen.'}


def reconcile(yolo, vlm):
    issues = []
    if '중복 후보:' in yolo:
        issues.append({'type': 'overlapping_classes', 'message': '같은 영역의 서로 다른 클래스 후보는 합산하지 않으며 종류·개수를 확정하지 않습니다.'})
    counts = {}
    explicit_vlm = {}
    for label, aliases in ALIASES.items():
        word = '(?:' + '|'.join(map(re.escape, aliases)) + ')'
        # Only explicitly numbered statements count. Unmentioned classes are unknown, never zero.
        ym = re.search(word + r'\s+(\d+)개', yolo, re.I)
        if ym:
            counts[label] = int(ym.group(1))
        vm = re.search(word + r'\s*(\d+|하나|한|두|둘|세|셋|네|넷)\s*(?:개|대|장)?(?:가|이|는|를|\s|[,.]|$)', vlm, re.I)
        if vm:
            value = vm.group(1)
            explicit_vlm[label] = int(value) if value.isdigit() else NUMBERS[value]
            if label in counts and counts[label] != explicit_vlm[label]:
                issues.append({'type': 'count_mismatch', 'label': label,
                               'yolo_count': counts[label], 'vlm_count': explicit_vlm[label]})
    return {'issues': issues, 'has_conflict': bool(issues), 'yolo_counts': counts,
            'vlm_explicit_counts': explicit_vlm,
            'count_policy': 'YOLO for unambiguous counts; VLM missing counts remain unknown.'}


def grounded_description(yolo, vlm, evidence):
    text = f'[YOLO] {yolo or "정보 없음"}. [VLM] {vlm or "정보 없음"}'
    if evidence['has_conflict']:
        text += ' [인식 불일치] '
        if any(x['type'] == 'overlapping_classes' for x in evidence['issues']):
            text += '겹치는 후보는 별개 물체로 합산하지 않았으며 종류·개수는 미확정입니다. '
        if any(x['type'] == 'count_mismatch' for x in evidence['issues']):
            text += '명시된 개수가 서로 다릅니다. 개수는 YOLO 기준이며 VLM 설명은 참고 정보입니다. '
        text += '이미지를 다시 확인해 주세요.'
    return text
