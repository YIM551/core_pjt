# -*- coding: utf-8 -*-
"""[도전 문제 2 ― 정답] 랜드마크로 펼친 손가락 개수(0~5)를 세는 count_fingers().

    ① 입력은 result.hand_landmarks[0] (21점)
    ② victory.jpg 는 2, pointing_up.jpg 는 1
    ③ 손을 90° 돌려도 같은 값이 나와야 한다
    ④ 3일차 대시보드의 '손가락 = 칸 수' 입력과 같은 원리

문제 파일(제스처_인식_도전2.py)과 count_fingers() 만 다르다.

실행:
    python 제스처_인식_도전2_정답.py
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day2 (공용 자료)
PROJECT_ROOT = DAY_DIR.parents[1]
GESTURE_MODEL_PATH = PROJECT_ROOT / "models" / "gesture_recognizer.task"


TIPS = [8, 12, 16, 20]      # 검지 ~ 새끼 끝
PIPS = [6, 10, 14, 18]      # 검지 ~ 새끼 중간 관절


def dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def count_fingers(landmarks) -> int:
    wrist = landmarks[0]
    # 네 손가락 : 끝이 중간 관절보다 손목에서 멀면 펴진 것
    count = sum(dist(landmarks[t], wrist) > dist(landmarks[p], wrist)
                for t, p in zip(TIPS, PIPS))
    # 엄지 : 옆으로 펴지므로 새끼 뿌리(17)에서 멀어지는지로 본다
    pinky_mcp = landmarks[17]
    if dist(landmarks[4], pinky_mcp) > dist(landmarks[3], pinky_mcp):
        count += 1
    return count


# ---------------------------------------------------------------------------
# 채점 (고치지 않는다)
# ---------------------------------------------------------------------------
CASES = [("pointing_up.jpg", 1), ("victory.jpg", 2)]
ANGLES = [0, 90]


def load_recognizer():
    if not GESTURE_MODEL_PATH.exists():
        raise SystemExit(f"제스처 모델 파일이 없습니다: {GESTURE_MODEL_PATH}")

    from mediapipe.tasks import python as mp_tasks
    from mediapipe.tasks.python import vision

    options = vision.GestureRecognizerOptions(
        # 경로 대신 바이트로 넘긴다 (한글 경로 문제 회피)
        base_options=mp_tasks.BaseOptions(
            model_asset_buffer=GESTURE_MODEL_PATH.read_bytes()),
        running_mode=vision.RunningMode.IMAGE,
        num_hands=1,
    )
    return vision.GestureRecognizer.create_from_options(options)


def to_mp_image(image: Image.Image):
    import mediapipe as mp

    return mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(image))


def main() -> None:
    recognizer = load_recognizer()
    print("[도전 2] count_fingers() 채점 (0° 와 90° 로 돌려 비교)")
    passed = total = 0
    for name, expected in CASES:
        image = Image.open(DAY_DIR / "samples" / name).convert("RGB")
        for angle in ANGLES:
            rotated = image.rotate(angle, expand=True)
            result = recognizer.recognize(to_mp_image(rotated))
            total += 1
            if not result.hand_landmarks:
                print(f"  X  {name:<16} {angle:>3}° → 손을 찾지 못함")
                continue
            got = count_fingers(result.hand_landmarks[0])
            gesture = result.gestures[0][0].category_name if result.gestures else None
            ok = got == expected
            passed += ok
            print(f"  {'O' if ok else 'X'}  {name:<16} {angle:>3}° → 펼친 손가락 {got}개"
                  f"  (기대 {expected}개, gesture: {gesture or 'None'})")
    print(f"\n  {passed}/{total} 통과")


if __name__ == "__main__":
    main()
