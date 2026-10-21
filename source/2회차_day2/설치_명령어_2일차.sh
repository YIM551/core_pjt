#!/usr/bin/env bash
# SSAFY AI 코어 프로젝트 2회차 2일차 ― 실습 환경 설치 (1일차 환경에 추가)
# 강의자료 8~9쪽. 위에서부터 순서대로 실행한다.
# (Windows 는 PowerShell/CMD 에서 각 줄을 그대로 입력)

# 1일차 가상환경에 이어서 설치
.venv\Scripts\activate
pip install mediapipe==1.0.1

# 제스처 인식 모델 (약 8MB) → models\   (PowerShell 에서는 반드시 curl.exe)
cd C:\work\core_pjt
curl.exe -L -o models\gesture_recognizer.task https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task

# LLM 가중치 (약 2.4GB) → models\   (1일차에 받았으면 생략)
hf download Qwen/Qwen3-4B-GGUF Qwen3-4B-Q4_K_M.gguf --local-dir models
