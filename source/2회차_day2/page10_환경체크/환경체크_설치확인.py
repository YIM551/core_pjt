# -*- coding: utf-8 -*-
"""[page 10] 2일차 실습 환경 체크 ― 1일차 환경 + 2일차 추가분이 준비됐는지 확인한다.

2일차에 새로 필요한 것은 두 가지다.
  - mediapipe 패키지 + 제스처 인식 모델(gesture_recognizer.task)
  - LLM 가중치 (Qwen3-4B GGUF)

실행:
    python 환경체크_설치확인.py
"""
import importlib
import platform
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day2 (공용 자료)
PROJECT_ROOT = DAY_DIR.parents[1]                   # 프로젝트 루트
MODELS_DIR = PROJECT_ROOT / "models"

REQUIRED_PACKAGES = [
    ("fastapi", "웹 대시보드 서버", False),
    ("uvicorn", "웹 대시보드 서버 실행", False),
    ("httpx", "3일차 API 검증", False),
    ("PIL", "이미지 처리 (pillow)", False),
    ("ultralytics", "YOLO Object Detection", False),
    ("llama_cpp", "VLM / LLM GGUF 추론", False),
    ("mediapipe", "손 제스처 인식", True),
]

WEIGHTS = [
    (PROJECT_ROOT / "yolo11n.pt", "YOLO11n", False),
    (MODELS_DIR / "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf", "VLM 본체", False),
    (MODELS_DIR / "mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf", "VLM mmproj", False),
    (MODELS_DIR / "gesture_recognizer.task", "제스처 모델", True),
    (MODELS_DIR / "Qwen3-4B-Q4_K_M.gguf", "LLM", True),
]

SAMPLES = ["sample.jpg", "pointing_up.jpg", "victory.jpg"]


def mark(is_new: bool) -> str:
    return "[2일차 신규]" if is_new else ""


def check_packages() -> bool:
    print("[1] 패키지 설치 확인")
    ok = True
    for module_name, purpose, is_new in REQUIRED_PACKAGES:
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, "__version__", "?")
            print(f"    OK   {module_name:<12} {version:<10} {purpose} {mark(is_new)}")
        except ImportError:
            ok = False
            print(f"    MISS {module_name:<12} {'':<10} {purpose} {mark(is_new)}")
    return ok


def check_weights() -> bool:
    print("\n[2] 모델 가중치 확인")
    ok = True
    for path, label, is_new in WEIGHTS:
        if path.exists():
            size_mb = path.stat().st_size / 1024 / 1024
            print(f"    OK   {label:<10} {size_mb:8.1f} MB  {path.name} {mark(is_new)}")
        elif path.name == "yolo11n.pt":
            # ultralytics 가 첫 실행 때 자동으로 받는다 ― 누락이 아니다
            print(f"    AUTO {label:<10} {'':>8}     {path.name} → 실습 1-1 첫 실행 때 자동 다운로드")
        else:
            ok = False
            print(f"    MISS {label:<10} {'':>8}     {path} {mark(is_new)}")
    return ok


def check_samples() -> bool:
    print("\n[3] 입력 이미지 확인")
    ok = True
    for name in SAMPLES:
        path = DAY_DIR / "samples" / name
        print(f"    {'OK  ' if path.exists() else 'MISS'} samples/{name}")
        ok = ok and path.exists()
    return ok


def main() -> int:
    print(f"Python {platform.python_version()} / {platform.system()}\n")
    packages_ok, weights_ok, samples_ok = check_packages(), check_weights(), check_samples()

    print("\n" + "-" * 60)
    if packages_ok and weights_ok and samples_ok:
        print("모든 준비 완료 ― 실습을 시작하세요.")
        return 0
    print("누락된 항목이 있습니다. MISS 항목을 먼저 해결하세요.")
    if not packages_ok:
        print("  패키지 : pip install <MISS 로 표시된 패키지>  (pillow 는 PIL)")
    if not weights_ok:
        print("  가중치 : source\\2회차_day2\\README.md 의 '받는 방법' 명령")
    return 1


if __name__ == "__main__":
    sys.exit(main())
