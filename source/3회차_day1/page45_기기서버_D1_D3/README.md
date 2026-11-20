# page38 ― 기기 서버 D1 ~ D3

> 강의자료 **45쪽** (실습 3-1 구조) · **46 ~ 47쪽** (D2 · D3 코드) / **48쪽** (실습 3-2) · **49쪽** (동작 결과)  ·  `AI코어프로젝트_3회차_DAY1.pptx`  ·  실행 위치: **라즈베리파이 (venv 파이썬)**

camera_server.py 하나로 8080 포트에서 영상(D1) · LED(D2) · OLED(D3)를 제공한다

## 무엇을 하는가

- `StreamingOutput` ― 최신 프레임 하나만 보관하고 Condition 으로 알린다 (큐에 쌓지 않는다)
- `ThreadingMixIn` ― 요청마다 스레드. 끝나지 않는 MJPEG 스트림을 보는 동안에도 LED 요청이 처리된다
- D2 · D3 은 받은 핀 · 글자만 출력한다 ― 방향 → 핀 · 글자 매핑은 PC 가 정한다 (R8)
- OLED 가 없거나 실패해도 D3 은 200, 결과는 `oled` 필드(shown · unavailable · error) (R6)
- `--fps` 옵션은 심화 F105 (해상도 대신 FPS 를 낮춘다)

## 실행

```bash
# PC (PowerShell) ― 코드 복사
scp camera_server.py ssafy@<PiIP>:~/

# 라즈베리파이
~/venv/bin/python3 ~/camera_server.py      # OLED 에 'start'
curl "http://localhost:8080/gpio-blink?pin=17"
curl "http://localhost:8080/gpio-blink?pin=27"
curl "http://localhost:8080/oled-display?text=LEFT"
pkill -f "[c]amera_server.py"               # SSH 로 끌 때 ― 대괄호가 없으면 SSH 세션까지 끊긴다
```

## 확인 포인트

- PC 브라우저 `http://<PiIP>:8080/stream.mjpg` 에 영상 (D1)
- LED 3회 점멸 + `{"ok": true}` (D2), OLED 에 LEFT + `{"ok": true, "oled": "shown"}` (D3)
- LED 를 깜빡여도 OLED 가 리셋되지 않는다
- 시스템 `python3` 로 띄우면 OLED 가 안 나온다 (luma.oled 는 venv 에만 있다)

## 이 폴더의 파일

- `camera_server.py`
- `기대출력.txt` ― 라즈베리파이 실물에서 나와야 하는 출력 형식 (코드의 출력 문구 · 강의자료 기준, 실측 아님)

---
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
