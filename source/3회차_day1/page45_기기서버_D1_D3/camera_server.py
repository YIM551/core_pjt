"""[page 45 ~ 49] 라즈베리파이 기기 서버 D1 ~ D3 ― 카메라 · LED · OLED 를 8080 포트로 제공한다 (PJT01).

대시보드(PC)의 중계 API(A6 · A7 · A8)가 이 서버를 호출한다. 포트 · 경로 · 응답 형식은
3회차 명세서(16-C-3-01)의 D1 ~ D3 과 같아야 한다 (PC 서버의 DEVICE_PORT, DEVICE_*_PATH).
이 파일은 PC 가 아니라 라즈베리파이 본체에서 실행한다.

제공하는 엔드포인트(모두 8080 포트):
  GET  /stream.mjpg          [D1] 카메라 MJPEG 스트림 (640x480, 약 15fps)
  GET  /gpio-blink?pin=      [D2] 요청 핀 LED 3회 점멸 → {"ok": true}
  GET  /oled-display?text=   [D3] 받은 글자(LEFT·RIGHT)를 OLED에 크게 표시 → 200 (OLED 실패해도 200)

역할: 기기는 센서와 출력만 맡는다. 방향 → 핀·글자 매핑, 규칙(R1~R5), 대화 기록(history)은
갖지 않는다(R7, R8).

실행: ~/venv/bin/python3 camera_server.py              (venv 파이썬 ― luma.oled 는 venv 에만 있다)
      ~/venv/bin/python3 camera_server.py --fps 10     [F105] 인식 부하가 크면 해상도 대신 FPS를 낮춘다
확인: 브라우저에서 http://<라즈베리파이IP>:8080/stream.mjpg 접속
      curl "http://localhost:8080/gpio-blink?pin=17"   ·   curl "http://localhost:8080/oled-display?text=LEFT"
"""

import argparse
import io
import json
import logging
import socketserver
import time
from http import server
from pathlib import Path
from threading import Condition, Lock
from urllib.parse import parse_qs, urlsplit

from gpiozero import LED
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput

# main.py:DEVICE_PORT / DEVICE_*_PATH 와 반드시 일치해야 대시보드 중계가 동작한다.
STREAM_PORT = 8080
STREAM_PATH = "/stream.mjpg"

# [F105] 인식 부하가 크면 해상도는 그대로 두고 FPS부터
# 낮춘다(--fps) — 해상도를 낮추면 이 스트림 프레임을 그대로 캡처해 쓰는 YOLO/VLM 인식
# 정확도도 함께 떨어지기 때문이다. 실제 FPS는 대시보드 기기 탭 영상 아래에 표시된다.
STREAM_WIDTH = 640
STREAM_HEIGHT = 480
STREAM_FPS = 15

# [D2] main.py가 방향(left/right)을 핀 번호로 바꿔 넘겨주므로(R8), 여기서는 특정
# 방향/핀 번호를 하드코딩하지 않고 요청받은 핀을 그대로 제어한다.
GPIO_BLINK_PATH = "/gpio-blink"
GPIO_BLINK_COUNT = 3
GPIO_BLINK_INTERVAL_SECONDS = 0.3

# --- SPI OLED [D3] -----------------------------------------------------------
OLED_DISPLAY_PATH = "/oled-display"
# 한 번에 표시할 수 있는 글자 수. 이보다 긴 요청은 400 이다.
OLED_MAX_TEXT_LENGTH = 16

# SSD1306 128x64를 가정한다. 실물이 SH1106 등 다른 칩이면 아래 드라이버 임포트와
# 함께 바꿔야 한다.
OLED_WIDTH = 128
OLED_HEIGHT = 64
# SPI0 기본 포트. /dev/spidev0.0에 대응한다.
OLED_SPI_PORT = 0
OLED_SPI_DEVICE = 0
# DC = GPIO 25(물리 22번 핀), RST = GPIO 22(물리 15번 핀).
# RST 는 LED 핀(main.py:DIRECTION_GPIO_PIN 의 17 · 27)과 겹치면 안 된다 — 같은 핀을
# luma(OLED 리셋)와 gpiozero(LED)가 함께 열면 "GPIO busy"로 실패하고, LED 를 깜빡일 때마다
# OLED 가 리셋된다.
OLED_GPIO_DC = 25
OLED_GPIO_RST = 22

# 화면 회전. OLED 모듈이 거꾸로 장착돼 있어 180도 돌려 출력한다.
# 0=0도, 1=90도, 2=180도, 3=270도. 나중에 모듈을 바로 달면 이 값만 0으로 되돌린다.
OLED_ROTATE = 2

# 기동 화면 문구. 빈 화면으로 두면 "OLED가 꺼진 것"인지 "정상 대기 중"인지 구분되지 않는다.
OLED_START_TEXT = "start"
# PIL 기본 비트맵 폰트는 128x64 화면에서 글씨가 너무 작다. 시스템에 있는 TrueType
# 폰트를 우선 찾아 쓰고, 하나도 없으면 기본 폰트로 폴백한다.
OLED_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)
# 글자를 화면 폭에 맞춰 가장 크게 그린다. 이 크기부터 줄여 가며 맞는 크기를 찾는다.
OLED_MAX_FONT_SIZE = 40
OLED_MARGIN = 4

