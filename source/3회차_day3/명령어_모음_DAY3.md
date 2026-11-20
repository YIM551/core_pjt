# 3회차 3일차 ― 명령어 모음 (복사용)

> `AI코어프로젝트_3회차_DAY3_r2.pptx` 의 명령어 화면을 그대로 옮겼다. 결과(출력)는 빼고 **입력할 명령만** 있다.
> 한 블록씩 복사해 붙여 넣는다. 결과는 강의자료 같은 쪽의 화면과 비교한다.

- **PC** = PowerShell. 프로젝트 폴더는 `C:\work\core_pjt` 이다.
  3회차 배포 폴더 `3회차_day1` · `3회차_day2` · `3회차_day3` · `3회차_web` 은 모두 `C:\work\core_pjt\source\` 안에 나란히 둔다.
  실습은 `C:\work\core_pjt\source\3회차_day3` 에서 시작한다. 오늘 쓰는 PC 서버는 3회차 완성본 `page30_음성경로_통합` 이다.
- **Pi** = 라즈베리파이 SSH 창. 홈 폴더(`~`)에서 실행한다.
- `<PiIP>` 는 라즈베리파이 IP 로 바꾼다 (예: `192.168.0.42`). `pi` 는 Pi 사용자 이름이다.
- 1 · 2일차 환경이 그대로 있으면 **0. SETUP 은 건너뛰고** 9쪽부터 시작한다. 새 PC · 새 라즈베리파이라면 0. SETUP 을 위에서부터 차례로 한다.
- PC 에서 **새 터미널**을 열 때마다 아래 3줄을 먼저 입력한다.

```powershell
cd C:\work\core_pjt
.venv\Scripts\activate
cd source\3회차_day3
```

---

## 0. SETUP ― 처음부터 세팅 (venv → 패키지 → 모델 → whisper → 기기 LLM)

**SETUP 에서 받는 모델 전체** ― 1 · 2 · 3일차에 쓰는 모델을 여기서 한 번에 받는다

| 모델 | 어디에 | 크기 | 쓰는 곳 | 받는 곳 |
|---|---|---|---|---|
| YOLO11n `yolo11n.pt` | PC `C:\work\core_pjt\` | 5.4MB | A3 객체 인식 | 0-2 |
| Qwen2.5-VL-3B 본체 `Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf` | PC `models\` | 1.9GB | A4 장면 설명 (VLM) | 0-2 |
| Qwen2.5-VL-3B 이미지 인코더 `mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf` | PC `models\` | 1.3GB | A4 ― 본체와 둘 다 있어야 이미지 입력이 된다 | 0-2 |
| Qwen3-4B `Qwen3-4B-Q4_K_M.gguf` | PC `models\` | 2.4GB | A5 도구 선택 (로컬 PC 탭) | 0-2 |
| 제스처 `gesture_recognizer.task` | PC `models\` | 8MB | 화면 MediaPipe 손 제스처 | 0-2 |
| whisper base `ggml-base.bin` | Pi `~/whisper.cpp/models/` | 142MB | D4 음성 인식 | 0-6 |
| Qwen3-1.7B `Qwen3-1.7B-Q4_K_M.gguf` | Pi `~/models/` | 1.3GB | D5 기기 LLM (기기 탭) | 0-7 |

### 0-1. PC ― 가상환경 · 패키지

```powershell
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

# 4) 확인
python -c "import fastapi, httpx, llama_cpp, ultralytics; print('ok')"
```

### 0-2. PC ― 모델 다운로드 (전부, 약 5.6GB)

반드시 `C:\work\core_pjt` 에서 실행한다 (서버가 이 폴더 기준으로 모델을 찾는다). PowerShell 에서는 `curl` 이 아니라 반드시 `curl.exe`.

```powershell
cd C:\work\core_pjt
.venv\Scripts\activate

# 1) YOLO11n (5.4MB) → 프로젝트 폴더 바로 아래 (models\ 아님)
#    처음 실행할 때 자동으로 받기도 하지만, 수업 중 네트워크 문제를 피하려고 미리 받는다
curl.exe -L -o yolo11n.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt

# 2) VLM 본체(1.9GB) + 이미지 인코더 mmproj(1.3GB) ― 둘 다 있어야 이미지 입력이 된다
hf download ggml-org/Qwen2.5-VL-3B-Instruct-GGUF Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf --local-dir models
hf download ggml-org/Qwen2.5-VL-3B-Instruct-GGUF mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf --local-dir models

# 3) PC LLM (2.4GB) ― 로컬 PC 탭의 도구 선택
hf download Qwen/Qwen3-4B-GGUF Qwen3-4B-Q4_K_M.gguf --local-dir models

