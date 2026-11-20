# -*- coding: utf-8 -*-
"""[page 52] F303 장애 주입 관찰 ― 기기를 일부러 끊어 보고, PC 가 어떻게 응답하는지 한 줄씩 본다.

기기 탭 상단의 연결 상태 줄(영상 · 음성 · 기기 LLM)과 같은 것을 터미널에 2초마다 찍는다
(기기가 꺼져 있으면 연결 시간 초과 3초씩만큼 줄 간격이 늘어난다).
이 스크립트를 띄워 둔 채 강의자료 52쪽의 장애를 하나씩 일으키고, 줄이 어떻게 바뀌는지 관찰한다.
  - 라즈베리파이 서버 Ctrl+C       → 영상 · 음성 502, 로컬 PC 는 정상 (R6)
  - 공유기에서 Pi Wi-Fi 잠시 끊기  → 영상 '응답 없음' → 약 10초 뒤 스트림 종료 (조용한 단절, F105)
  - 서버 다시 실행                 → 다시 '연결됨'

  영상    = A6 /api/camera-stream 이 첫 프레임을 주는가 (연결 3초 · 읽기 10초)
  음성    = A9 /api/voice-poll                        (3초)
  로컬 PC = A1 / 이 응답하는가 ― 기기가 꺼져도 로컬 PC 탭은 영향이 없어야 한다

--ask 를 주면 기기 탭 질문(source=device) 하나를 보내 기기 LLM 경로를 확인한다.
기기가 꺼져 있으면 502 device_llm_unreachable 이 빨리(연결 3초) 와야 하고, 켜져 있으면 첫 요청은
모델 로딩 때문에 1분 가까이 걸린다 (DEVICE_LLM_TIMEOUT 120초 안).

서버를 먼저 띄운다 (PC ../page30_음성경로_통합).

실행:
    python 장애_관찰.py --device 192.168.0.10                   # Ctrl+C 로 끝낸다
    python 장애_관찰.py --device 192.168.0.10 --seconds 60
    python 장애_관찰.py --device 192.168.0.10 --ask "오른쪽으로 2칸 가"
"""
import argparse
import time

import httpx

INTERVAL_SECONDS = 2.0


def camera_state(client, ip):
    """A6 → '연결됨' / '끊김 (502 camera_unreachable)' / '응답 없음'."""
    try:
        with client.stream("GET", "/api/camera-stream", params={"ip": ip},
                           timeout=httpx.Timeout(5.0, read=12.0)) as r:
            if r.status_code != 200:
                r.read()
                return f"끊김 ({r.status_code} {r.json().get('error')})"
            return "연결됨" if b"--FRAME" in next(r.iter_raw(), b"") else "프레임 없음"
    except httpx.ReadTimeout:
        return "응답 없음 (읽기 시간 초과)"
    except httpx.HTTPError as exc:
        return f"PC 오류 ({type(exc).__name__})"


def voice_state(client, ip):
    """A9 → '연결됨 seq=n' / '끊김 (502 ...)'."""
    try:
        r = client.get("/api/voice-poll", params={"ip": ip}, timeout=6.0)
    except httpx.HTTPError as exc:
        return f"PC 오류 ({type(exc).__name__})"
    if r.status_code != 200:
        return f"끊김 ({r.status_code} {r.json().get('error')})"
    return f"연결됨 seq={r.json()['seq']}"


def local_state(client):
    """A1 → 로컬 PC 탭이 쓰는 서버가 살아 있는가."""
    try:
        return "정상" if client.get("/", timeout=3.0).status_code == 200 else "이상"
    except httpx.HTTPError:
        return "PC 서버 꺼짐"


def ask_once(client, ip, prompt):
    """기기 탭 질문 한 번 ― 기기 LLM 경로(D5)와 오류 격리(R6)를 본다."""
    history = [{"role": "user", "content": "[사용자 질문] 저쪽으로 2칸 가"},
               {"role": "assistant", "content": '{"tool": "ask", "args": {"steps": 2}, "message": "어느 쪽으로 2칸 갈까요?"}'}]
    print(f"기기 탭 질문 (source=device, history {len(history)}개) : {prompt!r}", flush=True)
    t0 = time.perf_counter()
    r = client.post("/api/llm-answer", timeout=200, json={
        "prompt": prompt, "yolo_summary": "", "vlm_description": "", "gesture_direction": "none",
        "history": history, "source": "device", "ip": ip})
    sec = time.perf_counter() - t0
    data = r.json()
    if r.status_code != 200:
        print(f"  {sec:5.1f}s  {r.status_code} {data.get('error')} ― 화면은 오류 문구만 보이고 history {len(history)}개를 유지한다 (R6)")
    else:
        print(f"  {sec:5.1f}s  {data['tool']} {data['args']}  {data['message']!r}")
    print(f"  로컬 PC : {local_state(client)}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", required=True, metavar="IP", help="라즈베리파이 IP")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="PC 대시보드 서버")
    parser.add_argument("--seconds", type=float, default=0, help="관찰 시간 (0 이면 Ctrl+C 까지)")
    parser.add_argument("--ask", metavar="질문", help="기기 탭 질문 하나를 먼저 보낸다")
    args = parser.parse_args()

    with httpx.Client(base_url=args.url) as client:
        if args.ask:
            ask_once(client, args.device, args.ask)
        print(f"{'시각':8}  {'영상 (A6)':28}  {'음성 (A9)':28}  로컬 PC (A1)")
        deadline = time.monotonic() + args.seconds if args.seconds else None
        last = None
        try:
            while deadline is None or time.monotonic() < deadline:
                t0 = time.monotonic()
                row = (camera_state(client, args.device), voice_state(client, args.device), local_state(client))
                mark = "" if last is None or row == last else "   ← 바뀜"
                print(f"{time.strftime('%H:%M:%S')}  {row[0]:28}  {row[1]:28}  {row[2]}{mark}", flush=True)
                last = row
                time.sleep(max(0.0, INTERVAL_SECONDS - (time.monotonic() - t0)))
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
