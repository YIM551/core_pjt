# -*- coding: utf-8 -*-
"""[page 61] 평가 ― 파인튜닝 전/후 비교.

사전학습 모델(before)과 파인튜닝 모델(after)을 같은 검증셋으로 돌려
mAP50 / mAP50-95 / 추론 시간을 나란히 비교하고 CSV로 남긴다.

강의 포인트
  - 숫자보다 중요한 것은 '어떤 상황에서 실패하는가'다.
  - 확인은 반드시 학습에 쓰지 않은 데이터(val)로 한다.
  - 파인튜닝 전 모델은 우리 클래스를 아예 모르므로 mAP가 0에 가깝게 나온다.
    그 차이 자체가 '도메인 정렬'의 효과다.

사전 준비:
    python 데이터셋_준비와검증.py --demo
    python YOLO_파인튜닝_학습.py

실행:
    python YOLO_파인튜닝_평가비교.py
    python YOLO_파인튜닝_평가비교.py --conf 0.25    # 실제로 쓸 임계값에서 다시 평가 (과제 ②)
"""
import argparse
import csv
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day1 (공용 자료)
PROJECT_ROOT = DAY_DIR.parents[1]
DEFAULT_DATA = DAY_DIR / "dataset" / "data.yaml"
DEFAULT_BEFORE = PROJECT_ROOT / "yolo11n.pt"
DEFAULT_AFTER = DAY_DIR / "runs" / "ft_v1" / "weights" / "best.pt"
OUTPUT_CSV = BASE_DIR / "finetune_compare.csv"


def evaluate(weight_path: Path, data_path: Path, imgsz: int, device: str,
             conf: float) -> dict:
    from ultralytics import YOLO

    model = YOLO(str(weight_path))
    metrics = model.val(data=str(data_path), imgsz=imgsz, device=device, conf=conf,
                        verbose=False, plots=False)

    # 모델이 검증 이미지에서 낸 가장 높은 확신도 ― 실제 임계값(0.25 등)을 넘는지 본다
    val_images = sorted((data_path.parent / "images" / "val").glob("*.jpg"))
    max_conf = max((float(r.boxes.conf.max()) for r in
                    model.predict([str(p) for p in val_images], imgsz=imgsz, conf=0.001,
                                  device=device, verbose=False) if len(r.boxes)),
                   default=0.0)

    # 추론 속도는 검증셋 이미지 1장으로 따로 측정한다.
    sample = next((data_path.parent / "images" / "val").glob("*.jpg"), None)
    infer_ms = 0.0
    if sample is not None:
        model.predict(str(sample), imgsz=imgsz, verbose=False)   # 워밍업
        t0 = time.perf_counter()
        for _ in range(5):
            model.predict(str(sample), imgsz=imgsz, verbose=False)
        infer_ms = (time.perf_counter() - t0) / 5 * 1000

    return {
        "weights": weight_path.name,
        "mAP50": round(float(metrics.box.map50), 4),
        "mAP50_95": round(float(metrics.box.map), 4),
        "precision": round(float(metrics.box.mp), 4),
        "recall": round(float(metrics.box.mr), 4),
        "max_conf": round(max_conf, 4),
        "infer_ms": round(infer_ms, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--before", default=str(DEFAULT_BEFORE))
    parser.add_argument("--after", default=str(DEFAULT_AFTER))
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--conf", type=float, default=0.001,
                        help="평가 임계값 (기본 0.001 = ultralytics val 기본값)")
    args = parser.parse_args()

    data_path = Path(args.data)
    after_path = Path(args.after)
    before_path = Path(args.before)

    if not data_path.exists():
        raise SystemExit(
            f"data.yaml 이 없습니다: {data_path}\n"
            "  먼저 -> python 데이터셋_준비와검증.py --demo"
        )
    if not after_path.exists():
        raise SystemExit(
            f"파인튜닝 결과가 없습니다: {after_path}\n"
            "  먼저 -> python YOLO_파인튜닝_학습.py"
        )

    rows = []
    print("[before] 사전학습 모델 평가 중...")
    print(f"평가 임계값 conf = {args.conf}")
    rows.append({"stage": "before", **evaluate(before_path, data_path,
                                               args.imgsz, args.device, args.conf)})
    print("[after ] 파인튜닝 모델 평가 중...")
    rows.append({"stage": "after", **evaluate(after_path, data_path,
                                              args.imgsz, args.device, args.conf)})

    header = ["stage", "weights", "mAP50", "mAP50_95", "precision", "recall",
              "max_conf", "infer_ms"]
    print("\n" + " | ".join(f"{h:>10}" for h in header))
    print("-" * (13 * len(header)))
    for row in rows:
        print(" | ".join(f"{str(row[h]):>10}" for h in header))

    before, after = rows[0], rows[1]
    delta50 = after["mAP50"] - before["mAP50"]
    print(f"\nmAP50 변화    : {before['mAP50']:.4f} -> {after['mAP50']:.4f} "
          f"({delta50:+.4f})")
    print(f"mAP50-95 변화 : {before['mAP50_95']:.4f} -> {after['mAP50_95']:.4f} "
          f"({after['mAP50_95'] - before['mAP50_95']:+.4f})")

    if delta50 > 0:
        print("\n사전학습 모델은 우리 클래스를 모르기 때문에 점수가 거의 0이다.")
        print("이 차이가 '도메인 정렬(domain alignment)'의 효과다.")
    else:
        print("\n개선이 없다면 데이터 수/다양성 부족 또는 epochs 부족을 의심한다.")

    if after["max_conf"] < 0.25:
        print(f"\n[주의] 파인튜닝 모델의 최고 확신도 {after['max_conf']:.4f} < 0.25")
        print("  순위(mAP)는 맞지만 확신이 낮다 ― 실제로 쓰는 conf 0.25 에서는 아무것도 검출하지 못한다.")
        print("  확인 : python YOLO_파인튜닝_평가비교.py --conf 0.25")

    print("\n[과적합 징후 체크]")
    print("  - train loss는 내려가는데 val mAP가 정체/하락 -> 데이터 부족 또는 epochs 과다")
    print("  - 학습 데이터에서만 잘 맞고 새 사진에서 급락 -> 다양성 부족")

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV 저장: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
