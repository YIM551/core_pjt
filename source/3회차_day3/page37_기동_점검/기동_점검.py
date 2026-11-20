# -*- coding: utf-8 -*-
"""[page 37] 기동 순서 · 설치 확인 ― 앞 단계가 안 되면 뒤는 의미 없다.

강의자료 37쪽의 확인 순서를 PC 에서 한 번에 돌린다. 단계가 FAIL 이면 거기서 멈추고 고칠 곳을 알려 준다.
  1. D1 영상          기기 /stream.mjpg 에 MJPEG 프레임이 온다
  2. D2 · D3 출력     LED 17 · 27 점멸, OLED 에 LEFT ― 응답의 oled 가 shown 인지
  3. D4 음성          /voice-text 가 {seq, text} ― --ptt 면 PTT 로 말해 seq 가 1 오르는지
  4. D5 기기 LLM      /llm-infer 한 번 ― 모델을 미리 올려 둔다 (첫 요청 44 ~ 54초)
  5. PC 중계          대시보드 서버의 A6 영상 · A9 음성 중계

서버 두 개를 먼저 띄운다.
  라즈베리파이 : ~/venv/bin/python3 ~/camera_server.py   (또는 systemd 서비스 ― 1일차 심화 F106)
  PC           : ../page30_음성경로_통합/대시보드_음성통합.py

실행:
    python 기동_점검.py --device 192.168.0.10
    python 기동_점검.py --device 192.168.0.10 --ptt          # PTT 음성 인식까지 확인
"""
import argparse
import sys
import time

import httpx

DEVICE_PORT = 8080
USER_CONTENT = ("[YOLO 객체 인식] person 3개, bus 1개\n"
                "[VLM 장면 설명] 버스 앞에 두 명의 사람이 서 있습니다, 장애물 없음.\n"
                "[손 제스처] 가리키는 방향: 손 없음\n\n"
                "[사용자 질문] 앞에 뭐가 있어?")


class StepFailed(Exception):
    """이 단계가 FAIL ― 메시지는 고칠 곳."""


def first_chunk(client, url, params=None):
    """스트림을 열어 첫 조각만 읽고 닫는다 → (status, content-type, 첫 조각)."""
    with client.stream("GET", url, params=params) as r:
        return r.status_code, r.headers.get("content-type", ""), next(r.iter_raw(), b"")


def step_d1(device, pc):
    status, ctype, head = first_chunk(device, "/stream.mjpg")
    if status != 200 or b"--FRAME" not in head:
        raise StepFailed("영상이 안 온다 ― 카메라 케이블 · rpicam-hello --list-cameras (1일차 page26)")
    return f"{ctype}"


def step_d2_d3(device, pc):
    for pin in (17, 27):
        r = device.get("/gpio-blink", params={"pin": pin})
        if r.status_code != 200 or r.json().get("ok") is not True:
            raise StepFailed(f"LED {pin} 실패 ({r.status_code}) ― GPIO busy 면 다른 프로그램이 핀을 쓴다 (1일차 page29)")
    r = device.get("/oled-display", params={"text": "LEFT"})
    oled = r.json().get("oled") if r.status_code == 200 else None
    if r.status_code != 200:
        raise StepFailed(f"D3 {r.status_code} ― 기기 서버 버전을 확인한다 (1일차 page38 이후)")
    note = "" if oled == "shown" else "  ← OLED 미표시 (200 은 정상, R6). SPI · venv 파이썬 · 배선 확인 (1일차 page32)"
    return f"LED 17 · 27 점멸, OLED LEFT (oled={oled}){note} ― LED 를 깜빡여도 OLED 가 리셋되지 않는지 눈으로 본다"


