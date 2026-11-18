#!/usr/bin/env bash
# 3회차 1일차 (PJT01) ― 라즈베리파이 준비 명령어. 강의자료 9 · 11 · 32 · 36 · 38 · 48쪽.
# 한 줄씩 복사해 실행한다. 배선은 반드시 전원을 끈 상태에서 한다 (GPIO 는 3.3V ― 5V 금지).
# PC 는 2회차 프로젝트 폴더 C:\work\core_pjt 에 이어서 만든다 (.venv · models\ 그대로, httpx 포함).
# 3회차 배포 폴더 3회차_day1 · 3회차_web 은 C:\work\core_pjt\source\ 안에 둔다.

# ── PC (PowerShell) ① 처음부터 세팅 ― 2회차 환경(C:\work\core_pjt)이 없을 때만
#   python --version                              # 3.12 권장
#   cd C:\work\core_pjt
#   python -m venv .venv
#   .venv\Scripts\activate
#   python -m pip install --upgrade pip
#   pip install fastapi==0.141.1 uvicorn==0.54.0 pillow==12.3.0 httpx==0.28.1 psutil==7.2.2
#   pip install ultralytics==8.4.164 torch==2.14.0 torchvision==0.29.0
#   pip install llama-cpp-python==0.3.34 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
#   pip install huggingface_hub==2.0.0
#   hf download ggml-org/Qwen2.5-VL-3B-Instruct-GGUF Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf --local-dir models
#   hf download ggml-org/Qwen2.5-VL-3B-Instruct-GGUF mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf --local-dir models
#   hf download Qwen/Qwen3-4B-GGUF Qwen3-4B-Q4_K_M.gguf --local-dir models
#   curl.exe -L -o models\gesture_recognizer.task https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task

# ── PC (PowerShell) ② ▶ 2회차 환경이 이미 세팅되어 있다면 여기서 시작
#    코드를 라즈베리파이 홈으로 복사 (ssafy 는 Pi 사용자 이름)
#   cd C:\work\core_pjt
#   .venv\Scripts\activate
#   cd source\3회차_day1
#   scp page36_LED_테스트\test_led.py page39_OLED_테스트\test_oled.py page33_카메라_테스트\test_camera.py ssafy@<PiIP>:~/
#   scp page45_기기서버_D1_D3\camera_server.py ssafy@<PiIP>:~/
#   ssh ssafy@<PiIP>

# ── 라즈베리파이 (SSH) ────────────────────────────────────────────────

# [38쪽] SPI 켜기 → Interface Options → SPI → Enable (재부팅)
sudo raspi-config
ls /dev/spidev0.0                                   # 있으면 켜진 것

# [32쪽] 카메라 인식
rpicam-hello --list-cameras

# [11쪽] venv ― picamera2(apt 시스템 패키지)를 쓰려면 --system-site-packages 필수 (PEP 668)
python3 -m venv --system-site-packages ~/venv
~/venv/bin/pip install luma.oled                    # OLED 라이브러리 (venv 에만)
sudo apt install -y fonts-dejavu-core               # OLED 큰 글씨 폰트 (이미 있으면 생략)

# [33 · 36 · 39쪽] 센서 단독 확인 (서버를 띄우기 전에)
~/venv/bin/python3 ~/test_led.py
~/venv/bin/python3 ~/test_oled.py
~/venv/bin/python3 ~/test_camera.py

# [48쪽] 기기 서버 ― 반드시 venv 파이썬 (OLED 에 'start')
~/venv/bin/python3 ~/camera_server.py

# 다른 SSH 창에서 D2 · D3 확인
curl "http://localhost:8080/gpio-blink?pin=17"      # 오른쪽 LED 3회 → {"ok": true}
curl "http://localhost:8080/gpio-blink?pin=27"      # 왼쪽 LED 3회
curl "http://localhost:8080/oled-display?text=LEFT" # {"ok": true, "oled": "shown"}

# 끌 때 (SSH) ― 대괄호가 없으면 SSH 세션까지 끊긴다
pkill -f "[c]amera_server.py"
