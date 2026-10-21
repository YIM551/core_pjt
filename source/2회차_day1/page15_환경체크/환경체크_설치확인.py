# -*- coding: utf-8 -*-
"""[page 15] 실습 환경 체크 ― 필요한 패키지/모델 파일이 준비됐는지 한 번에 확인한다.

설치가 끝나면 각자 실행해서, 실습에 들어가기 전에
막히는 지점(설치 누락, GPU 미인식, 가중치 미다운로드)을 미리 찾아낸다.

실행:
    python 환경체크_설치확인.py
"""
import importlib
import platform
import sys
from pathlib import Path

# 이 프로젝트가 쓰는 모델 가중치 위치(강의 자료 기준).
# 실습 폴더 구조에 맞게 바꿔도 된다.
BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day1 (공용 자료)
PROJECT_ROOT = DAY_DIR.parents[1]                   # 프로젝트 루트
YOLO_WEIGHT = PROJECT_ROOT / "yolo11n.pt"
VLM_GGUF = PROJECT_ROOT / "models" / "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
VLM_MMPROJ = PROJECT_ROOT / "models" / "mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf"

REQUIRED_PACKAGES = [
    ("fastapi", "PoC 서버"),
    ("uvicorn", "PoC 서버 실행"),
    ("httpx", "PoC 클라이언트"),
    ("psutil", "성능 측정 (메모리)"),
    ("PIL", "이미지 처리 (pillow)"),
    ("ultralytics", "YOLO Object Detection"),
    ("torch", "YOLO 백엔드"),
    ("llama_cpp", "VLM GGUF 추론 (llama-cpp-python)"),
]


def check_packages() -> bool:
    print("[1] 패키지 설치 확인")
    ok = True
    for module_name, purpose in REQUIRED_PACKAGES:
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, "__version__", "?")
            print(f"    OK   {module_name:<14} {version:<12} ({purpose})")
        except ImportError:
            ok = False
            print(f"    MISS {module_name:<14} {'':<12} ({purpose})")
    return ok


def check_device() -> None:
    """GPU를 쓸 수 있는지 확인한다.

    torch가 CPU 빌드로 설치되면 GPU가 있어도 CPU로만 동작한다.
    RTX 50 시리즈(Blackwell)는 cu128 이상 빌드가 필요하다.
    """
    print("\n[2] 추론 디바이스 확인")
    try:
        import torch
    except ImportError:
        print("    torch 미설치 ― YOLO 실습 불가")
        return

    if torch.cuda.is_available():
        print(f"    OK   CUDA 사용 가능 : {torch.cuda.get_device_name(0)}")
    else:
        print("    INFO CPU 모드로 동작 (torch CPU 빌드이거나 GPU 없음)")
        print("         → 실습은 가능하지만 VLM/파인튜닝이 느립니다.")


def check_weights() -> bool:
    print("\n[3] 모델 가중치 파일 확인")
    ok = True
    # (경로, 이름, 없을 때 안내, 자동 다운로드 여부)
    targets = [
        (YOLO_WEIGHT, "YOLO11n", "다음 실습(page23)을 처음 실행할 때 자동으로 받는다", True),
        (VLM_GGUF, "VLM 본체", "README 의 hf download 명령으로 받는다", False),
        (VLM_MMPROJ, "VLM mmproj", "빠뜨리면 이미지 입력이 동작하지 않음", False),
    ]
    for path, label, hint, auto in targets:
        if path.exists():
            size_mb = path.stat().st_size / 1024 / 1024
            print(f"    OK   {label:<12} {size_mb:8.1f} MB  {path.name}")
        elif auto:                                   # 정상 ― 실패로 세지 않는다
            print(f"    AUTO {label:<12} {'':>8}      {path.name}")
            print(f"         → {hint}")
        else:
            ok = False
            print(f"    MISS {label:<12} {'':>8}      {path}")
            print(f"         → {hint}")
    return ok


def main() -> int:
    print(f"Python {platform.python_version()} / {platform.system()}\n")
    packages_ok = check_packages()
    check_device()
    weights_ok = check_weights()

    print("\n" + "-" * 60)
    if packages_ok and weights_ok:
        print("모든 준비 완료 ― 실습을 시작하세요.")
        return 0
    print("누락된 항목이 있습니다. 위 MISS 항목을 먼저 해결하세요.")
    if not packages_ok:
        print("  pip install fastapi==0.141.1 uvicorn==0.54.0 httpx==0.28.1 psutil==7.2.2 pillow==12.3.0")
        print("  pip install ultralytics==8.4.164 torch==2.14.0 torchvision==0.29.0")
        print("  pip install llama-cpp-python==0.3.34 \\")
        print("      --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu")
    if not weights_ok:
        print("  가중치 : README '가중치' 절의 hf download 명령 (models 폴더)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
