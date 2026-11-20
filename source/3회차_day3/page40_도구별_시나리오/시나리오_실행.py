# -*- coding: utf-8 -*-
"""[page 40] F301 도구별 통합 시나리오 ― 같은 질문을 텍스트 · 음성으로 보내 같은 결과인지 확인한다.

강의자료 40쪽의 시나리오 표를 채운다. 질문마다 기기 탭이 보내는 A5 요청을 두 번 보낸다.
  텍스트 = 기기 탭 타이핑         → source: "device"
  음성   = PTT → D4 → A9 자동 입력 → source: "voice"
둘 다 기기 ip 를 담아 기기 LLM(D5)이 고르고 PC 가 같은 규칙을 적용한다 (R9).
move 면 화면(index.html)처럼 이동마다 A8(OLED) · A7(LED, 좌우만)을 2초 간격으로 호출한다 (R8).

인식 결과(YOLO · VLM)는 고정 문구를 쓴다 ― 도구 선택만 비교하기 위해서다.
대시보드 기기 탭에서 같은 질문을 직접 해 보고, 이 표와 나란히 비교한다.

서버 두 개를 먼저 띄운다 (라즈베리파이 camera_server.py, PC ../page30_음성경로_통합).

실행:
    python 시나리오_실행.py --device 192.168.0.10              # 텍스트 · 음성(같은 문장) 모두
    python 시나리오_실행.py --device 192.168.0.10 --ptt        # 음성은 PTT 로 직접 말한다 (A9 로 받은 글자 사용)
    python 시나리오_실행.py --device 192.168.0.10 --no-output  # OLED · LED 는 건드리지 않는다
"""
import argparse
import time

import httpx

YOLO_SUMMARY = "person 3개, bus 1개"
VLM_DESCRIPTION = "버스 앞에 두 명의 사람이 서 있습니다, 장애물 없음."
OLED_TEXT = {"left": "LEFT", "right": "RIGHT", "up": "UP", "down": "DOWN"}
MOVE_INTERVAL_SECONDS = 2.0          # [R8] 연속 이동은 2초 간격 (LED 3회 점멸 ≈ 1.8초)

# (질문, 기대 도구, 기대 인자(guess 제외), 기대 OLED) ― 강의자료 40쪽 표
SCENARIOS = [
    ("앞에 뭐가 있어?", "describe", {}, []),
    ("오른쪽으로 3칸 가", "move", {"direction": "right", "steps": 3}, ["RIGHT"]),
    ("왼쪽으로 1칸 가", "move", {"direction": "left", "steps": 1}, ["LEFT"]),
    ("아래로 2칸 가", "move", {"direction": "down", "steps": 2}, ["DOWN"]),
    ("오른쪽 2칸 가고 위로 1칸", "move", {"direction": "right", "steps": 2}, ["RIGHT", "UP"]),
    ("저쪽으로 가", "ask", {"steps": 1}, []),
]


def ask(client, ip, prompt, source, history=None):
    """기기 탭이 보내는 A5 요청 한 번 → (응답 dict, 걸린 초)."""
    t0 = time.perf_counter()
    r = client.post("/api/llm-answer", json={
        "prompt": prompt, "yolo_summary": YOLO_SUMMARY, "vlm_description": VLM_DESCRIPTION,
        "gesture_direction": "none", "history": history or [], "source": source, "ip": ip})
    data = r.json() if r.status_code == 200 else {"error": r.json().get("error", r.status_code)}
    return data, time.perf_counter() - t0


def output_move(client, ip, data, enabled=True):
    """move 의 이동마다(args 다음 then 순서) A8 · A7 을 호출한다 → (OLED 글자 목록, LED 방향 목록)."""
    oled, led = [], []
    if data.get("tool") != "move":
        return oled, led
    for i, move in enumerate([data["args"]] + data.get("then", [])):
        if i:
            time.sleep(MOVE_INTERVAL_SECONDS if enabled else 0)
        oled.append(OLED_TEXT[move["direction"]])
        if move["direction"] in ("left", "right"):        # LED 는 좌우만 ― up · down 은 A7 을 부르지 않는다
            led.append(move["direction"])
        if enabled:
            client.post("/api/oled-display", json={"ip": ip, "direction": move["direction"]})
            if move["direction"] in ("left", "right"):
                client.post("/api/robot-signal", json={"ip": ip, "direction": move["direction"]})
    return oled, led


def wait_voice(client, ip, prompt, timeout=30):
    """PTT 로 말한 새 발화를 A9 로 받는다 (화면의 1초 폴링과 같다). 시간 안에 없으면 None."""
    seq = client.get("/api/voice-poll", params={"ip": ip}).json().get("seq", 0)
    print(f"    🎤 PTT 를 누른 채 '{prompt}' 라고 말하고 떼세요…", flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(1)
        data = client.get("/api/voice-poll", params={"ip": ip}).json()
        if data.get("seq", 0) > seq and data.get("text"):          # 502 면 seq 가 없다 ― 다음 폴링
            print(f"    인식: {data['text']!r}")
            return data["text"]
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", required=True, metavar="IP", help="라즈베리파이 IP")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="PC 대시보드 서버")
    parser.add_argument("--ptt", action="store_true", help="음성은 PTT 로 직접 말한다")
    parser.add_argument("--no-output", action="store_true", help="OLED · LED 를 호출하지 않는다")
    args = parser.parse_args()

    rows, same = [], 0
    with httpx.Client(base_url=args.url, timeout=200) as client:
        for prompt, tool, expected_args, expected_oled in SCENARIOS:
            print(f"\n■ {prompt}")
            got = {}
            for label, source in (("텍스트", "device"), ("음성", "voice")):
                text = prompt
                if source == "voice" and args.ptt:
                    text = wait_voice(client, args.device, prompt)
                    if text is None:
                        print("    음성 없음 ― 건너뛴다")
                        continue
                data, sec = ask(client, args.device, text, source)
                if "error" in data:
                    print(f"    {label:3}  X  {data['error']} ({sec:.1f}s)")
                    continue
                oled, led = output_move(client, args.device, data, not args.no_output)
                call_args = {k: v for k, v in data["args"].items() if k != "guess"}
                ok = data["tool"] == tool and call_args == expected_args and oled == expected_oled
                got[label] = (data["tool"], call_args, data.get("then"))
                then = f" + then {data['then']}" if data.get("then") else ""
                print(f"    {label:3}  {'O' if ok else 'X'}  {sec:4.1f}s  {data['tool']} {data['args']}{then}")
                print(f"              OLED {' → '.join(oled) or '그대로'}  ·  LED {', '.join(led) or '없음'}"
                      f"  ·  {data['message']!r}")
                rows.append(ok)
            if len(got) == 2:
                same += got["텍스트"] == got["음성"]
                print(f"    R9  텍스트 · 음성 같은 tool · args : {'같다' if got['텍스트'] == got['음성'] else '다르다'}")

    print("\n" + "-" * 60)
    print(f"시나리오 {sum(rows)}/{len(rows)} 기대와 같음  ·  텍스트 = 음성 {same}/{len(SCENARIOS)}")
    print("음성이 다르면 먼저 입력창(인식 글자)을 확인한다 ― STT 문제지 도구 선택 문제가 아니다 (37쪽)")


if __name__ == "__main__":
    main()
