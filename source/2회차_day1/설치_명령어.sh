#!/usr/bin/env bash
# SSAFY AI 코어 프로젝트 2회차 1일차 ― 실습 환경 설치
# 강의자료 12~13쪽. 위에서부터 순서대로 실행한다.
# (Windows 는 PowerShell/CMD 에서 각 줄을 그대로 입력)

# ── 1. 가상환경과 패키지 ──────────────────────────────
# 0) 파이썬 버전 확인 (3.12 권장)
python --version

# 1) 프로젝트 폴더로 이동 ― 배포 폴더(README.md · source)는
#    반드시 C:\work\core_pjt 에 둔다. 다른 곳이면 먼저 옮긴다
cd C:\work\core_pjt

# 2) 가상환경 생성 후 활성화
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

# 3) 패키지 설치 ― 한 줄씩 그대로 (약 3분)
python -m pip install --upgrade pip
pip install fastapi==0.141.1 uvicorn==0.54.0 pillow==12.3.0 httpx==0.28.1 psutil==7.2.2
pip install ultralytics==8.4.164 torch==2.14.0 torchvision==0.29.0
pip install llama-cpp-python==0.3.34 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

# ── 2. 모델 가중치 ────────────────────────────────────
# YOLO11n (5.4MB) ― page23 실습을 처음 돌릴 때 자동 다운로드

# hf 명령 설치 (HuggingFace 다운로드 도구) ― 1번과 같은 폴더에서
cd C:\work\core_pjt
pip install huggingface_hub==2.0.0

# VLM 본체(1.9GB) + mmproj(1.3GB) ― 둘 다 있어야 이미지 입력이 된다
hf download ggml-org/Qwen2.5-VL-3B-Instruct-GGUF Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf --local-dir models
hf download ggml-org/Qwen2.5-VL-3B-Instruct-GGUF mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf --local-dir models

# LLM(2.4GB) ― 2일차부터 쓴다. 오늘은 없어도 된다
hf download Qwen/Qwen3-4B-GGUF Qwen3-4B-Q4_K_M.gguf --local-dir models