# 4) 제스처 인식 모델 (약 8MB)
curl.exe -L -o models\gesture_recognizer.task https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task

# 5) 확인 ― 파일 5개가 위 표의 크기와 비슷하면 된다
dir yolo11n.pt
dir models
dir source -Name
```

### 0-3. PC → Pi ― 코드를 라즈베리파이 홈으로 복사

```powershell
cd C:\work\core_pjt\source
# 1일차 센서 테스트
scp 3회차_day1\page26_카메라_테스트\test_camera.py pi@<PiIP>:~/
scp 3회차_day1\page29_LED_테스트\test_led.py pi@<PiIP>:~/
scp 3회차_day1\page32_OLED_테스트\test_oled.py pi@<PiIP>:~/
# 2일차 마이크 · PTT · whisper, 3일차 D5 확인
scp 3회차_day2\page48_마이크_테스트\test_mic.py pi@<PiIP>:~/
scp 3회차_day2\page51_PTT_버튼_테스트\test_ptt.py pi@<PiIP>:~/
scp 3회차_day2\page58_whisper_빌드\whisper_빌드.sh pi@<PiIP>:~/
scp 3회차_day2\page58_whisper_빌드\PTT_음성인식_단독.py pi@<PiIP>:~/
scp 3회차_day3\page25_온디바이스LLM_D5\D5_단독확인.py pi@<PiIP>:~/
# 3회차 완성 기기 서버 (D1 ~ D5 + F205) · 부팅 자동 실행 서비스
scp 3회차_day2\심화_F205_음성품질\camera_server.py pi@<PiIP>:~/
scp 3회차_day1\심화_F105_F106\camera-stream.service pi@<PiIP>:~/
ssh pi@<PiIP>
```

### 0-4. Pi ― SPI · 카메라 · 가상환경 (1일차)

```bash
# SPI 켜기 ― Interface Options → SPI → Enable (재부팅)
sudo raspi-config
ls /dev/spidev0.0

# 카메라 인식
rpicam-hello --list-cameras

# 가상환경 ― picamera2 를 쓰려면 --system-site-packages 필수
python3 -m venv --system-site-packages ~/venv
~/venv/bin/pip install luma.oled
sudo apt install -y fonts-dejavu-core
~/venv/bin/python3 -c "import picamera2, gpiozero, luma.oled; print('ok')"
```

### 0-5. Pi ― I2S 마이크 켜기 (2일차)

파일 맨 아래에 두 줄을 `#` 없이 넣고 저장(Ctrl+O · Enter · Ctrl+X) → 재부팅

```bash
sudo nano /boot/firmware/config.txt
```

```text
dtparam=i2s=on
dtoverlay=googlevoicehat-soundcard
```

```bash
sudo reboot
```

재부팅 후 다시 `ssh pi@<PiIP>`

```bash
arecord -l
```

### 0-6. Pi ― whisper.cpp 빌드 · base 모델 (2일차, 약 3분)

```bash
sudo apt install -y build-essential cmake git
nohup bash ~/whisper_빌드.sh > ~/whisper.log 2>&1 &
```

`whisper_빌드.sh` 가 없으면 아래를 직접 한 줄씩 실행한다 (스크립트와 같은 내용)

```bash
git clone --depth 1 https://github.com/ggml-org/whisper.cpp ~/whisper.cpp
cd ~/whisper.cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j4 --config Release
./models/download-ggml-model.sh base
cd ~
```

### 0-7. Pi ― 기기 LLM : llama-cpp-python · Qwen3-1.7B 모델 (3일차, 6 ~ 20분)

반드시 venv 의 pip. 컴파일이 오래 걸리므로 백그라운드로 돌린다.

```bash
nohup ~/venv/bin/pip install "llama-cpp-python==0.3.35" > ~/pip.log 2>&1 &
mkdir -p ~/models
curl -fL -o ~/models/Qwen3-1.7B-Q4_K_M.gguf https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf
```

4GB 모델에서 컴파일이 `Killed` 로 끝나면 동시에 쓰는 코어를 줄여 다시

```bash
CMAKE_BUILD_PARALLEL_LEVEL=2 nohup ~/venv/bin/pip install "llama-cpp-python==0.3.35" > ~/pip.log 2>&1 &
```

### 0-8. Pi ― SETUP 확인 (9쪽 화면과 같다)

설치가 끝나기 전에 전원을 끄지 않는다 ― 컴파일을 처음부터 다시 한다.

