"""방향 LED 단독 테스트 ― camera_server.py 없이 LED 배선과 gpiozero 만 확인한다.

실행: ~/venv/bin/python3 test_led.py              (오른쪽 GPIO 17 → 왼쪽 GPIO 27 순서)
      ~/venv/bin/python3 test_led.py --pin 17     (한 핀만)
확인: 로그의 ON/OFF 타이밍에 맞춰 LED 가 3번씩 깜빡이는지 눈으로 본다.
      점멸 간격 0.3초 · 3회는 기기 서버 D2(/gpio-blink)와 같다.

주의: camera_server.py 가 돌고 있으면 핀을 잡고 있어 "GPIO busy" 가 난다. 먼저 끈다.
"""

import argparse
import time

from gpiozero import LED, Device

# main.py:DIRECTION_GPIO_PIN 과 같은 매핑 (R8)
PINS = {17: "오른쪽", 27: "왼쪽"}
BLINK_COUNT = 3
BLINK_INTERVAL_SECONDS = 0.3

parser = argparse.ArgumentParser(description="방향 LED 단독 테스트")
parser.add_argument("--pin", type=int, help="한 핀만 확인 (BCM 번호)")
only_pin = parser.parse_args().pin
pins = [only_pin] if only_pin else list(PINS)

# Pi 5 는 lgpio 핀 팩토리가 잡혀야 한다. 여기서 예외가 나면 배선이 아니라 라이브러리 문제다.
print("pin factory:", Device.pin_factory)

failed = []
for pin in pins:
    label = f"GPIO {pin} ({PINS.get(pin, '?')})"
    print(f"--- {label} ---")
    try:
        led = LED(pin)
    except Exception as exc:
        print(f"  LED 생성 실패: {type(exc).__name__}: {exc}")
        failed.append(pin)
        continue
    try:
        for i in range(BLINK_COUNT):
            led.on()
            print(f"  [{i + 1}/{BLINK_COUNT}] ON")
            time.sleep(BLINK_INTERVAL_SECONDS)
            led.off()
            print(f"  [{i + 1}/{BLINK_COUNT}] OFF")
            time.sleep(BLINK_INTERVAL_SECONDS)
    finally:
        led.close()

if failed:
    print(f"FAIL  {failed} ― 다른 프로그램이 핀을 쓰는지(camera_server.py) 확인한다")
    raise SystemExit(1)
print("코드는 끝까지 돌았다. LED 가 안 켜졌다면 배선 문제다:")
print("  ① 긴 다리(+)가 GPIO 쪽인가  ② 저항이 직렬로 들어갔나  ③ 물리 핀 11(17) · 13(27) · GND 6 인가")
print("PASS  (눈으로 깜빡임을 확인했다면)")
