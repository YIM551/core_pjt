"""[page 14 · 15] 라즈베리파이 기기 서버 D1 ~ D4 ― PTT 음성 인식 결과를 {seq, text} 로 제공한다 (PJT02).

1일차 page38 기기 서버(D1 ~ D3)에 PTT 녹음 → whisper.cpp 인식 → [D4] /voice-text 를 더한다.
대시보드(PC)의 A9(/api/voice-poll)가 1초마다 D4 를 중계한다. 이 파일은 라즈베리파이 본체에서 실행한다.

제공하는 엔드포인트(모두 8080 포트):
  GET  /stream.mjpg          [D1] 카메라 MJPEG 스트림 (640x480, 약 15fps)
  GET  /gpio-blink?pin=      [D2] 요청 핀 LED 3회 점멸 → {"ok": true}
  GET  /oled-display?text=   [D3] 받은 글자(LEFT·RIGHT·UP·DOWN)를 OLED에 크게 표시 → 200 (OLED 실패해도 200)
  GET  /voice-text           [D4] 가장 최근 PTT 음성 인식 결과 {seq, text} ― 읽어도 지우지 않는다

PTT: 버튼 누름 = arecord 녹음 시작, 뗌 = 녹음 종료 → 별도 스레드에서 whisper.cpp 인식 → seq += 1
마이크 · 버튼 · whisper 가 없어도 서버는 죽지 않는다 ― 카메라 · LED · OLED 는 그대로 동작한다.

실행: ~/venv/bin/python3 camera_server.py              (venv 파이썬으로 실행)
확인: curl http://localhost:8080/voice-text            → {"seq": 0, "text": ""}
      PTT 를 누른 채 "오른쪽으로 두 칸 가" → 뗌 → 다시 curl → {"seq": 1, "text": "오른쪽으로 두 칸 가"}
"""

import argparse
import io
import json
import logging
import os
import socketserver
import subprocess
import tempfile
import time
from http import server
from pathlib import Path
from threading import Condition, Event, Lock, Thread
from urllib.parse import parse_qs, urlsplit

from gpiozero import InputDevice, LED
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput

# main.py:DEVICE_PORT / DEVICE_*_PATH 와 반드시 일치해야 대시보드 중계가 동작한다.
STREAM_PORT = 8080
STREAM_PATH = "/stream.mjpg"

# [F105] 온디바이스 LLM·STT와 CPU를 공유해 부하가 크면 해상도는 그대로 두고 FPS부터
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

# --- PTT(Push-To-Talk) 음성 입력 [D4] -------------------------------------
VOICE_TEXT_PATH = "/voice-text"

# PTT 버튼은 GPIO 23(물리 16번 핀)이다.
# 내부 풀업(pull_up=True)을 쓰므로 버튼 반대쪽은 GND에 연결한다(누르면 LOW).
VOICE_BUTTON_PIN = 23
# gpiozero Button은 Pi 5 에서 이벤트 등록(lgpio gpio_claim_alert)이 'bad event request'로
# 실패한다. 그래서 InputDevice로 핀을 주기적으로 읽는다. 연속 샘플이 같아야 상태를
# 바꾸므로 채터링도 함께 걸러진다(20ms x 2 = 40ms).
VOICE_BUTTON_POLL_SECONDS = 0.02
VOICE_BUTTON_STABLE_SAMPLES = 2

# arecord로 녹음할 때 쓰는 ALSA 장치. 카드 번호는 사운드 장치 구성에 따라 바뀌므로
# `arecord -l`에 나오는 카드 이름으로 지정한다.
VOICE_ALSA_DEVICE = "plughw:CARD=sndrpigooglevoi,DEV=0"
# whisper.cpp가 16kHz mono를 기대하므로 이 포맷은 고정이다.
VOICE_SAMPLE_RATE = 16000
# [F205] 이보다 짧게 누른 버튼은 실수로 본다 — whisper를 돌리지 않고 seq도 올리지 않는다.
# 글자 수로 거르지 않는 이유: 되묻기에 답하는 '응'(한 글자)도 정상 발화다(F302).
VOICE_MIN_SECONDS = 0.5

# whisper.cpp는 파이썬 바인딩 대신 빌드된 바이너리를 subprocess로 호출한다.
# 아래 경로/이름은 whisper.cpp 버전에 따라 달라져 왔으므로(main → whisper-cli, make →
# cmake) 실물에서 실제 빌드 결과를 확인해 맞춘다.
WHISPER_DIR = Path.home() / "whisper.cpp"
WHISPER_BIN_PATH = WHISPER_DIR / "build" / "bin" / "whisper-cli"
WHISPER_MODEL_DIR = WHISPER_DIR / "models"
# Pi 5 실측(3초 오디오 기준): small = 10.3초, base = 2.7초로 약 3.8배 차이.
# 음성 프롬프트 뒤에 YOLO/VLM/LLM이 더 붙는 구조라 STT에서만 10초를 쓸 수 없어 base를
# 기본값으로 둔다. 인식 정확도가 부족하면 "small"로 바꾼다.
WHISPER_MODEL_SIZE = "base"
WHISPER_LANGUAGE = "ko"
# 인식이 이 시간을 넘기면 포기한다. 무한정 기다리면 STT 스레드가 영영 남는다.
WHISPER_TIMEOUT_SECONDS = 120
# 녹음 종료(terminate) 후 arecord가 파일을 닫을 때까지 기다리는 시간.
VOICE_RECORD_STOP_TIMEOUT_SECONDS = 5

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