```bash
arecord -l
tail -n 2 ~/whisper.log
ls ~/whisper.cpp/build/bin/whisper-cli ~/whisper.cpp/models/ggml-base.bin
tail -n 1 ~/pip.log
ls -lh ~/models
~/venv/bin/python3 -c "import llama_cpp, gpiozero, luma.oled; print('ok')"
free -h
```

### 0-9. Pi ― 부팅 자동 실행 (선택, F106)

```bash
sed -i "s/__USER__/$USER/g" ~/camera-stream.service
sudo cp ~/camera-stream.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now camera-stream
journalctl -u camera-stream -f
```

---

## 9쪽 ― 실습 환경 설치 · 기기 LLM (3일차 추가분)

**Pi** ― 2일차 상태 확인 (I2S 사운드 카드 · whisper 빌드)

```bash
arecord -l
tail -n 2 ~/whisper.log
```

**Pi** ― 기기 LLM 설치를 백그라운드로 시작한다 (컴파일 6 ~ 20분, 반드시 venv 의 pip). 기다리는 동안 트렌드 · 모델 설명을 진행한다

```bash
nohup ~/venv/bin/pip install "llama-cpp-python==0.3.35" > ~/pip.log 2>&1 &
mkdir -p ~/models
curl -fL -o ~/models/Qwen3-1.7B-Q4_K_M.gguf https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf
```

**Pi** ― 4GB 모델에서 컴파일이 `Killed` 로 끝나면 동시에 쓰는 코어를 줄여 다시

```bash
CMAKE_BUILD_PARALLEL_LEVEL=2 nohup ~/venv/bin/pip install "llama-cpp-python==0.3.35" > ~/pip.log 2>&1 &
```

**PC** ― 오늘 쓰는 기기 서버(D1 ~ D5) · D5 확인 스크립트를 라즈베리파이로 복사

```powershell
cd C:\work\core_pjt\source\3회차_day3
scp page25_온디바이스LLM_D5\camera_server.py pi@<PiIP>:~/
scp page25_온디바이스LLM_D5\D5_단독확인.py pi@<PiIP>:~/
```

## 21쪽 ― 실습 1-1 llama-cpp-python · Qwen3-1.7B 설치 확인

**Pi** ― 9쪽에서 시작한 설치가 끝났는지 (설치가 끝나기 전에 전원을 끄지 않는다)

```bash
tail -n 1 ~/pip.log
ls -lh ~/models
~/venv/bin/python3 -c "import llama_cpp, gpiozero, luma.oled; print('ok')"
free -h
```

## 25 ~ 26쪽 ― 실습 1-2 D5 단독 확인 (F203)

**Pi** ― 기기 서버 (반드시 venv 파이썬 ― 시스템 python3 면 /llm-infer 가 매번 실패)

```bash
~/venv/bin/python3 ~/camera_server.py
```

**Pi** ― 다른 SSH 창 (첫 요청은 1분 가까이)

```bash
python3 ~/D5_단독확인.py --device localhost
curl -X POST localhost:8080/llm-infer -H "Content-Type: application/json" -d '{"user_content": "[사용자 질문] 오른쪽으로 2칸 가"}'
curl -X POST localhost:8080/llm-infer -H "Content-Type: application/json" -d '{"user_content": ""}'
```

## 30 ~ 31쪽 ― 실습 1-3 통합 확인 (F204)

**Pi** ― 첫 음성 질문 전에 기기 LLM 을 미리 올려 둔다 (워밍업)

```bash
curl -X POST localhost:8080/llm-infer -H "Content-Type: application/json" -d '{"user_content": "[사용자 질문] 준비", "history": []}'
```

**PC** ― 기기 서버를 켜 둔 채 실행 → 브라우저 http://127.0.0.1:8000 → 연동 탭에 IP 등록 → 기기 탭에서 PTT 질문 · 타이핑 질문

```powershell
cd page30_음성경로_통합
python 대시보드_음성통합.py
```

## 32 ~ 33쪽 ― 실습 1-4 API 검증

**PC 터미널 2** ― 터미널 1 에는 `page30_음성경로_통합` 서버를 켜 둔다

```powershell
cd page32_API_검증
python API_검증.py --quick
python API_검증.py
python API_검증.py --device <PiIP>
```

## 35 ~ 36쪽 ― 실습 1-5 센서 테스트 5종

**Pi** ― 기기 서버 · 서비스를 먼저 끄고, 출력 → 입력 순서로

```bash
sudo systemctl stop camera-stream 2>/dev/null
pkill -f "[c]amera_server.py"
~/venv/bin/python3 ~/test_camera.py
~/venv/bin/python3 ~/test_led.py
~/venv/bin/python3 ~/test_oled.py
python3 ~/test_mic.py
~/venv/bin/python3 ~/test_ptt.py
```