logging.basicConfig(level=logging.INFO)

# 요청마다 LED(pin)을 새로 만들고 닫는 대신 핀별로 하나만 만들어 재사용한다. 매번 열고
# 닫으면 lgpio 핸들이 제때 반환되지 않아 다음 요청이 "GPIO busy"로 실패할 수 있다.
# 여러 요청이 겹쳐 같은 LED를 동시에 켜고 끄지 않도록 _gpio_lock으로 직렬화한다.
_led_cache = {}
_gpio_lock = Lock()


def _get_led(pin):
    if pin not in _led_cache:
        _led_cache[pin] = LED(pin)
    return _led_cache[pin]


# ---------------------------------------------------------------------------
# SPI OLED [D3]
#
# OLED는 출력 장치 중 하나일 뿐이다. 라이브러리가 없거나 배선이 안 됐거나 초기화에
# 실패해도 카메라/LED는 그대로 동작해야 하고, /oled-display 요청도 실패시키지
# 않는다(R6: OLED 표시 실패는 오류로 보지 않는다).
# ---------------------------------------------------------------------------

_oled_device = None
# 한 번 실패하면 다시 시도하지 않는다. 배선을 나중에 하면 서버를 재시작해야 인식된다.
_oled_init_failed = False
_oled_lock = Lock()


def get_oled_device():
    """SPI OLED 장치를 최초 요청 시 한 번만 초기화한다(실패하면 None)."""
    global _oled_device, _oled_init_failed
    if _oled_device is None and not _oled_init_failed:
        try:
            from luma.core.interface.serial import spi
            from luma.oled.device import ssd1306

            serial = spi(
                port=OLED_SPI_PORT,
                device=OLED_SPI_DEVICE,
                gpio_DC=OLED_GPIO_DC,
                gpio_RST=OLED_GPIO_RST,
            )
            _oled_device = ssd1306(
                serial, width=OLED_WIDTH, height=OLED_HEIGHT, rotate=OLED_ROTATE
            )
            logging.info("OLED: 초기화 완료 (%dx%d, rotate=%d)", OLED_WIDTH, OLED_HEIGHT, OLED_ROTATE)
        except Exception:
            logging.exception("OLED: 초기화 실패 - OLED 없이 계속 진행한다")
            _oled_init_failed = True
    return _oled_device


def _load_oled_font(size):
    """OLED에 쓸 TrueType 폰트를 찾는다. 하나도 없으면 None(PIL 기본 폰트)."""
    from PIL import ImageFont

    for candidate in OLED_FONT_CANDIDATES:
        path = Path(candidate)
        if not path.exists():
            continue
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            continue
    return None


