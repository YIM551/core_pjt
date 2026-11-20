# page63 ― 음성 인식 D4 {seq, text}

> 강의자료 **60쪽** (설계) · **61 ~ 62쪽** (녹음 · 인식 코드) / **63쪽** (실습 3-2)  ·  `AI코어프로젝트_3회차_DAY2_r2.pptx`  ·  실행 위치: **라즈베리파이 (venv 파이썬)**

1일차 기기 서버에 PTT 녹음 → whisper 인식 → [D4] /voice-text 를 더한다

## 무엇을 하는가

- 누름 = arecord 녹음 시작, 뗌 = 녹음 종료 → whisper 는 별도 스레드 (버튼 감시를 막지 않는다)
- D4 는 읽어도 지우지 않는다 ― 새 발화인지는 화면이 seq 증가로 판단한다 (폴링 응답이 유실돼도 발화가 사라지지 않는다)
- seq 는 text 가 준비된 뒤에 text 와 함께 올린다 ― 먼저 올리면 화면이 빈 text 를 새 결과로 본다
- `[BLANK_AUDIO]` · `(음악)` 처럼 괄호로만 된 줄은 버린다 ― 무음 환각 방지
- 0.5초 미만 누름은 whisper 를 돌리지 않고 seq 도 올리지 않는다 ('응' 한 글자도 정상 발화라 글자 수로 거르지 않는다)
- 마이크 · 버튼 · whisper 가 없어도 서버는 죽지 않는다 ― 카메라 · LED · OLED 는 그대로

## 실행

```bash
# PC (PowerShell)
scp camera_server.py pi@<PiIP>:~/

# 라즈베리파이
~/venv/bin/python3 ~/camera_server.py
curl http://localhost:8080/voice-text            # {"seq": 0, "text": ""}
# PTT 를 누른 채 '오른쪽으로 두 칸 가' → 뗌
curl http://localhost:8080/voice-text
```

## 확인 포인트

- 로그 `PTT 버튼 준비 완료 (GPIO 23)`
- `PTT: 녹음 시작 → 녹음 종료 → STT: 결과 seq=1`, D4 가 `{"seq": 1, "text": "오른쪽으로 두 칸 가"}`
- 아주 짧게 누르면 `너무 짧아 무시`, seq 그대로
- 녹음이 시작되지 않으면 arecord 장치 이름, 인식 결과가 비면 whisper 경로 · 모델 파일을 로그에서 확인

## 이 폴더의 파일

- `camera_server.py`
- `기대출력.txt` ― 라즈베리파이 실물에서 나와야 하는 출력 형식 (코드의 출력 문구 · 강의자료 기준, 실측 아님)

---
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