## 37쪽 ― 실습 1-6 기동 순서 점검

**Pi** ― ① 기기 서버 (또는 `sudo systemctl start camera-stream`)

```bash
~/venv/bin/python3 ~/camera_server.py
```

**Pi** ― 다른 SSH 창 ③ ~ ⑤ (④ 는 PTT 를 누르고 말한 뒤)

```bash
curl "http://localhost:8080/gpio-blink?pin=17"
curl "http://localhost:8080/oled-display?text=LEFT"
curl http://localhost:8080/voice-text
curl -X POST localhost:8080/llm-infer -H "Content-Type: application/json" -d '{"user_content": "[사용자 질문] 준비", "history": []}'
```

**PC 터미널 1** ― ⑥ 서버 (② 영상은 브라우저 http://<PiIP>:8080/stream.mjpg)

```powershell
cd page30_음성경로_통합
python 대시보드_음성통합.py
```

**PC 터미널 2** ― 한 번에 점검

```powershell
cd page37_기동_점검
python 기동_점검.py --device <PiIP>
python 기동_점검.py --device <PiIP> --ptt
```

## 40 ~ 41쪽 ― 실습 2-1 도구별 시나리오 (F301)

기기 탭 질문 (텍스트로 한 번, PTT 음성으로 한 번)

```text
앞에 뭐가 있어?
오른쪽으로 3칸 가
위로 2칸 가
오른쪽 2칸 가고 위로 1칸
저쪽으로 가
```

**PC 터미널 2** ― 같은 질문을 스크립트로

```powershell
cd page40_도구별_시나리오
python 시나리오_실행.py --device <PiIP>
python 시나리오_실행.py --device <PiIP> --ptt
python 시나리오_실행.py --device <PiIP> --no-output
```

## 44 ~ 45쪽 ― 실습 3-1 음성 되묻기 대화 (F302)

기기 탭에서 PTT 로 `저쪽으로 2칸 가` → 이어서 `왼쪽` 또는 `응`

**PC 터미널 2**

```powershell
cd page44_되묻기_대화
python 되묻기_대화.py --device <PiIP>
python 되묻기_대화.py --device <PiIP> --ptt
```

## 52 ~ 53쪽 ― 실습 4-1 장애 주입 (F303)

**PC 터미널 2** ― 띄워 둔 채 장애를 하나씩 만든다
① 라즈베리파이 서버 Ctrl+C ② 다시 실행 ③ 공유기에서 Pi Wi-Fi 잠시 끊기 ④ 서버 재시작 직후 첫 질문 ⑤ OLED 선을 뽑고 move

```powershell
cd page52_장애_주입
python 장애_관찰.py --device <PiIP>
python 장애_관찰.py --device <PiIP> --ask "왼쪽"
```

**Pi** ― ① 기기 서버 끄기 · ② 다시 실행

```bash
pkill -f "[c]amera_server.py"
~/venv/bin/python3 ~/camera_server.py
```

## 56 ~ 57쪽 ― 실습 5-1 최종 검증 (F304)

**PC 터미널 1**

```powershell
cd page30_음성경로_통합
python 대시보드_음성통합.py
```

**PC 터미널 2** ― 마지막 줄 `전체 N/N PASS` 를 확인한다

```powershell
cd page56_최종_검증
python API_검증.py --quick
python API_검증.py
python API_검증.py --device <PiIP>
python API_검증.py --quick --device <PiIP>
```

## 76쪽 ― 부록 A 전체 실행 명령 모음

**Pi**

```bash
sudo systemctl stop camera-stream 2>/dev/null; pkill -f "[c]amera_server.py"
for t in camera led oled ptt; do ~/venv/bin/python3 ~/test_$t.py; done
python3 ~/test_mic.py
~/venv/bin/python3 ~/camera_server.py
curl -X POST localhost:8080/llm-infer -H "Content-Type: application/json" -d '{"user_content": "[사용자 질문] 준비", "history": []}'
```

**PC 터미널 1** ― 서버 (3회차 완성 서버)

```powershell
cd page30_음성경로_통합
python 대시보드_음성통합.py
```

**PC 터미널 2** ― 점검 · 시나리오 · 검증

```powershell
cd page37_기동_점검
python 기동_점검.py --device <PiIP>
cd ..\page40_도구별_시나리오
python 시나리오_실행.py --device <PiIP>
cd ..\page44_되묻기_대화
python 되묻기_대화.py --device <PiIP>
cd ..\page52_장애_주입
python 장애_관찰.py --device <PiIP>
cd ..\page56_최종_검증
python API_검증.py --device <PiIP>
```
