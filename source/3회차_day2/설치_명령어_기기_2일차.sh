#!/usr/bin/env bash
# 3회차 2일차 (PJT02) ― 라즈베리파이 준비 명령어. 강의자료 9 ~ 11쪽 (설치 · 체크), 47 · 58쪽. (기기 LLM 설치는 3일차로 옮김)
# whisper.cpp 빌드(약 3분)는 오래 걸리므로 수업 시작 때(9쪽) 백그라운드로 돌려 둔다.
# 1일차 배선(LED · OLED)은 그대로 두고 PTT 버튼(GPIO 23 ↔ GND) · SPH0645 마이크(I2S)를 더한다 ― 전원을 끄고.
# PC 쪽은 새로 설치할 것이 없다.

# ── PC (PowerShell) ― 코드 복사
#   cd C:\work\core_pjt\source\3회차_day2
#   scp page48_마이크_테스트\test_mic.py page51_PTT_버튼_테스트\test_ptt.py page58_whisper_빌드\PTT_음성인식_단독.py pi@<PiIP>:~/
#   scp page58_whisper_빌드\whisper_빌드.sh pi@<PiIP>:~/
#   scp page63_음성인식_D4\camera_server.py pi@<PiIP>:~/

# ── 라즈베리파이 (SSH) ────────────────────────────────────────────────

# [9쪽] 수업 시작 ① I2S 마이크 켜기 ― /boot/firmware/config.txt 맨 아래에 두 줄을 # 없이 넣고 재부팅
#   dtparam=i2s=on
#   dtoverlay=googlevoicehat-soundcard
sudo nano /boot/firmware/config.txt
sudo reboot

# [9쪽] 수업 시작 ② 재부팅 후 다시 ssh → 오래 걸리는 설치를 백그라운드로
sudo apt install -y build-essential cmake git
nohup bash ~/whisper_빌드.sh > ~/whisper.log 2>&1 &

# [11쪽] 설치 확인
tail -n 2 ~/whisper.log
~/venv/bin/python3 -c "import gpiozero, luma.oled; print('ok')"

# [47 ~ 48쪽] I2S 마이크 확인 (config.txt 는 9쪽에서 이미 켰다)
arecord -l                                                            # card N: sndrpigooglevoi
arecord -D plughw:CARD=sndrpigooglevoi,DEV=0 -f S16_LE -r 16000 -c 1 -d 5 ~/test.wav
aplay ~/test.wav
python3 ~/test_mic.py

# [51쪽] PTT 버튼만 확인
~/venv/bin/python3 ~/test_ptt.py

# [58쪽] whisper.cpp 빌드 · base 모델 · 단독 인식 (9쪽에서 시작했다면 확인만 ― 다시 실행해도 된다)
tail -n 2 ~/whisper.log
bash ~/whisper_빌드.sh
python3 ~/PTT_음성인식_단독.py

# 기기 서버 (D1 ~ D4) ― venv 파이썬
~/venv/bin/python3 ~/camera_server.py

# [63쪽] 다른 SSH 창에서 D4 확인
curl http://localhost:8080/voice-text                                 # {"seq": 0, "text": ""}
