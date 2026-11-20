# page29 ― LED 테스트

> 강의자료 **35쪽** (LED 회로) / **36쪽** (실습 2-2) · **37쪽** (동작 결과)  ·  `AI코어프로젝트_3회차_DAY1.pptx`  ·  실행 위치: **라즈베리파이 (venv 파이썬)**

서버 없이 LED 배선과 gpiozero 만 따로 확인한다 (GPIO 17 오른쪽 · GPIO 27 왼쪽)

## 무엇을 하는가

- GPIO → 저항(220 ~ 330Ω) → LED 긴 다리(+) → 짧은 다리(−) → GND
- 기기 서버 D2 와 같은 점멸(0.3초 × 3회)을 서버 없이 돌린다 ― 로그의 ON/OFF 와 불빛이 같은 박자인지 눈으로 본다
- `--pin 17` 처럼 한 핀만 확인할 수도 있다

## 실행

```bash
# PC (PowerShell) ― 코드 복사
scp test_led.py ssafy@<PiIP>:~/

# 라즈베리파이 (SSH)
~/venv/bin/python3 test_led.py
~/venv/bin/python3 test_led.py --pin 17     # 한 핀만
```

## 확인 포인트

- `pin factory:` 줄에 LGPIOFactory 가 찍힌다 (Pi 5)
- 안 켜지면 LED 방향(긴 다리) → 저항 위치 → 핀 번호(물리 11 · 13 · GND 6) 순서로 의심
- 오른쪽 · 왼쪽이 바뀌어 켜지면 선을 바꿔 꽂는다 ― 코드(매핑)를 고치지 않는다
- 기기 서버가 핀을 잡고 있으면 `GPIOPinInUse` ― `pkill -f "[c]amera_server.py"` 로 먼저 끈다

## 이 폴더의 파일

- `test_led.py`
- `기대출력.txt` ― 라즈베리파이 실물에서 나와야 하는 출력 형식 (코드의 출력 문구 · 강의자료 기준, 실측 아님)

---
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
