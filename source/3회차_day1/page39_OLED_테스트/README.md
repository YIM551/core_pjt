# page32 ― SPI OLED 확인

> 강의자료 **38쪽** (SPI 켜기 · 흔한 실수) / **39쪽** (실습 2-3) · **40쪽** (동작 결과)  ·  `AI코어프로젝트_3회차_DAY1.pptx`  ·  실행 위치: **라즈베리파이 (venv 파이썬)**

서버 없이 SPI OLED 배선과 luma.oled 만 따로 확인한다 (DC = GPIO 25, RST = GPIO 22)

## 무엇을 하는가

- `sudo raspi-config` → Interface Options → SPI → Enable 후 `/dev/spidev0.0` 확인
- 테두리 → LEFT → RIGHT 를 1초씩 크게 표시한다 ― 기기 서버 D3 이 그리는 두 글자 (좌우만)
- SPI 는 단방향 ― 핀이 틀려도 코드는 '성공' 으로 끝난다. 화면을 눈으로 확인한다

## 실행

```bash
~/venv/bin/pip install luma.oled
~/venv/bin/python3 test_oled.py
~/venv/bin/python3 test_oled.py --rotate 0        # 모듈을 바로 달았을 때
~/venv/bin/python3 test_oled.py --driver sh1106   # SH1106 칩일 때
```

## 확인 포인트

- 네 변이 모두 보이는 테두리 → 방향 글자 네 개가 화면 가운데에 크게
- 글자가 거꾸로면 `--rotate 0`, 화면 일부가 밀려 보이면 `--driver sh1106`
- RST(GPIO 22)가 LED 핀(17 · 27)과 겹치면 GPIO busy, LED 를 깜빡일 때마다 OLED 가 리셋된다

## 이 폴더의 파일

- `test_oled.py`
- `기대출력.txt` ― 라즈베리파이 실물에서 나와야 하는 출력 형식 (코드의 출력 문구 · 강의자료 기준, 실측 아님)

---
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
