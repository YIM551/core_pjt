# -*- coding: utf-8 -*-
"""[page 56] 데이터 수집 & 라벨링 ― YOLO 데이터셋 구조를 만들고 검증한다.

YOLO 라벨 포맷
    images/train/img001.jpg  ↔  labels/train/img001.txt
    labels 파일 한 줄 = "class_id  x_center  y_center  width  height"
    좌표는 모두 0~1 로 정규화된 값이다.

이 스크립트가 하는 일
    --init  : 빈 데이터셋 폴더 구조 + data.yaml 생성
    --demo  : 실습용 미니 데이터셋을 즉시 생성(도형 이미지 + 라벨 자동 작성)
              → 라벨링 도구 없이도 page 58 파인튜닝 실습을 바로 돌려볼 수 있다
    (기본)  : 기존 데이터셋의 라벨을 검증(범위 이탈, 짝 없는 파일, 클래스 분포)

실행:
    python 데이터셋_준비와검증.py --demo
    python 데이터셋_준비와검증.py            # 검증만
"""
import argparse
import random
from pathlib import Path

from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day1 (공용 자료)
DATASET_DIR = DAY_DIR / "dataset"
CLASS_NAMES = ["obstacle", "marker"]
SPLITS = ("train", "val")


def make_dirs() -> None:
    for split in SPLITS:
        (DATASET_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (DATASET_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)


def write_data_yaml() -> Path:
    """ultralytics 가 읽는 데이터셋 정의 파일.

    path 는 절대경로로 써서 실행 디렉터리(cwd)에 상관없이 동작하게 한다.
    """
    lines = [
        f"path: {DATASET_DIR.as_posix()}",
        "train: images/train",
        "val: images/val",
        "names:",
    ]
    lines += [f"  {i}: {name}" for i, name in enumerate(CLASS_NAMES)]
    yaml_path = DATASET_DIR / "data.yaml"
    yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return yaml_path


def make_demo_sample(index: int, split: str, rng: random.Random) -> None:
    """도형 2종(사각형=obstacle, 원=marker)을 그려 이미지와 라벨을 함께 만든다.

    실제 수업에서는 이 자리에 '운용 환경에서 직접 촬영한 사진 + 라벨링 도구'가 들어간다.
    여기서는 파인튜닝 파이프라인을 돌려보는 것이 목적이라 합성 데이터를 쓴다.
    """
    size = 320
    image = Image.new("RGB", (size, size),
                      (rng.randint(200, 255),) * 3)
    draw = ImageDraw.Draw(image)
    rows = []

    for class_id in range(len(CLASS_NAMES)):
        if rng.random() < 0.25:          # 가끔 빠뜨려 클래스 분포에 변화를 준다
            continue
        w = rng.randint(50, 90)
        h = rng.randint(50, 90)
        x1 = rng.randint(5, size - w - 5)
        y1 = rng.randint(5, size - h - 5)
        box = (x1, y1, x1 + w, y1 + h)
        if class_id == 0:
            draw.rectangle(box, fill=(220, 60, 60))
        else:
            draw.ellipse(box, fill=(50, 110, 220))
        rows.append(
            f"{class_id} {(x1 + w / 2) / size:.6f} {(y1 + h / 2) / size:.6f} "
            f"{w / size:.6f} {h / size:.6f}"
        )

    name = f"img{index:03d}"
    image.save(DATASET_DIR / "images" / split / f"{name}.jpg", quality=90)
    (DATASET_DIR / "labels" / split / f"{name}.txt").write_text(
        "\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")


def build_demo(train_count: int, val_count: int) -> None:
    rng = random.Random(42)          # 재현 가능한 데이터셋
    make_dirs()
    for i in range(train_count):
        make_demo_sample(i, "train", rng)
    for i in range(val_count):
        make_demo_sample(1000 + i, "val", rng)
    print(f"데모 데이터셋 생성 완료: train {train_count}장 / val {val_count}장")


def validate() -> bool:
    """라벨 파일을 검증한다. 실제 수업에서 가장 많이 터지는 지점이다."""
    if not DATASET_DIR.exists():
        print(f"데이터셋이 없습니다: {DATASET_DIR}")
        print("  --demo 또는 --init 으로 먼저 만드세요.")
        return False

    ok = True
    class_counter = {name: 0 for name in CLASS_NAMES}

    for split in SPLITS:
        image_dir = DATASET_DIR / "images" / split
        label_dir = DATASET_DIR / "labels" / split
        images = sorted(p for p in image_dir.glob("*")
                        if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
        print(f"\n[{split}] 이미지 {len(images)}장")

        for image_path in images:
            label_path = label_dir / f"{image_path.stem}.txt"
            if not label_path.exists():
                ok = False
                print(f"  [라벨 없음] {image_path.name}")
                continue

            for line_no, line in enumerate(
                    label_path.read_text(encoding="utf-8").splitlines(), 1):
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) != 5:
                    ok = False
                    print(f"  [필드 수 오류] {label_path.name}:{line_no} -> {line}")
                    continue
                class_id = int(parts[0])
                values = [float(v) for v in parts[1:]]
                if not 0 <= class_id < len(CLASS_NAMES):
                    ok = False
                    print(f"  [클래스 범위 초과] {label_path.name}:{line_no} "
                          f"class_id={class_id}")
                    continue
                if any(not 0.0 <= v <= 1.0 for v in values):
                    ok = False
                    print(f"  [정규화 안 됨] {label_path.name}:{line_no} -> {values}")
                    print("        좌표는 이미지 크기로 나눈 0~1 값이어야 합니다.")
                    continue
                class_counter[CLASS_NAMES[class_id]] += 1

        # 라벨만 있고 이미지가 없는 경우도 잡는다
        stems = {p.stem for p in images}
        for label_path in label_dir.glob("*.txt"):
            if label_path.stem not in stems:
                ok = False
                print(f"  [이미지 없음] {label_path.name}")

    print("\n[클래스 분포]")
    for name, count in class_counter.items():
        print(f"  {name:<12} {count}개")
    if min(class_counter.values(), default=0) == 0:
        print("  주의: 박스가 하나도 없는 클래스가 있습니다. 학습되지 않습니다.")

    print("\n" + ("[PASS] 데이터셋 검증 통과" if ok else "[FAIL] 위 항목을 수정하세요"))
    return ok


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true", help="빈 폴더 구조만 생성")
    parser.add_argument("--demo", action="store_true",
                        help="실습용 미니 데이터셋 자동 생성")
    parser.add_argument("--train-count", type=int, default=40)
    parser.add_argument("--val-count", type=int, default=10)
    args = parser.parse_args()

    if args.init:
        make_dirs()
        print(f"폴더 구조 생성 완료: {DATASET_DIR}")
    if args.demo:
        build_demo(args.train_count, args.val_count)
    if args.init or args.demo:
        print(f"data.yaml 작성: {write_data_yaml()}")

    validate()


if __name__ == "__main__":
    main()
