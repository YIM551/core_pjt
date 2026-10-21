# -*- coding: utf-8 -*-
"""[도전 문제 1 ― 정답] summarize() 를 아래 규칙에 맞게 고친 것.

    ① conf 0.5 미만 검출은 버린다
    ② 출력 형식을 한 줄로 고정한다 : 총 5개 (person 4개, bus 1개)
    ③ 개수가 많은 순, 개수가 같으면 이름 순 : car 2개, person 2개
    ④ NOT_OBSTACLE 에 든 소지품(tie 등)은 장애물이 아니므로 빼고 센다

문제 파일(YOLO결과_텍스트요약_도전1.py)과 summarize() 만 다르다.

실행:
    python YOLO결과_텍스트요약_도전1_정답.py
"""
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day2 (공용 자료)
SAMPLES_DIR = DAY_DIR / "samples"
YOLO_MODEL_PATH = DAY_DIR.parents[1] / "yolo11n.pt"

NO_OBJECT_TEXT = "인식된 객체 없음"
NOT_OBSTACLE = {"tie", "handbag", "backpack", "umbrella", "cell phone"}   # 장애물이 아닌 소지품


def summarize(model, results, min_conf: float = 0.5) -> str:
    counter = Counter(
        model.names[int(box.cls)]
        for box in results[0].boxes
        if float(box.conf) >= min_conf                      # ① 0.5 미만은 버린다
        and model.names[int(box.cls)] not in NOT_OBSTACLE   # ④ 소지품 제외
    )
    if not counter:
        return NO_OBJECT_TEXT
    # ③ 많은 순, 개수가 같으면 이름 순
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    text = ", ".join(f"{name} {count}개" for name, count in items)
    return f"총 {sum(counter.values())}개 ({text})"          # ② 형식 고정


# ---------------------------------------------------------------------------
# 채점 (고치지 않는다)
# ---------------------------------------------------------------------------
IMAGE_CASES = [
    ("sample.jpg", "총 5개 (person 4개, bus 1개)"),
    ("pointing_up.jpg", "총 1개 (person 1개)"),      # tie 는 conf 0.30 ― ① 에서 빠진다
    ("victory.jpg", NO_OBJECT_TEXT),                  # person 이 conf 0.34 ― 남는 것이 없다
]

# 샘플 사진에는 동률 · 높은 conf 의 소지품이 없어 가상 검출로 ③ ④ 를 확인한다
FAKE_NAMES = {0: "person", 1: "car", 2: "bus", 3: "tie", 4: "dog"}
FAKE_BOXES = [(0, 0.90), (1, 0.80), (0, 0.85), (1, 0.70), (2, 0.60), (3, 0.90), (4, 0.30)]
FAKE_EXPECTED = "총 5개 (car 2개, person 2개, bus 1개)"


def fake_detection():
    model = SimpleNamespace(names=FAKE_NAMES)
    boxes = [SimpleNamespace(cls=cls, conf=conf) for cls, conf in FAKE_BOXES]
    return model, [SimpleNamespace(boxes=boxes)]


def check(label: str, got: str, expected: str) -> bool:
    ok = got == expected
    print(f"  {'O' if ok else 'X'}  {label:<24} → {got}")
    if not ok:
        print(f"     {'':<24}   기대 : {expected}")
    return ok


def main() -> None:
    if not YOLO_MODEL_PATH.exists():
        raise SystemExit(f"YOLO 가중치가 없습니다: {YOLO_MODEL_PATH}")

    from ultralytics import YOLO

    model = YOLO(str(YOLO_MODEL_PATH))
    print("[도전 1] summarize() 채점 (conf 0.25 로 검출한 뒤 요약)")
    passed = 0
    for name, expected in IMAGE_CASES:
        image = Image.open(SAMPLES_DIR / name).convert("RGB")
        results = model.predict(image, conf=0.25, verbose=False)
        passed += check(name, summarize(model, results), expected)

    fake_model, fake_results = fake_detection()
    passed += check("가상 검출 (동률 · tie 0.90)",
                    summarize(fake_model, fake_results), FAKE_EXPECTED)

    total = len(IMAGE_CASES) + 1
    print(f"\n  {passed}/{total} 통과")


if __name__ == "__main__":
    main()
