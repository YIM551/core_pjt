"""SPI OLED 단독 테스트 ― camera_server.py 없이 OLED 배선과 luma.oled 만 확인한다.

실행: ~/venv/bin/python3 test_oled.py                 (SSD1306 128x64, 180도 회전 ― 기기 서버와 같은 설정)
      ~/venv/bin/python3 test_oled.py --rotate 0      (모듈을 바로 달았을 때)
      ~/venv/bin/python3 test_oled.py --driver sh1106 (SH1106 칩일 때)
확인: 테두리 → LEFT → RIGHT 가 1초씩 크게 보이고, 마지막에 화면이 지워진다.

주의: SPI 는 단방향이라 핀이 틀려도 코드는 "성공" 으로 끝난다. 화면을 눈으로 확인한다.
      camera_server.py 가 돌고 있으면 같은 SPI · RST 핀을 잡고 있어 실패한다. 먼저 끈다.
"""

import argparse
import os
import time

from luma.core.interface.serial import spi
from luma.core.render import canvas
from PIL import ImageFont

# camera_server.py 의 OLED_* 상수와 같은 값
OLED_GPIO_DC = 25         # 물리 22
OLED_GPIO_RST = 22        # 물리 15 ― LED 핀 17 · 27 과 겹치면 안 된다
WIDTH, HEIGHT = 128, 64
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TEXTS = ["LEFT", "RIGHT"]                    # main.py:DIRECTION_OLED_TEXT 의 두 글자 (좌우만)

parser = argparse.ArgumentParser(description="SPI OLED 단독 테스트")
parser.add_argument("--rotate", type=int, default=2, choices=[0, 1, 2, 3], help="0=0도 … 2=180도 (기본 2)")
parser.add_argument("--driver", default="ssd1306", choices=["ssd1306", "sh1106"])
args = parser.parse_args()

# ① SPI 가 켜져 있어야 /dev/spidev0.0 이 생긴다.
if not os.path.exists("/dev/spidev0.0"):
    print("FAIL  /dev/spidev0.0 없음 ― sudo raspi-config → Interface Options → SPI → Enable 후 재부팅")
    raise SystemExit(1)

# ② 드라이버 초기화 ― 여기서 GPIO busy 가 나면 RST/DC 핀을 다른 프로그램이 쓰고 있다.
if args.driver == "sh1106":
    from luma.oled.device import sh1106 as driver
else:
    from luma.oled.device import ssd1306 as driver
serial = spi(port=0, device=0, gpio_DC=OLED_GPIO_DC, gpio_RST=OLED_GPIO_RST)
device = driver(serial, width=WIDTH, height=HEIGHT, rotate=args.rotate)
print(f"초기화 완료: {args.driver} {WIDTH}x{HEIGHT}, rotate={args.rotate}")

try:
    font = ImageFont.truetype(FONT_PATH, 30)
except OSError:
    print("WARN  DejaVu 폰트가 없어 기본 폰트로 그린다 (글씨가 작다) ― sudo apt install fonts-dejavu-core")
    font = ImageFont.load_default()

# ③ 테두리 ― 네 변이 모두 보여야 해상도 · 칩 설정이 맞다 (한쪽이 잘리면 --driver 를 바꾼다)
with canvas(device) as draw:
    draw.rectangle(device.bounding_box, outline="white")
print("테두리 표시 ― 네 변이 모두 보이는가?")
time.sleep(1.5)

# ④ 방향 글자 ― 기기 서버 D3 가 그리는 것과 같은 두 글자
for text in TEXTS:
    with canvas(device) as draw:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        x = (WIDTH - (right - left)) // 2 - left
        y = (HEIGHT - (bottom - top)) // 2 - top
        draw.text((x, y), text, font=font, fill="white")
    print(f"표시: {text}")
    time.sleep(1.0)

device.clear()
print("코드는 끝까지 돌았다. 화면이 안 나왔다면: ① VCC 가 3.3V 인가 ② DC(물리 22) · RST(물리 15) ③ CS(물리 24)")
print("글자가 거꾸로면 --rotate 0, 화면 일부가 밀려 보이면 --driver sh1106")
print("PASS  (눈으로 글자를 확인했다면)")
