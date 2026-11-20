# 3회차 2일차 ― 명령어 모음 (복사용)

> `AI코어프로젝트_3회차_DAY2_r2.pptx` 의 명령어 화면을 그대로 옮겼다. 결과(출력)는 빼고 **입력할 명령만** 있다.
> 한 블록씩 복사해 붙여 넣는다. 결과는 강의자료 같은 쪽의 화면과 비교한다.

- **PC** = PowerShell. 2회차 · 1일차 프로젝트 폴더 `C:\work\core_pjt` 에 이어서 한다 (`.venv` · `models\` 그대로, PC 는 새로 설치할 것이 없다).
  3회차 배포 폴더 `3회차_day2` 는 `C:\work\core_pjt\source\` 안, `3회차_day1` · `3회차_web` 옆에 둔다. 실습은 `C:\work\core_pjt\source\3회차_day2` 에서 시작한다.
- **Pi** = 라즈베리파이 SSH 창. 홈 폴더(`~`)에서 실행한다. 1일차 `~/venv` 를 그대로 쓴다.
- `<PiIP>` 는 라즈베리파이 IP 로 바꾼다 (예: `192.168.0.42`). `pi` 는 Pi 사용자 이름이다.
- PC 에서 **새 터미널**을 열 때마다 아래 3줄을 먼저 입력한다.

```powershell
cd C:\work\core_pjt
.venv\Scripts\activate
cd source\3회차_day2
```

---

## 8쪽 ― 시작 전 확인 · 1일차 상태 그대로인가

**Pi** ― 1일차 기기 서버 · LED (확인 후 Ctrl+C 로 끈다)

```bash
~/venv/bin/python3 ~/camera_server.py
```

**Pi** ― 다른 SSH 창

```bash
curl "http://localhost:8080/gpio-blink?pin=27"
free -h
```

## 9쪽 ― 실습 환경 설치 · 라즈베리파이 준비 (2일차 추가분)

**PC** ― 2일차 코드를 라즈베리파이 홈으로 복사

```powershell
cd C:\work\core_pjt\source\3회차_day2
scp page48_마이크_테스트\test_mic.py pi@<PiIP>:~/
scp page51_PTT_버튼_테스트\test_ptt.py pi@<PiIP>:~/
scp page58_whisper_빌드\whisper_빌드.sh pi@<PiIP>:~/
scp page58_whisper_빌드\PTT_음성인식_단독.py pi@<PiIP>:~/
ssh pi@<PiIP>
```

**Pi** ― I2S 마이크 켜기 : 파일 맨 아래에 두 줄을 `#` 없이 넣고 저장(Ctrl+O · Enter · Ctrl+X) → 재부팅

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

**Pi** ― 재부팅 후 다시 `ssh pi@<PiIP>` → 오래 걸리는 설치를 백그라운드로 시작한다 (1일차 이어서 실습을 하는 동안 끝난다)

```bash
sudo apt install -y build-essential cmake git
nohup bash ~/whisper_빌드.sh > ~/whisper.log 2>&1 &
```

## 10쪽 ― 실습 환경 체크 ① PC

**PC**

```powershell
cd C:\work\core_pjt
.venv\Scripts\activate
python -c "import fastapi, httpx; print('ok')"
dir models -Name
dir source -Name
cd source\3회차_day2
```

## 11쪽 ― 실습 환경 체크 ② 라즈베리파이

**Pi** ― 설치가 끝났는지 (끝나지 않았으면 1일차 이어서 실습을 먼저 진행한다)

```bash
arecord -l
tail -n 2 ~/whisper.log
ls ~/whisper.cpp/build/bin/whisper-cli ~/whisper.cpp/models/ggml-base.bin
~/venv/bin/python3 -c "import gpiozero, luma.oled; print('ok')"
free -h
```

## 15쪽 ― 실습 1-1 카메라 중계 (F103)

**PC** ― 서버를 띄운 뒤 브라우저 http://127.0.0.1:8000 → 연동 탭에 기기 이름 · IP 등록

```powershell
cd page15_카메라_중계
python 대시보드_카메라중계.py
```

## 23 ~ 25쪽 ― 실습 1-2 기기 연동 (F103 · F104)

**PC** ― 서버를 띄운 뒤 기기 탭에서 질문

```powershell
cd page23_기기연동
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

## 29 ~ 30쪽 ― 실습 1-3 API 검증

**PC 터미널 2** ― 터미널 1 에는 `page23_기기연동` 서버를 켜 둔다

```powershell
cd page29_기기연동_API_검증
python API_검증.py --quick
python API_검증.py --device <PiIP>
```

## 27쪽 ― 도전 문제 (F105) · 심화 F106 (선택, 강의자료 없음)

**Pi** ― F105 FPS 낮추기

```bash
~/venv/bin/python3 ~/camera_server.py --fps 10
```

**PC** ― F106 서비스 파일 복사

```powershell
scp 심화_F105_F106\camera-stream.service pi@<PiIP>:~/
```

**Pi** ― F106 부팅 자동 실행 등록

```bash
sed -i "s/__USER__/$USER/g" ~/camera-stream.service
sudo cp ~/camera-stream.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now camera-stream
journalctl -u camera-stream -f
```

## 45쪽 ― 배선 순서 (전원 OFF)

**Pi** ― 9쪽 whisper 빌드가 끝났는지 확인한 뒤 끈다 (빌드 중에 끄면 처음부터 다시 해야 한다)

```bash
tail -n 2 ~/whisper.log
sudo systemctl stop camera-stream 2>/dev/null; pkill -f "[c]amera_server.py"
sudo shutdown -h now
```

## 47 ~ 49쪽 ― I2S 마이크 켜기 · 실습 2-1 마이크 테스트

**Pi**

```bash
arecord -l
arecord -D plughw:CARD=sndrpigooglevoi,DEV=0 -f S16_LE -r 16000 -c 1 -d 5 /tmp/mic_speech.wav
aplay /tmp/mic_speech.wav
python3 ~/test_mic.py
python3 ~/test_mic.py --play
```

## 51 ~ 52쪽 ― 실습 2-2 PTT 버튼 테스트

**Pi**

```bash
~/venv/bin/python3 ~/test_ptt.py
```

## 58 ~ 59쪽 ― 실습 3-1 whisper.cpp 빌드와 단독 확인

**Pi** ― 9쪽에서 시작한 빌드가 끝났는지 확인하고, 2-1 의 녹음 파일로 인식해 본다

```bash
tail -n 2 ~/whisper.log
~/whisper.cpp/build/bin/whisper-cli -m ~/whisper.cpp/models/ggml-base.bin -l ko -nt -f /tmp/mic_speech.wav
python3 ~/PTT_음성인식_단독.py
```

**Pi** ― 빌드를 아직 안 했다면 (약 3분)

```bash
bash ~/whisper_빌드.sh
```

## 63쪽 ― 실습 3-2 음성 인식 D4 확인 (F201)

**PC** ― D4 기기 서버 복사

```powershell
scp page63_음성인식_D4\camera_server.py pi@<PiIP>:~/
```

**Pi** ― 테스트 스크립트를 모두 끈 뒤 기기 서버 실행

```bash
~/venv/bin/python3 ~/camera_server.py
```

**Pi** ― 다른 SSH 창 (PTT 를 누른 채 '오른쪽으로 두 칸 가' → 뗀 뒤 다시 확인)

```bash
curl http://localhost:8080/voice-text
curl http://localhost:8080/voice-text
```

## 67 ~ 69쪽 ― 실습 4-1 A9 음성 중계 (F202)

**PC** ― 기기 서버(63쪽)를 켜 둔 채 실행 → 기기 탭을 열어 두고 PTT 로 말한다

```powershell
cd page67_음성중계_A9
python 대시보드_음성중계.py
```

**PC** ― 기기 없이 확인 (다른 터미널)

```powershell
curl.exe -i "http://127.0.0.1:8000/api/voice-poll?ip=192.0.2.1"
```

## 심화 F205 음성 품질 (선택)

**PC**

```powershell
scp 심화_F205_음성품질\camera_server.py 심화_F205_음성품질\보정_전후_비교.py pi@<PiIP>:~/
```

**Pi**

```bash
python3 ~/보정_전후_비교.py --target "오른쪽으로 두 칸 가" --count 20
~/venv/bin/python3 ~/camera_server.py
```

## 74쪽 ― 부록 A 전체 실행 명령 모음

**PC** ― 서버 (2일차 마지막 단계)

```powershell
cd page67_음성중계_A9
python 대시보드_음성중계.py
```

**Pi**

```bash
~/venv/bin/python3 ~/camera_server.py
curl http://localhost:8080/voice-text
```
