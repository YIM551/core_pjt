# page48 ― I2S 마이크 켜기 · 녹음 확인

> 강의자료 **47쪽** (I2S 켜기) / **48쪽** (실습 2-1) · **49쪽** (동작 결과)  ·  `AI코어프로젝트_3회차_DAY2_r2.pptx`  ·  실행 위치: **라즈베리파이**

SPH0645 I2S 마이크를 OS 에서 켜고, 서버 없이 녹음이 되는지 소리 크기로 확인한다

## 무엇을 하는가

- I2S 는 디지털 MEMS 마이크 ― `/boot/firmware/config.txt` 에 `dtparam=i2s=on` · `dtoverlay=googlevoicehat-soundcard` 를 넣고 재부팅해야 사운드 카드로 보인다
- 장치는 카드 번호가 아니라 이름으로 ― `plughw:CARD=sndrpigooglevoi,DEV=0` (기기 서버 VOICE_ALSA_DEVICE 와 같다)
- 16kHz · mono · S16_LE 고정 ― whisper.cpp 가 기대하는 형식
- 조용히 2초 / 말하기 3초를 녹음해 RMS 차이가 10dB 이상이면 PASS

## 실행

```bash
arecord -l                                # card N: sndrpigooglevoi
arecord -D plughw:CARD=sndrpigooglevoi,DEV=0 -f S16_LE -r 16000 -c 1 -d 5 /tmp/mic_speech.wav && aplay /tmp/mic_speech.wav
python3 test_mic.py
python3 test_mic.py --min-gain-db 3       # 현장 점검 예시: 말하기 RMS가 3dB 이상 증가하면 PASS
python3 test_mic.py --play
```

## 확인 포인트

- `arecord -l` 에 sndrpigooglevoi 가 보인다 (안 보이면 config.txt 줄 앞의 # 확인)
- 기본 실행은 수업 기준 10dB를 적용한다. `--min-gain-db`로 양수 값을 지정하면 출력에 실제 차이와 적용 기준이 함께 표시된다.
- 소리가 안 잡히면 코드가 아니라 리눅스 오디오 설정 문제 ― 오버레이를 바꿔 가며 재시도
- `/tmp/mic_speech.wav` 는 page58 의 whisper 단독 확인에 다시 쓴다

## 이 폴더의 파일

- `test_mic.py`
- `기대출력.txt` ― 라즈베리파이 실물에서 나와야 하는 출력 형식 (코드의 출력 문구 · 강의자료 기준, 실측 아님)

---
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
