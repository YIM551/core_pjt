# 3회차 1일차 ― 명령어 모음 (복사용)

> `AI코어프로젝트_3회차_DAY1.pptx` 의 명령어 화면을 그대로 옮겼다. 결과(출력)는 빼고 **입력할 명령만** 있다.
> 한 블록씩 복사해 붙여 넣는다. 결과는 강의자료 같은 쪽의 화면과 비교한다.

- **PC** = PowerShell. 2회차 프로젝트 폴더 `C:\work\core_pjt` 에 이어서 만든다 (2회차 `.venv` · `models\` 그대로).
  3회차 배포 폴더 `3회차_day1` · `3회차_web` 은 `C:\work\core_pjt\source\` 안에 둔다. 실습은 `C:\work\core_pjt\source\3회차_day1` 에서 시작한다.
- **Pi** = 라즈베리파이 SSH 창. 홈 폴더(`~`)에서 실행한다.
- `<PiIP>` 는 라즈베리파이 IP 로 바꾼다 (예: `192.168.0.42`). `ssafy` 는 Pi 사용자 이름이다.
- PC 에서 **새 터미널**을 열 때마다 아래 3줄을 먼저 입력한다.

```powershell
cd C:\work\core_pjt
.venv\Scripts\activate
cd source\3회차_day1
```

---

## 9쪽 ― 실습 환경 설치 · 라즈베리파이 준비

**PC ①** ― 처음부터 세팅 (2회차 환경이 없을 때만. 있으면 ② 로 건너뛴다)

```powershell
# ① 처음부터 세팅 ― 2회차 환경(C:\work\core_pjt)이 없을 때만
# 0) 파이썬 버전 확인 (3.12 권장)
python --version

# 1) 프로젝트 폴더 ― 배포 폴더(README.md · source)는 반드시 C:\work\core_pjt 에 둔다
cd C:\work\core_pjt

# 2) 가상환경 생성 후 활성화
python -m venv .venv
.venv\Scripts\activate

# 3) 패키지 설치 ― 한 줄씩 그대로 (약 3분)
python -m pip install --upgrade pip
pip install fastapi==0.141.1 uvicorn==0.54.0 pillow==12.3.0 httpx==0.28.1 psutil==7.2.2
pip install ultralytics==8.4.164 torch==2.14.0 torchvision==0.29.0
pip install llama-cpp-python==0.3.34 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
pip install huggingface_hub==2.0.0

# 4) 모델 가중치 → models\  (YOLO11n 은 처음 실행할 때 자동 다운로드)
hf download ggml-org/Qwen2.5-VL-3B-Instruct-GGUF Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf --local-dir models
hf download ggml-org/Qwen2.5-VL-3B-Instruct-GGUF mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf --local-dir models
hf download Qwen/Qwen3-4B-GGUF Qwen3-4B-Q4_K_M.gguf --local-dir models
curl.exe -L -o models\gesture_recognizer.task https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task
```

**PC ②** ― 2회차 환경에 3회차 추가 · 코드를 라즈베리파이 홈으로 복사

```powershell
# ② ▶ 2회차 환경(C:\work\core_pjt)이 이미 세팅되어 있다면 여기서 시작
#    PC 는 새로 설치할 패키지가 없다. 3회차_day1 · 3회차_web 을 C:\work\core_pjt\source\ 에 넣는다
cd C:\work\core_pjt
.venv\Scripts\activate
cd source\3회차_day1
scp page33_카메라_테스트\test_camera.py ssafy@<PiIP>:~/
scp page36_LED_테스트\test_led.py ssafy@<PiIP>:~/
scp page39_OLED_테스트\test_oled.py ssafy@<PiIP>:~/
scp page45_기기서버_D1_D3\camera_server.py ssafy@<PiIP>:~/
ssh ssafy@<PiIP>
```

**Pi** ― SPI 켜기 (Interface Options → SPI → Enable, 재부팅)

```bash
sudo raspi-config
ls /dev/spidev0.0
```

**Pi** ― 카메라 인식

```bash
rpicam-hello --list-cameras
```

**Pi** ― 가상환경 (picamera2 를 쓰려면 `--system-site-packages` 필수)

```bash
python3 -m venv --system-site-packages ~/venv
~/venv/bin/pip install luma.oled
sudo apt install -y fonts-dejavu-core
```

## 10쪽 ― 실습 환경 체크 ① PC

**PC**

```powershell
cd C:\work\core_pjt
.venv\Scripts\activate
python --version
python -c "import fastapi, httpx, llama_cpp; print('ok')"
dir models
ipconfig
cd source\3회차_day1
```

## 11쪽 ― 실습 환경 체크 ② 라즈베리파이

**PC**

```powershell
ssh ssafy@<PiIP>
```

**Pi**

```bash
cat /etc/os-release | head -1
python3 --version
hostname -I
python3 -m venv --system-site-packages ~/venv
~/venv/bin/pip install luma.oled
~/venv/bin/python3 -c "import picamera2, gpiozero, luma.oled; print('ok')"
```

## 23 ~ 24쪽 ― 실습 1-1 기준선 기록 (F101)

**PC 터미널 1** ― 대시보드 서버 (켜 둔다)

```powershell
cd page23_기준선_검증
python 대시보드_기준선.py
```

**PC 터미널 2** ― 검증

```powershell
cd page23_기준선_검증
python API_검증.py --quick
python API_검증.py
```

## 33 ~ 34쪽 ― 실습 2-1 카메라 테스트

**Pi**

```bash
~/venv/bin/python3 ~/test_camera.py
~/venv/bin/python3 ~/test_camera.py --fps 10
```

**PC** ― 스냅샷을 PC 로 가져와 초점 · 밝기 확인

```powershell
scp ssafy@<PiIP>:~/camera_test.jpg .
```

## 36 ~ 37쪽 ― 실습 2-2 LED 테스트

**Pi**

```bash
~/venv/bin/python3 ~/test_led.py
```

## 39 ~ 40쪽 ― 실습 2-3 OLED 테스트

**Pi**

```bash
~/venv/bin/python3 ~/test_oled.py
```

## 48 ~ 49쪽 ― 실습 3-2 기기 서버 엔드포인트별 확인 (F102)

**PC** ― 코드 복사 (9쪽에서 했으면 생략)

```powershell
scp page45_기기서버_D1_D3\camera_server.py ssafy@<PiIP>:~/
```

**Pi** ― 기기 서버 (반드시 venv 파이썬, 켜 둔다)

```bash
~/venv/bin/python3 ~/camera_server.py
```

**Pi 의 다른 SSH 창**

```bash
curl "http://localhost:8080/gpio-blink?pin=17"
curl "http://localhost:8080/gpio-blink?pin=27"
curl "http://localhost:8080/oled-display?text=LEFT"
curl "http://localhost:8080/gpio-blink?pin=abc"
```

**Pi** ― 기기 서버 끄기 (대괄호가 없으면 SSH 세션까지 끊긴다)

```bash
pkill -f "[c]amera_server.py"
```

## 53쪽 ― 실습 4-1 카메라 중계 (F103)

**PC** ― 서버를 띄운 뒤 브라우저 http://127.0.0.1:8000 → 연동 탭에 기기 이름 · IP 등록

```powershell
cd page53_카메라_중계
python 대시보드_카메라중계.py
```

## 61 ~ 63쪽 ― 실습 4-2 기기 연동 (F103 · F104)

**PC** ― 서버를 띄운 뒤 기기 탭에서 질문

```powershell
cd page61_기기연동
python 대시보드_기기연동.py
```

기기 탭 질문 (복사해서 입력창에 붙여 넣는다)

```text
앞에 뭐가 있어?
오른쪽으로 3칸 가
위로 2칸 가
오른쪽 2칸 가고 위로 1칸
저쪽으로 가
```

## 71 ~ 72쪽 ― 실습 5-1 API 검증

**PC 터미널 2** ― 터미널 1 에는 `page61_기기연동` 서버를 켜 둔다

```powershell
cd page71_API_검증
python API_검증.py --quick
python API_검증.py --device <PiIP>
```

## 73쪽 ― 심화 과제 (선택) F105 · F106

**Pi** ― F105 FPS 낮추기

```bash
~/venv/bin/python3 ~/camera_server.py --fps 10
```

**PC** ― F106 서비스 파일 복사

```powershell
scp 심화_F105_F106\camera-stream.service ssafy@<PiIP>:~/
```

**Pi** ― F106 부팅 자동 실행 등록

```bash
sed -i "s/__USER__/$USER/g" ~/camera-stream.service
sudo cp ~/camera-stream.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now camera-stream
journalctl -u camera-stream -f
```

## 78쪽 ― 부록 A 전체 실행 명령 모음

**PC 터미널 1** ― 서버

```powershell
cd page61_기기연동
python 대시보드_기기연동.py
```

**PC 터미널 2** ― 검증 · 코드 복사

```powershell
cd page71_API_검증
python API_검증.py --quick
python API_검증.py --device <PiIP>
cd ..
scp page33_카메라_테스트\test_camera.py ssafy@<PiIP>:~/
scp page36_LED_테스트\test_led.py ssafy@<PiIP>:~/
scp page39_OLED_테스트\test_oled.py ssafy@<PiIP>:~/
scp page45_기기서버_D1_D3\camera_server.py ssafy@<PiIP>:~/
```

**Pi**

```bash
rpicam-hello --list-cameras
~/venv/bin/python3 ~/test_camera.py
~/venv/bin/python3 ~/test_led.py
~/venv/bin/python3 ~/test_oled.py
~/venv/bin/python3 ~/camera_server.py
pkill -f "[c]amera_server.py"
curl "http://localhost:8080/gpio-blink?pin=17"
curl "http://localhost:8080/oled-display?text=LEFT"
```