def step_d4(device, pc, ptt=False, wait=20):
    r = device.get("/voice-text")
    data = r.json() if r.status_code == 200 else {}
    if not (isinstance(data.get("seq"), int) and isinstance(data.get("text"), str)):
        raise StepFailed(f"/voice-text 형식이 다르다 ({r.status_code} {data}) ― 2일차 page63_음성인식_D4 이후 기기 서버인지 확인한다")
    if not ptt:
        return f"{data}  (--ptt 로 실제 발화까지 확인할 수 있다)"
    print(f"         PTT 를 누른 채 '오른쪽으로 두 칸 가' 라고 말하고 떼세요 ({wait}초 안에)…", flush=True)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        time.sleep(1)
        new = device.get("/voice-text").json()
        if new["seq"] > data["seq"]:
            if not new["text"]:
                raise StepFailed("seq 는 올랐는데 text 가 비었다 ― whisper 경로 · 모델 파일, 마이크 (2일차 page58_whisper_빌드 · page48_마이크_테스트)")
            return f"seq {data['seq']} → {new['seq']}, text={new['text']!r}"
    raise StepFailed("seq 가 오르지 않았다 ― 서버 로그에 'PTT: 녹음 시작' 이 없으면 버튼, 있으면 arecord 장치 (2일차 page51_PTT_버튼_테스트 · page48_마이크_테스트)")


def step_d5(device, pc):
    t0 = time.perf_counter()
    r = device.post("/llm-infer", json={"user_content": USER_CONTENT, "history": []}, timeout=180)
    data = r.json() if r.status_code == 200 else {}
    if data.get("tool") not in ("move", "describe", "ask"):
        raise StepFailed(f"{r.status_code} {r.text[:80]} ― 500 이면 venv 파이썬으로 띄웠는지 · 모델 경로 (page25_온디바이스LLM_D5)")
    return f"{time.perf_counter() - t0:.1f}s → {data['tool']} {data['args']} (이제 모델이 올라가 있다)"


def step_pc(device, pc, ip=""):
    try:
        status, _, head = first_chunk(pc, "/api/camera-stream", params={"ip": ip})
    except httpx.ConnectError:
        raise StepFailed("PC 대시보드 서버가 꺼져 있다 ― page30_음성경로_통합 서버를 띄운다")
    if status != 200 or b"--FRAME" not in head:
        raise StepFailed(f"A6 {status} ― 연동 탭에 등록한 IP 와 같은지, PC 와 Pi 가 같은 네트워크인지")
    r = pc.get("/api/voice-poll", params={"ip": ip})
    if r.status_code != 200:
        raise StepFailed(f"A9 {r.status_code} {r.text[:60]} ― 2일차 page67_음성중계_A9 이후 서버인지")
    return f"A6 영상 중계 · A9 {r.json()} ― 이제 연동 탭에 IP 를 등록한다"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", required=True, metavar="IP", help="라즈베리파이 IP")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="PC 대시보드 서버")
    parser.add_argument("--ptt", action="store_true", help="PTT 로 말해 D4 seq 가 오르는지까지 확인")
    args = parser.parse_args()

    steps = [("1", "D1 영상", step_d1),
             ("2", "D2 · D3 LED · OLED", step_d2_d3),
             ("3", "D4 음성 인식", lambda d, p: step_d4(d, p, args.ptt)),
             ("4", "D5 기기 LLM", step_d5),
             ("5", "PC 중계 A6 · A9", lambda d, p: step_pc(d, p, args.device))]
    with httpx.Client(base_url=f"http://{args.device}:{DEVICE_PORT}", timeout=10) as device, \
            httpx.Client(base_url=args.url, timeout=10) as pc:
        for no, title, step in steps:
            try:
                detail = step(device, pc)
            except (httpx.ConnectError, httpx.ConnectTimeout):
                detail = None
                error = f"기기 {args.device}:{DEVICE_PORT} 에 연결할 수 없다 ― 기기 서버 실행 · IP · 같은 네트워크인지"
            except (httpx.HTTPError, StepFailed) as exc:
                detail, error = None, str(exc) or type(exc).__name__
            if detail is None:
                print(f"  FAIL  {no}. {title}  ― {error}")
                print(f"\n{no}단계에서 멈춤 ― 앞 단계가 안 되면 뒤는 의미 없다. 고친 뒤 다시 실행한다.")
                sys.exit(1)
            print(f"  PASS  {no}. {title}  ― {detail}", flush=True)
    print("\n전 단계 PASS ― 시나리오 실습(page40)으로 넘어간다.")


if __name__ == "__main__":
    main()
