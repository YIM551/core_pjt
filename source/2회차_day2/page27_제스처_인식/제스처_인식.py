# -*- coding: utf-8 -*-
"""[page 27] 실습 2-1 ― MediaPipe GestureRecognizer 로 손 제스처 인식.

이미지 1장 → 손 1개당 세 가지가 나온다.
  - gesture    : 기본 카테고리 7종 중 하나 + 점수
  - handedness : 왼손 / 오른손
  - landmarks  : 손 관절 21점의 정규화 좌표 (x, y 는 0~1, 원점은 좌상단)

주의: mediapipe 는 한글이 들어간 경로를 읽지 못한다.
      그래서 파일 경로를 넘기지 않고, PIL 로 읽어 numpy 배열로 넘긴다.

실행:
    python 제스처_인식.py
    python 제스처_인식.py --image ../samples/victory.jpg
    python 제스처_인식.py --save        # 랜드마크 21점을 그린 PNG 를 이 폴더에 저장
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day2 (공용 자료)
PROJECT_ROOT = DAY_DIR.parents[1]
GESTURE_MODEL_PATH = PROJECT_ROOT / "models" / "gesture_recognizer.task"
DEFAULT_IMAGES = [DAY_DIR / "samples" / "pointing_up.jpg",
                  DAY_DIR / "samples" / "victory.jpg"]

# 랜드마크 21점 중 자주 쓰는 번호
WRIST, THUMB_TIP, INDEX_TIP = 0, 4, 8


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


# 손가락별 관절 연결 (손목 0 에서 각 손가락 끝까지)
HAND_CONNECTIONS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
                    (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15),
                    (15, 16), (13, 17), (0, 17), (17, 18), (18, 19), (19, 20)]


def save_landmarks(image: Image.Image, landmarks, out_path: Path) -> None:
    """랜드마크 21점과 번호를 그려 저장한다. 정규화 좌표 × 이미지 크기 = 픽셀."""
    from PIL import ImageDraw

    canvas = image.copy()
    draw = ImageDraw.Draw(canvas)
    points = [(lm.x * image.width, lm.y * image.height) for lm in landmarks]
    for a, b in HAND_CONNECTIONS:
        draw.line([points[a], points[b]], fill=(40, 121, 192), width=3)
    for idx, (x, y) in enumerate(points):
        color = (237, 125, 49) if idx in (WRIST, THUMB_TIP, INDEX_TIP) else (255, 255, 255)
        draw.ellipse([x - 5, y - 5, x + 5, y + 5], fill=color, outline=(0, 0, 0))
        draw.text((x + 6, y - 6), str(idx), fill=(0, 0, 0))
    canvas.save(out_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", action="append",
                        help="여러 번 줄 수 있다 (기본: pointing_up, victory)")
    parser.add_argument("--save", action="store_true",
                        help="랜드마크를 그린 이미지를 landmarks_<이름>.png 로 저장")
    args = parser.parse_args()
    paths = [Path(p) for p in args.image] if args.image else DEFAULT_IMAGES

    recognizer = load_recognizer()
    for path in paths:
        if not path.exists():
            raise SystemExit(f"이미지를 찾을 수 없습니다: {path}")
        image = Image.open(path).convert("RGB")
        result = recognizer.recognize(to_mp_image(image))

        print(f"입력 이미지 : {path.name} ({image.width}x{image.height})")
        if not result.gestures:
            print("  손을 찾지 못했습니다.\n")
            continue

        gesture = result.gestures[0][0]
        hand = result.handedness[0][0]
        landmarks = result.hand_landmarks[0]
        print(f"  gesture    : {gesture.category_name} (score {gesture.score:.2f})")
        print(f"  handedness : {hand.category_name}")
        print(f"  landmarks  : {len(landmarks)}점")
        for idx, name in ((WRIST, "손목"), (THUMB_TIP, "엄지 끝"),
                          (INDEX_TIP, "검지 끝")):
            lm = landmarks[idx]
            print(f"    [{idx:>2}] {name:<5} x={lm.x:.2f} y={lm.y:.2f}")
        if args.save:
            out_path = BASE_DIR / f"landmarks_{path.stem}.png"
            save_landmarks(image, landmarks, out_path)
            print(f"  저장       : {out_path.name}")
        print()

    print("gesture 는 '무슨 손 모양인가', landmarks 는 '손이 어디를 향하는가' 를 알려준다.")


if __name__ == "__main__":
    main()