# 가장 최근 음성 인식 결과. 대시보드가 1초 간격으로 /voice-text를 폴링하면서 seq가
# 커졌는지로 "새 발화인지"를 판별하므로, 값을 pop 하지 않고 계속 최신값을 그대로
# 돌려준다. seq는 STT가 끝나 text가 준비된 시점에 text와 함께 한 번에 올린다 — 먼저
# 올리면 대시보드가 아직 비어 있는 text를 새 결과로 보게 된다.
_voice_state = {"seq": 0, "text": ""}
# 녹음 중인 arecord 프로세스와 그 출력 파일, 녹음 시작 시각. 버튼 콜백 스레드와 요청
# 스레드가 모두 접근하므로 _voice_lock으로 보호한다.
_recording = {"process": None, "path": None, "started": 0.0}
_voice_lock = Lock()
_voice_stop = Event()


def _watch_voice_button(button):
    """PTT 핀을 주기적으로 읽어 눌림 · 뗌이 확정되면 녹음을 시작 · 종료한다."""
    pressed = False
    changed_samples = 0
    while not _voice_stop.wait(VOICE_BUTTON_POLL_SECONDS):
        changed_samples = changed_samples + 1 if button.is_active != pressed else 0
        if changed_samples >= VOICE_BUTTON_STABLE_SAMPLES:
            pressed = not pressed
            changed_samples = 0
            if pressed:
                _start_recording()
            else:
                _stop_recording()