def _build_text_image(text):
    """글자를 화면 폭·높이에 들어가는 가장 큰 크기로 가운데에 그린다."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT), 0)
    draw = ImageDraw.Draw(image)
    font = None
    for size in range(OLED_MAX_FONT_SIZE, 7, -2):
        candidate = _load_oled_font(size)
        if candidate is None:
            break
        bbox = draw.textbbox((0, 0), text, font=candidate)
        if bbox[2] - bbox[0] <= OLED_WIDTH - OLED_MARGIN * 2 and bbox[3] - bbox[1] <= OLED_HEIGHT - OLED_MARGIN * 2:
            font = candidate
            break
    if font is None:
        logging.info("OLED: TrueType 폰트를 찾지 못해 기본 폰트를 쓴다(글씨가 작게 보인다)")
        font = ImageFont.load_default()
    # textbbox는 글자 자체의 실제 경계를 돌려주므로, 그 오프셋까지 빼야 시각적으로
    # 정확히 가운데에 놓인다(폰트마다 위쪽 여백이 다르다).
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (OLED_WIDTH - (bbox[2] - bbox[0])) // 2 - bbox[0]
    y = (OLED_HEIGHT - (bbox[3] - bbox[1])) // 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=1)
    return image


def show_oled_text(text):
    """OLED에 글자를 표시한다. 결과를 문자열로 돌려주고, 어떤 실패도 예외로 올리지 않는다."""
    device = get_oled_device()
    if device is None:
        return "unavailable"
    try:
        # 요청이 겹쳐 들어와도 화면 갱신이 뒤섞이지 않게 직렬화한다.
        with _oled_lock:
            device.display(_build_text_image(text))
    except Exception:
        logging.exception("OLED: 화면 갱신 실패 (text=%s)", text)
        return "error"
    logging.info("OLED: %s 표시 완료", text)
    return "shown"


class StreamingOutput(io.BufferedIOBase):
    """JpegEncoder가 인코딩한 프레임을 조건 변수로 넘겨받아 최신 프레임만 보관한다.

    여러 클라이언트(스트리밍 요청 스레드)가 같은 최신 프레임을 동시에 읽어야 하므로,
    프레임을 큐에 쌓지 않고 하나만 유지한 채 Condition으로 새 프레임 도착을 알린다.
    """

    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == STREAM_PATH:
            self._handle_stream()
        elif parsed.path == GPIO_BLINK_PATH:
            self._handle_gpio_blink(parse_qs(parsed.query))
        elif parsed.path == OLED_DISPLAY_PATH:
            self._handle_oled_display(parse_qs(parsed.query))
        else:
            self.send_error(404)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_stream(self):
        """[D1] MJPEG 스트림."""
        self.send_response(200)
        self.send_header("Age", "0")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        # index.html의 MJPEG 파서가 Content-Type에서 boundary= 값을 추출해 프레임 구분에
        # 쓰므로, 이 문자열 형식을 임의로 바꾸면 안 된다.
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
        self.end_headers()
        try:
            while True:
                with output.condition:
                    output.condition.wait()
                    frame = output.frame
                self.wfile.write(b"--FRAME\r\n")
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(frame)))
                self.end_headers()
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            logging.info("Client disconnected: %s", self.client_address)

    def _handle_gpio_blink(self, query):
        """[D2] 요청 핀 3회 점멸 → {"ok": true}. pin 이 숫자가 아니면 400."""
        pin_values = query.get("pin")
        if not pin_values or not pin_values[0].isdigit():
            self._send_json({"error": "invalid_request"}, status=400)
            return
        pin = int(pin_values[0])
        logging.info("GPIO blink requested: pin=%d", pin)

        # _gpio_lock으로 LED 캐시 조회/생성과 on-off 시퀀스 전체를 직렬화해, 겹쳐 들어온
        # 요청이 같은 LED 객체를 동시에 만지거나 같은 핀을 중복 오픈하지 않게 한다.
        with _gpio_lock:
            led = _get_led(pin)
            for _ in range(GPIO_BLINK_COUNT):
                led.on()
                time.sleep(GPIO_BLINK_INTERVAL_SECONDS)
                led.off()
                time.sleep(GPIO_BLINK_INTERVAL_SECONDS)
        logging.info("GPIO blink done: pin=%d", pin)
        self._send_json({"ok": True})

    def _handle_oled_display(self, query):
        """[D3] 받은 글자를 OLED에 크게 표시한다.

        방향 → 글자 매핑(left → LEFT 등)은 PC가 정하므로 여기서는 받은 글자를 그대로 쓴다.
        글자가 없거나 너무 길면 400. OLED가 없거나 표시에 실패해도 200이고, 실제로
        무엇이 됐는지는 `oled` 필드로 남긴다(R6).
        """
        text_values = query.get("text")
        text = text_values[0].strip() if text_values else ""
        if not text or len(text) > OLED_MAX_TEXT_LENGTH:
            self._send_json({"error": "invalid_request"}, status=400)
            return
        self._send_json({"ok": True, "oled": show_oled_text(text)})

    def log_message(self, format, *args):
        pass


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


parser = argparse.ArgumentParser(description="라즈베리파이 기기 서버 (D1~D3)")
parser.add_argument("--fps", type=int, default=STREAM_FPS,
                    help=f"카메라 FPS (기본 {STREAM_FPS}). 부하가 크면 해상도 대신 이 값을 낮춘다")
cli = parser.parse_args()
stream_fps = max(1, min(cli.fps, 30))

picam2 = Picamera2()
video_config = picam2.create_video_configuration(
    main={"size": (STREAM_WIDTH, STREAM_HEIGHT)},
    controls={"FrameDurationLimits": (int(1_000_000 / stream_fps), int(1_000_000 / stream_fps))},
)
picam2.configure(video_config)

output = StreamingOutput()
picam2.start_recording(JpegEncoder(), FileOutput(output))

# 기동 시 OLED를 기동 화면("start")으로 덮어쓴다. 이렇게 하지 않으면 이전 실행에서
# 남은 방향 글자가 그대로 떠 있어 지금 상태를 오해하게 된다.
logging.info("OLED: 기동 화면 표시 -> %s", show_oled_text(OLED_START_TEXT))

try:
    logging.info("Streaming on http://0.0.0.0:%d%s (%dx%d, %dfps)",
                 STREAM_PORT, STREAM_PATH, STREAM_WIDTH, STREAM_HEIGHT, stream_fps)
    StreamingServer(("", STREAM_PORT), StreamingHandler).serve_forever()
except KeyboardInterrupt:
    pass
finally:
    picam2.stop_recording()
    # 방향 글자가 남은 채로 서버가 내려가면 다음 기동까지 그대로 켜져 있으므로 지우고 나간다.
    if _oled_device is not None:
        try:
            _oled_device.clear()
        except Exception:
            logging.exception("OLED: 종료 시 화면 정리 실패")
    for led in _led_cache.values():
        led.close()
