# -*- coding: utf-8 -*-
"""[page 25] 실습 2-1 ― YOLO11n 첫 추론.

이미지 1장을 넣고 검출된 객체의 이름 / 확신도 / 박스 좌표와
추론에 걸린 시간을 출력한다.

TODO(실습)
    conf 값을 0.1 / 0.25 / 0.6 으로 바꿔가며 검출 개수가 어떻게 변하는지 기록한다.
    --sweep 옵션을 주면 세 값을 한 번에 비교해 준다.

실행:
    python YOLO_첫추론.py
    python YOLO_첫추론.py --image ../samples/sample2.jpg --conf 0.5
    python YOLO_첫추론.py --sweep
"""
import argparse
import time
from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day1 (공용 자료)
DEFAULT_IMAGE = DAY_DIR / "samples" / "sample.jpg"
YOLO_MODEL_PATH = DAY_DIR.parents[1] / "yolo11n.pt"


def load_model():
    from ultralytics import YOLO

    return YOLO(str(YOLO_MODEL_PATH))


def detect(model, image: Image.Image, conf: float):
    """추론 1회를 수행하고 (결과, 소요시간 ms)를 돌려준다."""
    t0 = time.perf_counter()
    results = model.predict(image, conf=conf, verbose=False)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return results, elapsed_ms


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default=str(DEFAULT_IMAGE))
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--sweep", action="store_true",
                        help="conf 0.1 / 0.25 / 0.6 비교")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"이미지를 찾을 수 없습니다: {image_path}")

    image = Image.open(image_path).convert("RGB")
    print(f"입력 이미지 : {image_path.name}  ({image.width}x{image.height})")

    t0 = time.perf_counter()
    model = load_model()
    print(f"모델 로딩   : {time.perf_counter() - t0:.2f}s\n")

    if args.sweep:
        print(f"{'conf':>6} | {'검출 수':>6} | {'추론(ms)':>9} | 검출 결과")
        print("-" * 72)
        for conf in (0.1, 0.25, 0.6):
            results, elapsed_ms = detect(model, image, conf)
            boxes = results[0].boxes
            names = [model.names[int(b.cls)] for b in boxes]
            print(f"{conf:>6.2f} | {len(boxes):>6} | {elapsed_ms:>9.0f} | "
                  f"{', '.join(names) if names else '(없음)'}")
        print("\nconf 를 낮추면 검출 수가 늘지만 오탐(False Positive)도 함께 늘어난다.")
        return

    results, elapsed_ms = detect(model, image, args.conf)
    boxes = results[0].boxes
    print(f"conf 임계값 : {args.conf}")
    print(f"검출 객체   : {len(boxes)}개\n")
    for box in boxes:
        name = model.names[int(box.cls)]
        score = float(box.conf)
        x1, y1, x2, y2 = (round(v) for v in box.xyxy[0].tolist())
        print(f"  {name:<12} conf={score:.2f}  xyxy=({x1}, {y1}, {x2}, {y2})")
    print(f"\n추론 시간   : {elapsed_ms:.0f} ms")


if __name__ == "__main__":
    main()
