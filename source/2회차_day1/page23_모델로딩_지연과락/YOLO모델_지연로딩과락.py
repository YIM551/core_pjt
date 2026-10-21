# -*- coding: utf-8 -*-
"""[page 23] YOLO 모델 지연 로딩(lazy loading) + 락(lock) 패턴.

강의 포인트
  - 서버 기동 시점에 모델을 올리면 기동이 느려지고, 가중치가 없을 때 앱 자체가 죽는다.
    → 첫 요청 때 로드하는 '지연 로딩'을 쓴다.
  - 지연 로딩을 여러 스레드에서 동시에 호출하면 모델이 중복 로드되어 메모리가 2배로 든다.
    → double-checked locking으로 초기화 구간을 보호한다.

이 스크립트는 스레드 8개로 동시에 get_yolo_model()을 호출해서
모델 객체가 '단 하나'만 만들어지는지 직접 확인한다.

실행:
    python YOLO모델_지연로딩과락.py
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# 규칙: 정적 파일/가중치 경로는 실행 디렉터리(cwd)에 의존하지 않도록
#       항상 __file__ 기준 절대경로로 만든다.
BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day1 (공용 자료)
PROJECT_ROOT = DAY_DIR.parents[1]                   # 프로젝트 루트
YOLO_MODEL_PATH = PROJECT_ROOT / "yolo11n.pt"

_yolo_model = None
_yolo_init_lock = threading.Lock()
_load_count = 0  # 실제로 몇 번 로드됐는지 세기 위한 실습용 카운터


def _resolve_device() -> str:
    """추론에 쓸 디바이스를 결정한다. GPU가 없으면 CPU로 떨어진다."""
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def get_yolo_model():
    """YOLO 모델을 최초 요청 시 한 번만 로드해 재사용한다."""
    global _yolo_model, _load_count
    if _yolo_model is None:                 # ① 락 없이 빠르게 검사
        with _yolo_init_lock:               # ② 초기화 구간만 잠근다
            if _yolo_model is None:         # ③ 락 획득 후 한 번 더 검사
                from ultralytics import YOLO

                model = YOLO(str(YOLO_MODEL_PATH))
                model.to(_resolve_device())
                _load_count += 1
                _yolo_model = model
    return _yolo_model


def main() -> None:
    print(f"가중치 경로 : {YOLO_MODEL_PATH}")
    print(f"디바이스   : {_resolve_device()}")
    print("\n스레드 8개에서 동시에 get_yolo_model() 호출...")

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as pool:
        models = list(pool.map(lambda _: get_yolo_model(), range(8)))
    elapsed = time.perf_counter() - t0

    unique_ids = {id(m) for m in models}
    print(f"  반환된 객체 수        : {len(models)}")
    print(f"  서로 다른 모델 인스턴스: {len(unique_ids)}")
    print(f"  실제 로드 횟수        : {_load_count}")
    print(f"  소요 시간             : {elapsed:.2f}s")

    assert len(unique_ids) == 1, "모델이 중복 로드됐습니다 ― 락이 동작하지 않음"
    assert _load_count == 1, f"로드가 {_load_count}번 발생 ― 락이 동작하지 않음"
    print("\n[PASS] 8개 스레드가 같은 모델 인스턴스 1개를 공유합니다.")

    print("\n(참고) _yolo_init_lock 을 제거하면 _load_count 가 2 이상으로 올라가며,")
    print("       VLM처럼 2GB짜리 모델이라면 메모리가 그만큼 배로 늘어납니다.")


if __name__ == "__main__":
    main()
