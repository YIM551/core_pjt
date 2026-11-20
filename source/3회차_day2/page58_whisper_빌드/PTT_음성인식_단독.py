"""[page 30] PTT + 녹음 + whisper.cpp 단독 확인 — 대시보드/camera_server.py와 무관하게
PTT 버튼 + 마이크 + whisper.cpp 음성 인식만 따로 확인한다 (기기 서버 D4 에 넣기 전 단계).

실행: python3 PTT_음성인식_단독.py   (camera_server.py가 켜져 있으면 먼저 끌 것 — 같은 버튼 핀을 쓴다)
확인: 버튼을 누르고 있는 동안 말하고, 떼면 인식 결과가 터미널에 찍힌다. Ctrl+C로 종료.
"""

import os
import subprocess
import tempfile
import time
import wave
from pathlib import Path

from gpiozero import InputDevice

# 아래 값은 라즈베리파이에 있는 camera_server.py와 같다(실물 확인값).
BUTTON_PIN = 23                     # GPIO 23(물리 16번 핀). 버튼 반대쪽은 GND에 연결(내부 풀업 사용)
# 카드 번호(0, 2…)는 부팅마다 바뀔 수 있어 이름으로 지정한다(Pi의 camera_server.py와 같은 값).
ALSA_DEVICE = "plughw:CARD=sndrpigooglevoi,DEV=0"
SAMPLE_RATE = 16000
MIN_SECONDS = 0.5                   # 이보다 짧게 누르면 실수로 보고 무시
POLL_SECONDS = 0.01                 # 버튼 상태를 확인하는 간격
WHISPER_DIR = Path.home() / "whisper.cpp"
WHISPER_BIN = WHISPER_DIR / "build" / "bin" / "whisper-cli"
WHISPER_MODEL = WHISPER_DIR / "models" / "ggml-base.bin"


def wait_until(button, pressed):
    """버튼이 원하는 상태(pressed=True: 눌림, False: 뗌)가 될 때까지 기다린다.

    gpiozero Button은 엣지 이벤트를 등록하는데, 이 기기에서는 lgpio가 'bad event request'로
    거부해 실행이 안 된다. 그래서 이벤트 없이 상태를 직접 읽는 방식(폴링)을 쓴다.
    """
    while button.is_active != pressed:
        time.sleep(POLL_SECONDS)


def record_while_pressed(button):
    """버튼을 누르고 있는 동안만 녹음해 (wav 경로, 녹음 시간)을 돌려준다. 녹음이 비면 경로는 None.

    arecord가 WAV를 직접 쓰게 하면 중간에 끊을 때 헤더가 제대로 마무리되지 않아 whisper가
    "failed to read audio"로 읽지 못할 수 있다. 그래서 헤더 없는 raw로 받아 파이썬이 WAV를 만든다.
    """
    fd, raw_path = tempfile.mkstemp(prefix="mic_test_", suffix=".raw")
    os.close(fd)
    process = subprocess.Popen(
        ["arecord", "-D", ALSA_DEVICE, "-t", "raw", "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1", raw_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    started = time.monotonic()
    wait_until(button, pressed=False)
    duration = time.monotonic() - started
    process.terminate()
    _, error = process.communicate()

    with open(raw_path, "rb") as f:
        frames = f.read()
    os.remove(raw_path)
    if not frames:
        print(f"녹음 실패 — 마이크에서 받은 소리가 없다. arecord 메시지: {error.strip()}")
        return None, duration

    wav_path = raw_path[:-len(".raw")] + ".wav"
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)               # S16_LE = 2바이트
        w.setframerate(SAMPLE_RATE)
        w.writeframes(frames)
    return wav_path, duration


def transcribe(path):
    result = subprocess.run(
        [str(WHISPER_BIN), "-m", str(WHISPER_MODEL), "-l", "ko", "-nt", "-f", path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return f"(whisper 실패: {result.stderr.strip()})"
    return " ".join(result.stdout.split())


def main():
    if not WHISPER_BIN.exists() or not WHISPER_MODEL.exists():
        print(f"whisper 바이너리/모델이 없다: {WHISPER_BIN}, {WHISPER_MODEL} (이 폴더 whisper_빌드.sh 참고)")
        return

    button = InputDevice(BUTTON_PIN, pull_up=True)   # 풀업 → 누르면 LOW, is_active=True
    print("준비 완료 — 버튼을 누르고 있는 동안 말하세요. (종료: Ctrl+C)")
    try:
        while True:
            wait_until(button, pressed=True)
            print("녹음 중...")
            path, duration = record_while_pressed(button)
            if path is None:
                continue
            try:
                if duration < MIN_SECONDS:
                    print(f"{duration:.2f}초 — 너무 짧아 무시")
                    continue
                print(f"녹음 종료 ({duration:.1f}초), 인식 중...")
                print(f"인식 결과: {transcribe(path)}")
            finally:
                os.remove(path)
    except KeyboardInterrupt:
        print("\n종료")
    finally:
        button.close()


if __name__ == "__main__":
    main()
