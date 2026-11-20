"""PTT 버튼 단독 테스트 ― camera_server.py 없이 버튼 배선과 눌림 판정만 확인한다.

실행: ~/venv/bin/python3 test_ptt.py              (15초 동안 버튼을 눌렀다 떼 본다)
      ~/venv/bin/python3 test_ptt.py --seconds 30
확인: 누를 때 '눌림', 뗄 때 '뗌 (n.n초)' 가 한 번씩만 찍힌다. 한 번 눌렀는데 여러 번 찍히면 채터링.

판정 방식은 camera_server.py 의 _watch_voice_button 과 같다 ― 20ms 마다 읽고 연속 2회 같으면 확정.
Pi 5 에서 gpiozero Button(이벤트 방식)은 'bad event request' 로 실패하므로 InputDevice 를 폴링한다.
주의: camera_server.py 가 돌고 있으면 GPIO 23 을 잡고 있어 "GPIO busy" 가 난다. 먼저 끈다.
"""

import argparse
import time

from gpiozero import InputDevice

BUTTON_PIN = 23                  # 물리 16 ↔ GND 물리 14
POLL_SECONDS = 0.02
STABLE_SAMPLES = 2
MIN_SECONDS = 0.5                # camera_server.py:VOICE_MIN_SECONDS ― 이보다 짧으면 서버는 무시한다

parser = argparse.ArgumentParser(description="PTT 버튼 단독 테스트")
parser.add_argument("--seconds", type=float, default=15)
seconds = parser.parse_args().seconds

button = InputDevice(BUTTON_PIN, pull_up=True)       # 내부 풀업 ― 누르면 LOW = is_active True
print(f"GPIO {BUTTON_PIN} 준비. 현재 상태: {'눌림' if button.is_active else '떼어짐'}")
if button.is_active:
    print("WARN  손을 대지 않았는데 '눌림' ― 버튼 반대쪽이 GND 가 아니라 3.3V 에 꽂혔는지 확인한다")
print(f"{seconds:.0f}초 동안 버튼을 눌렀다 떼 보세요 (Ctrl+C 로 종료)")

pressed, changed, pressed_at, presses = False, 0, 0.0, 0
deadline = time.monotonic() + seconds
try:
    while time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        changed = changed + 1 if button.is_active != pressed else 0
        if changed < STABLE_SAMPLES:
            continue
        pressed, changed = not pressed, 0
        if pressed:
            pressed_at = time.monotonic()
            print("  눌림   → (서버라면 arecord 녹음 시작)")
        else:
            held = time.monotonic() - pressed_at
            presses += 1
            note = "너무 짧아 서버는 무시" if held < MIN_SECONDS else "서버라면 whisper 인식"
            print(f"  뗌 ({held:.1f}초) → {note}")
except KeyboardInterrupt:
    pass
finally:
    button.close()

if presses == 0:
    print("FAIL  한 번도 감지되지 않았다 ― 물리 16(GPIO 23) · 14(GND) 에 꽂혔는지, 버튼 다리 방향을 확인한다")
    raise SystemExit(1)
print(f"PASS  버튼 {presses}회 감지")
