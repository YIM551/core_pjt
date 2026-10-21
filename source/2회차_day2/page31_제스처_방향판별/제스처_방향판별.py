# -*- coding: utf-8 -*-
"""[page 31] 실습 2-2 ― 랜드마크로 가리키는 방향을 판별하고 Text 로 만든다.

pointing_up.jpg 를 0 / 90 / 180 / 270 도 돌려 네 방향을 만든다.
  - gesture 카테고리는 손이 돌아가면 틀린다 (학습 데이터가 '세운 손' 위주)
  - 랜드마크 벡터(손목 → 검지 끝)는 회전과 무관하게 방향을 알려준다

좌표계 주의: 정규화 좌표는 원점이 좌상단이고 y 가 '아래로' 커진다.
            그래서 dy < 0 이 '위' 다.

실행:
    python 제스처_방향판별.py
    python 제스처_방향판별.py --mirror      # 셀카(거울) 화면 기준으로 좌우를 맞춘다
    python 제스처_방향판별.py --save        # 회전별 방향을 그린 PNG 를 이 폴더에 저장
"""
import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day2 (공용 자료)
PROJECT_ROOT = DAY_DIR.parents[1]
GESTURE_MODEL_PATH = PROJECT_ROOT / "models" / "gesture_recognizer.task"
DEFAULT_IMAGE = DAY_DIR / "samples" / "pointing_up.jpg"

WRIST, INDEX_TIP = 0, 8
MIN_VECTOR_RATIO = 0.08     # 벡터가 이미지 짧은 변의 8% 보다 짧으면 판단 보류
DIRECTION_KO = {"up": "위", "down": "아래", "left": "왼쪽", "right": "오른쪽",
                "unknown": "인식 불가"}


def load_recognizer():
    if not GESTURE_MODEL_PATH.exists():
        raise SystemExit(f"제스처 모델 파일이 없습니다: {GESTURE_MODEL_PATH}")

    from mediapipe.tasks import python as mp_tasks
    from mediapipe.tasks.python import vision

    options = vision.GestureRecognizerOptions(
        base_options=mp_tasks.BaseOptions(
            model_asset_buffer=GESTURE_MODEL_PATH.read_bytes()),
        running_mode=vision.RunningMode.IMAGE,
        num_hands=1,
    )
    return vision.GestureRecognizer.create_from_options(options)


def to_mp_image(image: Image.Image):
    import mediapipe as mp

    return mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(image))


def classify_direction(landmarks, width: int, height: int,
                       mirror: bool = False) -> str:
    """손목 → 검지 끝 벡터로 up / down / left / right 를 정한다.

    정규화 좌표(0~1)를 픽셀로 되돌려야 가로·세로 비율이 맞는다.
    """
    wrist, tip = landmarks[WRIST], landmarks[INDEX_TIP]
    dx = (tip.x - wrist.x) * width
    dy = (tip.y - wrist.y) * height          # y 는 아래로 커진다
    if math.hypot(dx, dy) < min(width, height) * MIN_VECTOR_RATIO:
        return "unknown"
    if abs(dx) > abs(dy):
        is_right = dx > 0
        if mirror:                           # 거울 화면이면 좌우만 뒤집는다
            is_right = not is_right
        return "right" if is_right else "left"
    return "down" if dy > 0 else "up"


def to_text(category: str, direction: str) -> str:
    """LLM 입력용 한 줄. 형식은 한 번 정하면 바꾸지 않는다."""
    return f"손 제스처: {category}, 가리키는 방향: {DIRECTION_KO[direction]}"


def save_directions(tiles, out_path: Path) -> None:
    """회전한 이미지마다 손목 → 검지 끝 화살표와 판정 방향을 그려 가로로 이어 붙인다.

    PIL 기본 글꼴은 한글을 못 그려서 그림 속 글자는 영어로 쓴다.
    """
    from PIL import ImageDraw

    canvas = Image.new("RGB", (sum(img.width for img, _, _ in tiles),
                               max(img.height for img, _, _ in tiles)), "white")
    draw = ImageDraw.Draw(canvas)
    x0 = 0
    for image, landmarks, label in tiles:
        canvas.paste(image, (x0, 0))
        if landmarks:
            wrist, tip = landmarks[WRIST], landmarks[INDEX_TIP]
            p0 = (x0 + wrist.x * image.width, wrist.y * image.height)
            p1 = (x0 + tip.x * image.width, tip.y * image.height)
            draw.line([p0, p1], fill=(237, 125, 49), width=5)
            draw.ellipse([p1[0] - 7, p1[1] - 7, p1[0] + 7, p1[1] + 7], fill=(237, 125, 49))
        draw.rectangle([x0, 0, x0 + draw.textlength(label) + 12, 22], fill="white")
        draw.text((x0 + 6, 5), label, fill=(0, 0, 0))
        x0 += image.width
    canvas.save(out_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default=str(DEFAULT_IMAGE))
    parser.add_argument("--mirror", action="store_true",
                        help="셀카 카메라처럼 좌우가 반전된 화면 기준으로 판정")
    parser.add_argument("--save", action="store_true",
                        help="회전별 방향을 그린 이미지를 direction_<이름>.png 로 저장")
    args = parser.parse_args()

    path = Path(args.image)
    if not path.exists():
        raise SystemExit(f"이미지를 찾을 수 없습니다: {path}")
    base = Image.open(path).convert("RGB")
    recognizer = load_recognizer()

    print(f"입력 이미지 : {path.name}   mirror={args.mirror}\n")
    print(f"{'회전':>5} | {'gesture 카테고리':<22} | {'랜드마크 방향':<8}")
    print("-" * 50)
    texts, tiles = [], []
    for angle in (0, 90, 180, 270):
        image = base.rotate(angle, expand=True)   # 반시계 방향 회전
        result = recognizer.recognize(to_mp_image(image))
        if not result.gestures:
            print(f"{angle:>4}° | 손을 찾지 못함")
            tiles.append((image, None, f"{angle} deg -> no hand"))
            continue
        gesture = result.gestures[0][0]
        direction = classify_direction(result.hand_landmarks[0],
                                       image.width, image.height, args.mirror)
        category = f"{gesture.category_name} ({gesture.score:.2f})"
        print(f"{angle:>4}° | {category:<22} | {DIRECTION_KO[direction]}")
        texts.append(to_text(gesture.category_name, direction))
        tiles.append((image, result.hand_landmarks[0], f"{angle} deg -> {direction}"))

    print("\n[LLM 입력용 Text]")
    for text in texts:
        print(f"  {text}")
    if args.save:
        out_path = BASE_DIR / f"direction_{path.stem}.png"
        save_directions(tiles, out_path)
        print(f"\n저장 : {out_path.name}")
    print("\n카테고리는 손이 돌아가면 틀린다 → 방향은 랜드마크로 판단한다.")


if __name__ == "__main__":
    main()
