# -*- coding: utf-8 -*-
"""[page 14] 실습 1-1 ― YOLO 결과를 'LLM이 읽을 텍스트'로 변환.

LLM은 박스 좌표를 이해하지 못한다. LLM 입력으로 넣으려면
검출 결과를 "person 2개, chair 1개" 같은 한 문장으로 요약해야 한다.

강의 포인트
  - 출력 형식을 고정해야 LLM 프롬프트가 안정적으로 동작한다.
  - conf 가 낮은 검출을 포함할지는 노이즈 ↔ 누락의 트레이드오프다.

실행:
    python YOLO결과_텍스트요약.py
    python YOLO결과_텍스트요약.py --image ../samples/pointing_up.jpg
"""
import argparse
from collections import Counter
from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day2 (공용 자료)
DEFAULT_IMAGE = DAY_DIR / "samples" / "sample.jpg"
YOLO_MODEL_PATH = DAY_DIR.parents[1] / "yolo11n.pt"

NO_OBJECT_TEXT = "인식된 객체 없음"


def summarize(model, results, min_conf: float = 0.0) -> str:
    """검출 결과를 '이름 N개, 이름 M개' 형태의 한 문장으로 요약한다.

    min_conf 미만의 검출은 버린다. LLM 입력 포맷이 되므로
    한 번 정한 형식을 바꾸지 않는 것이 중요하다.
    """
    counter = Counter(
        model.names[int(box.cls)]
        for box in results[0].boxes
        if float(box.conf) >= min_conf
    )
    if not counter:
        return NO_OBJECT_TEXT
    return ", ".join(f"{name} {count}개" for name, count in counter.most_common())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default=str(DEFAULT_IMAGE))
    parser.add_argument("--conf", type=float, default=0.25,
                        help="YOLO 검출 임계값")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"이미지를 찾을 수 없습니다: {image_path}")

    from ultralytics import YOLO

    model = YOLO(str(YOLO_MODEL_PATH))
    image = Image.open(image_path).convert("RGB")
    results = model.predict(image, conf=args.conf, verbose=False)

    print(f"입력 이미지 : {image_path.name}")
    print("\n[원본 검출 결과]")
    for box in results[0].boxes:
        print(f"  {model.names[int(box.cls)]:<12} conf={float(box.conf):.2f}")

    print("\n[LLM 입력용 요약 문장]")
    print(f"  [YOLO 객체 인식] {summarize(model, results)}")

    # 요약 단계에서 한 번 더 거르면 노이즈를 줄일 수 있다.
    print("\n[min_conf 별 요약 비교 ― 노이즈 ↔ 누락]")
    for min_conf in (0.0, 0.5, 0.8):
        print(f"  min_conf={min_conf:.1f} → {summarize(model, results, min_conf)}")

    print("\n이 한 문장이 VLM 설명문과 함께 LLM 입력으로 들어갑니다.")


if __name__ == "__main__":
    main()
