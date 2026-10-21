# -*- coding: utf-8 -*-
"""[page 58] 실습 5 ― YOLO11n 파인튜닝 실행.

핵심: 반드시 사전학습 가중치(yolo11n.pt)에서 출발한다(전이학습).
      처음부터 학습(scratch)하면 수만 장의 데이터가 필요하다.

사전 준비:
    python 데이터셋_준비와검증.py --demo

실행:
    python YOLO_파인튜닝_학습.py                 # 실습 기본값(epochs 10)
    python YOLO_파인튜닝_학습.py --epochs 50 --device 0
    python YOLO_파인튜닝_학습.py --data <내_data.yaml 경로>

주의: CPU 학습은 느리다. 실습에서는 epochs 를 10~20 으로 줄인다.
      OOM(메모리 부족)이 나면 batch 를 8 → 4 로 낮춘다.
"""
import argparse
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day1 (공용 자료)
PROJECT_ROOT = DAY_DIR.parents[1]
DEFAULT_DATA = DAY_DIR / "dataset" / "data.yaml"
PRETRAINED = PROJECT_ROOT / "yolo11n.pt"
RUNS_DIR = DAY_DIR / "runs"


def resolve_device(requested: str) -> str:
    """'auto' 면 GPU가 있을 때만 GPU를 쓴다."""
    if requested != "auto":
        return requested
    try:
        import torch

        return "0" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--epochs", type=int, default=10,
                        help="실습 기본 10. 실제로는 50~100")
    parser.add_argument("--imgsz", type=int, default=320,
                        help="운용 해상도와 맞출 것 (실전은 보통 640)")
    parser.add_argument("--batch", type=int, default=8,
                        help="OOM 발생 시 가장 먼저 줄일 값")
    parser.add_argument("--patience", type=int, default=10,
                        help="개선 없으면 조기 종료")
    parser.add_argument("--device", default="auto", help="auto | cpu | 0")
    parser.add_argument("--name", default="ft_v1")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        raise SystemExit(
            f"data.yaml 이 없습니다: {data_path}\n"
            "  먼저 실행하세요 -> python 데이터셋_준비와검증.py --demo"
        )
    if not PRETRAINED.exists():
        print(f"(참고) {PRETRAINED.name} 이 없어 ultralytics가 자동 다운로드합니다.")

    device = resolve_device(args.device)
    print(f"데이터셋 : {data_path}")
    print(f"디바이스 : {device}")
    print(f"설정     : epochs={args.epochs} imgsz={args.imgsz} batch={args.batch}\n")

    from ultralytics import YOLO

    # 사전학습 가중치에서 출발하는 것이 전이학습의 핵심이다.
    model = YOLO(str(PRETRAINED) if PRETRAINED.exists() else "yolo11n.pt")

    t0 = time.perf_counter()
    model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        patience=args.patience,
        device=device,
        project=str(RUNS_DIR),
        name=args.name,
        exist_ok=True,
        verbose=False,
        plots=False,
    )
    elapsed = time.perf_counter() - t0

    best = RUNS_DIR / args.name / "weights" / "best.pt"
    print(f"\n학습 완료 : {elapsed / 60:.1f}분")
    print(f"best.pt   : {best}")
    print(f"존재 여부 : {best.exists()}")
    print("\n다음 단계 -> python YOLO_파인튜닝_평가비교.py")


if __name__ == "__main__":
    main()
