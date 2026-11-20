#!/usr/bin/env bash
# [page 59] whisper.cpp 빌드 · 모델 받기 · 단독 인식 (라즈베리파이). Pi 5 에서 약 3분.
# 수업 시작 때 백그라운드로 돌려 둔다 (강의자료 9쪽) : nohup bash ~/whisper_빌드.sh > ~/whisper.log 2>&1 &
# 다시 실행해도 된다 ― 이미 받은 소스 · 빌드는 건너뛴다.
set -e

sudo apt install -y build-essential cmake git                         # 빌드 도구
[ -d ~/whisper.cpp ] || git clone --depth 1 https://github.com/ggml-org/whisper.cpp ~/whisper.cpp   # 이미 있으면 건너뛴다
cd ~/whisper.cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j4 --config Release
#   결과: ~/whisper.cpp/build/bin/whisper-cli  ← camera_server.py 의 WHISPER_BIN_PATH
#   (실행 파일 이름은 버전에 따라 main → whisper-cli 로 바뀌어 왔다 ― 실제 결과를 확인한다)

./models/download-ggml-model.sh base                                  # ggml-base.bin (142MB)

# page48 test_mic.py 가 녹음한 /tmp/mic_speech.wav 를 한국어로 ― 말한 내용이 나오면 성공
[ -f /tmp/mic_speech.wav ] && ./build/bin/whisper-cli -m models/ggml-base.bin -l ko -nt -f /tmp/mic_speech.wav   # 녹음 파일이 있을 때만
cd ~
echo "whisper 빌드 끝"