def _start_recording():
    """PTT 버튼을 누른 순간 arecord로 녹음을 시작한다(버튼 감시 스레드에서 호출)."""
    with _voice_lock:
        if _recording["process"] is not None:
            # 연타로 시작이 중복 호출된 경우. 이미 도는 녹음을 그대로 둔다.
            logging.info("PTT: 이미 녹음 중이므로 무시")
            return
        fd, path = tempfile.mkstemp(prefix="ptt_", suffix=".wav")
        os.close(fd)
        command = [
            "arecord",
            "-D", VOICE_ALSA_DEVICE,
            "-f", "S16_LE",
            "-r", str(VOICE_SAMPLE_RATE),
            "-c", "1",
            path,
        ]
        try:
            process = subprocess.Popen(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except (OSError, ValueError):
            # arecord가 없거나(alsa-utils 미설치) 실행할 수 없는 경우. 마이크가 없어도
            # 카메라/GPIO는 계속 동작해야 하므로 서버를 죽이지 않고 로그만 남긴다.
            logging.exception("PTT: arecord 실행 실패 (alsa-utils 설치 · I2S 마이크 설정 확인)")
            _safe_unlink(path)
            return
        _recording["process"] = process
        _recording["path"] = path
        _recording["started"] = time.monotonic()
    logging.info("PTT: 녹음 시작 -> %s", path)


def _stop_recording():
    """PTT 버튼을 뗀 순간 녹음을 끝내고, STT는 별도 스레드로 넘긴다."""
    with _voice_lock:
        process = _recording["process"]
        path = _recording["path"]
        duration = time.monotonic() - _recording["started"]
        _recording["process"] = None
        _recording["path"] = None
    if process is None:
        return

    process.terminate()
    try:
        process.wait(timeout=VOICE_RECORD_STOP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        logging.warning("PTT: arecord가 종료되지 않아 강제 종료한다")
        process.kill()
        process.wait()

    if duration < VOICE_MIN_SECONDS:                  # [F205] 너무 짧은 발화는 보내지 않는다
        logging.info("PTT: %.2f초 — 너무 짧아 무시", duration)
        _safe_unlink(path)
        return
    logging.info("PTT: 녹음 종료 (%.1f초) -> %s", duration, path)

    # whisper.cpp 실행은 수 초 이상 걸리므로 콜백 스레드를 잡아두지 않고 넘긴다.
    Thread(target=_transcribe_worker, args=(path,), daemon=True).start()


def _transcribe_worker(wav_path):
    """녹음 파일을 whisper.cpp로 인식해 _voice_state에 반영하고 파일을 정리한다."""
    try:
        text = _run_whisper(wav_path)
    except Exception:
        # STT가 실패해도 서버는 계속 살아 있어야 한다. 결과는 빈 문자열로 두고, 대시보드는
        # "빈 인식 결과는 프롬프트창을 채우지 않는다"는 규칙으로 이를 무시한다.
        logging.exception("STT: whisper 실행 중 예외")
        text = ""
    finally:
        _safe_unlink(wav_path)

    with _voice_lock:
        _voice_state["seq"] += 1
        _voice_state["text"] = text
        seq = _voice_state["seq"]
    logging.info("STT: 결과 seq=%d text=%r", seq, text)


def _run_whisper(wav_path):
    """whisper.cpp 바이너리를 실행해 인식된 텍스트를 돌려준다(실패 시 빈 문자열)."""
    model_path = WHISPER_MODEL_DIR / f"ggml-{WHISPER_MODEL_SIZE}.bin"
    if not WHISPER_BIN_PATH.exists() or not model_path.exists():
        logging.error(
            "STT: whisper 바이너리/모델을 찾을 수 없다 (bin=%s, model=%s). whisper.cpp 빌드와 ggml-base.bin 다운로드 확인",
            WHISPER_BIN_PATH, model_path,
        )
        return ""

    command = [
        str(WHISPER_BIN_PATH),
        "-m", str(model_path),
        "-l", WHISPER_LANGUAGE,
        "-nt",                       # 타임스탬프 없이 인식 텍스트만 출력
        "-f", wav_path,
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=WHISPER_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired:
        logging.error("STT: whisper 실행이 %d초를 넘겨 중단", WHISPER_TIMEOUT_SECONDS)
        return ""
    if result.returncode != 0:
        logging.error("STT: whisper 실패 (returncode=%d) %s", result.returncode, result.stderr.strip())
        return ""
    return _clean_whisper_output(result.stdout)


def _clean_whisper_output(raw_text):
    """whisper 출력에서 실제 발화 텍스트만 남긴다.

    whisper.cpp는 무음 구간에 [BLANK_AUDIO], (음악) 같은 비발화 태그를 출력한다. 이런
    줄만 있는 결과는 사용자가 아무 말도 하지 않은 것이므로 빈 문자열로 접어, 대시보드가
    "빈 인식 결과"로 보고 그냥 무시하게 한다.
    """
    lines = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            continue
        if stripped.startswith("(") and stripped.endswith(")"):
            continue
        lines.append(stripped)
    return " ".join(" ".join(lines).split())


def _safe_unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# SPI OLED [D3]
#
# OLED는 출력 장치 중 하나일 뿐이다. 라이브러리가 없거나 배선이 안 됐거나 초기화에
# 실패해도 카메라/음성/LED는 그대로 동작해야 하고, /oled-display 요청도 실패시키지
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
        elif parsed.path == VOICE_TEXT_PATH:
            self._handle_voice_text()
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

    def _handle_voice_text(self):
        """[D4] 가장 최근 음성 인식 결과 {seq, text}를 그대로 돌려준다.

        값을 소비(pop)하지 않고 최신값을 계속 반환한다 — "새 결과인지"의 판단은 호출
        측(대시보드)이 seq를 비교해서 한다. 마이크나 whisper가 준비되지 않은 상태에서도
        초기값(seq=0, text="")을 정상 응답한다.
        """
        with _voice_lock:
            payload = {"seq": _voice_state["seq"], "text": _voice_state["text"]}
        self._send_json(payload)

    def log_message(self, format, *args):
        pass


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


parser = argparse.ArgumentParser(description="라즈베리파이 기기 서버 (D1~D4)")
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

# PTT 버튼. 버튼이 아직 배선되지 않았거나 핀을 열 수 없어도 카메라/GPIO 기능은 그대로 동작해야
# 하므로, 초기화 실패는 로그만 남기고 넘어간다.
voice_button = None
voice_button_thread = None
try:
    voice_button = InputDevice(VOICE_BUTTON_PIN, pull_up=True)
    voice_button_thread = Thread(target=_watch_voice_button, args=(voice_button,), daemon=True)
    voice_button_thread.start()
    logging.info("PTT 버튼 준비 완료 (GPIO %d)", VOICE_BUTTON_PIN)
except Exception:
    logging.exception("PTT 버튼 초기화 실패 - 음성 입력 없이 계속 진행한다")

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
    _voice_stop.set()
    if voice_button_thread is not None:
        voice_button_thread.join(timeout=1)
    # 종료 시점에 녹음이 돌고 있으면 arecord 프로세스와 임시 파일이 남는다.
    with _voice_lock:
        pending_process = _recording["process"]
        pending_path = _recording["path"]
        _recording["process"] = None
        _recording["path"] = None
    if pending_process is not None:
        pending_process.terminate()
        _safe_unlink(pending_path)
    if voice_button is not None:
        voice_button.close()
    # 방향 글자가 남은 채로 서버가 내려가면 다음 기동까지 그대로 켜져 있으므로 지우고 나간다.
    if _oled_device is not None:
        try:
            _oled_device.clear()
        except Exception:
            logging.exception("OLED: 종료 시 화면 정리 실패")
    for led in _led_cache.values():
        led.close()
