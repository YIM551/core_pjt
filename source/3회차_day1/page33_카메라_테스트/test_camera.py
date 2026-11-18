"""카메라(CSI) 단독 테스트 ― camera_server.py 없이 카메라 배선과 picamera2 만 확인한다.

실행: ~/venv/bin/python3 test_camera.py            (기본 640x480, 15fps ― 기기 서버와 같은 설정)
      ~/venv/bin/python3 test_camera.py --fps 10   [F105] FPS 를 낮췄을 때 비교
확인: ① 카메라가 목록에 보인다 ② camera_test.jpg 가 저장된다 ③ 측정 FPS 가 설정값 근처다

주의: camera_server.py(또는 camera-stream 서비스)가 돌고 있으면 카메라를 잡고 있어 실패한다.
      먼저 끈다 ― pkill -f "[c]amera_server.py" 또는 sudo systemctl stop camera-stream
"""

import argparse
import time

from picamera2 import Picamera2

# camera_server.py 의 STREAM_WIDTH · STREAM_HEIGHT · STREAM_FPS 와 같은 값으로 확인한다.
WIDTH, HEIGHT = 640, 480
MEASURE_FRAMES = 45
SNAPSHOT_PATH = "camera_test.jpg"

parser = argparse.ArgumentParser(description="카메라 단독 테스트")
parser.add_argument("--fps", type=int, default=15, help="카메라 FPS (기본 15)")
fps = max(1, min(parser.parse_args().fps, 30))

# ① 카메라 인식 ― 비어 있으면 케이블 방향 · 잠금 탭 · 전원 순서를 의심한다.
cameras = Picamera2.global_camera_info()
print("카메라 목록:", cameras)
if not cameras:
    print("FAIL  카메라가 보이지 않는다 ― 전원을 끈 뒤 CSI 케이블(접점 방향 · 잠금 탭)을 다시 꽂는다")
    raise SystemExit(1)

picam2 = Picamera2()
frame_us = int(1_000_000 / fps)
picam2.configure(picam2.create_video_configuration(
    main={"size": (WIDTH, HEIGHT)},
    controls={"FrameDurationLimits": (frame_us, frame_us)},
))
try:
    picam2.start()
    time.sleep(1.0)                         # 자동 노출이 자리 잡을 때까지 기다린다

    # ② 스냅샷 ― 대시보드 [전송] 때 YOLO · VLM 이 받는 것과 같은 크기의 프레임
    picam2.capture_file(SNAPSHOT_PATH)
    print(f"스냅샷 저장: {SNAPSHOT_PATH} ({WIDTH}x{HEIGHT}) ― scp 로 PC 에 가져와 초점 · 밝기를 본다")

    # ③ 실제 FPS ― 프레임을 연속으로 받아 걸린 시간으로 잰다
    t0 = time.monotonic()
    for _ in range(MEASURE_FRAMES):
        picam2.capture_array()
    measured = MEASURE_FRAMES / (time.monotonic() - t0)
    print(f"측정 FPS: {measured:.1f} (설정 {fps})")
finally:
    picam2.stop()
    picam2.close()

if measured < fps * 0.7:
    print("WARN  설정보다 많이 느리다 ― 다른 프로그램이 CPU 를 쓰고 있지 않은지 확인한다")
print("PASS  카메라 정상")
