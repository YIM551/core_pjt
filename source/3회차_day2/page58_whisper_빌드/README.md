# page58 ― whisper.cpp 빌드 · 단독 인식

> 강의자료 **58쪽** (실습 3-1) · **59쪽** (모델 선택)  ·  `AI코어프로젝트_3회차_DAY2_r2.pptx`  ·  실행 위치: **라즈베리파이**

whisper.cpp 를 빌드해 녹음 파일을 한국어로 인식하고, PTT + 녹음 + 인식을 서버 없이 이어 본다

## 무엇을 하는가

- `whisper_빌드.sh` ― 빌드(약 3분) · ggml-base.bin(142MB) 다운로드 · page48 의 /tmp/mic_speech.wav 인식
- 파이썬 바인딩 대신 빌드된 바이너리를 subprocess 로 ― 설치가 단순하고, 인식이 실패해도 서버 프로세스에 영향이 없다
- base(2.7초) vs small(10.3초) ― STT 뒤에 YOLO · VLM · LLM 이 더 붙으므로 base 를 기본값으로 (Pi 5, 3초 오디오 실측)
- `PTT_음성인식_단독.py` ― 버튼을 누르는 동안 녹음, 떼면 인식 결과를 찍는다 (기기 서버 D4 에 넣기 전 단계)

## 실행

```bash
bash whisper_빌드.sh                        # 한 줄씩 실행해도 된다
~/whisper.cpp/build/bin/whisper-cli -m ~/whisper.cpp/models/ggml-base.bin -l ko -nt -f /tmp/mic_speech.wav
python3 PTT_음성인식_단독.py
```

## 확인 포인트

- `~/whisper.cpp/build/bin/whisper-cli` 가 생긴다 ― 버전에 따라 이름이 main → whisper-cli 로 바뀌어 왔다
- page48 에서 녹음한 말이 한국어로 나온다
- PTT 로 '오른쪽으로 두 칸 가' → `인식 결과: 오른쪽으로 두 칸 가`

## 이 폴더의 파일

- `whisper_빌드.sh`
- `PTT_음성인식_단독.py`
- `기대출력.txt` ― 라즈베리파이 실물에서 나와야 하는 출력 형식 (코드의 출력 문구 · 강의자료 기준, 실측 아님)

---
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
