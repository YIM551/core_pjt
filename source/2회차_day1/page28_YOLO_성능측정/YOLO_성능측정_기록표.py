# -*- coding: utf-8 -*-
"""[page 28] 측정 결과 기록표 자동 채우기.

강의 자료의 '측정 결과 기록표'를 손으로 채우는 대신 이 스크립트로 측정한다.
모델 로딩 시간 / 추론 시간(N회 평균) / 검출 객체 수 / 메모리 증가량을
CSV로 남겨 3일차 최종 발표의 '모델 선정 근거'로 사용한다.

실행:
    python YOLO_성능측정_기록표.py
    python YOLO_성능측정_기록표.py --models yolo11n.pt yolo11s.pt --runs 10
    (yolo11s.pt 는 없으면 ultralytics가 자동 다운로드한다)
"""
import argparse
import csv
import time
from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day1 (공용 자료)
PROJECT_ROOT = DAY_DIR.parents[1]
DEFAULT_IMAGE = DAY_DIR / "samples" / "sample.jpg"
OUTPUT_CSV = BASE_DIR / "measurement.csv"


def current_memory_mb() -> float:
    """현재 프로세스의 메모리 사용량(MB). psutil이 없으면 0을 돌려준다."""
    try:
        import psutil

        return psutil.Process().memory_info().rss / 1024 / 1024
    except ImportError:
        return 0.0


def resolve_weight(name: str) -> str:
    """프로젝트 루트에 가중치가 있으면 그 경로를, 없으면 이름 그대로 쓴다.

    이름 그대로 넘기면 ultralytics가 자동으로 내려받는다.
    """
    local = PROJECT_ROOT / name
    return str(local) if local.exists() else name


def benchmark(weight_name: str, image: Image.Image, runs: int, conf: float) -> dict:
    from ultralytics import YOLO

    mem_before = current_memory_mb()

    t0 = time.perf_counter()
    model = YOLO(resolve_weight(weight_name))
    load_s = time.perf_counter() - t0

    # 첫 추론에는 초기화 비용이 섞이므로 워밍업 1회는 평균에서 제외한다.
    model.predict(image, conf=conf, verbose=False)

    durations = []
    for _ in range(runs):
        t0 = time.perf_counter()
        results = model.predict(image, conf=conf, verbose=False)
        durations.append((time.perf_counter() - t0) * 1000)

    mem_after = current_memory_mb()
    names = [model.names[int(b.cls)] for b in results[0].boxes]

    return {
        "model": weight_name,
        "load_s": round(load_s, 2),
        "infer_ms_avg": round(sum(durations) / len(durations), 1),
        "infer_ms_min": round(min(durations), 1),
        "infer_ms_max": round(max(durations), 1),
        "fps": round(1000 / (sum(durations) / len(durations)), 1),
        "detected": len(names),
        "objects": " ".join(sorted(set(names))) or "-",
        "mem_delta_mb": round(mem_after - mem_before, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["yolo11n.pt"])
    parser.add_argument("--image", default=str(DEFAULT_IMAGE))
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--conf", type=float, default=0.25)
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"이미지를 찾을 수 없습니다: {image_path}")
    image = Image.open(image_path).convert("RGB")

    if current_memory_mb() == 0.0:
        print("(참고) psutil 미설치 ― 메모리 항목은 0으로 표시됩니다."
              " pip install psutil==7.2.2\n")

    rows = []
    for name in args.models:
        print(f"측정 중: {name} ({args.runs}회) ...")
        rows.append(benchmark(name, image, args.runs, args.conf))

    header = ["model", "load_s", "infer_ms_avg", "infer_ms_min", "infer_ms_max",
              "fps", "detected", "objects", "mem_delta_mb"]
    print("\n" + " | ".join(f"{h:>12}" for h in header))
    print("-" * (15 * len(header)))
    for row in rows:
        print(" | ".join(f"{str(row[h]):>12}" for h in header))

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV 저장: {OUTPUT_CSV}")
    print("이 파일은 중간 결과입니다. 3일차까지 보관하세요.")


if __name__ == "__main__":
    main()
