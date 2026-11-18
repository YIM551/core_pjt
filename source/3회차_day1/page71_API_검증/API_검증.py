# -*- coding: utf-8 -*-
"""[page 71] PJT01 검증 ― 기준선(2회차) 항목 + A6 ~ A8 · R6 · R8 · R10.

page16 의 검증 스크립트에 3회차 PJT01 항목을 더했다. 번호는 명세서(16-C-3-01) 'API 및 규칙 명세' 표 번호다.
  --quick        : 기기 없이 ― 잘못된 요청 → 400, 연결할 수 없는 IP(192.0.2.1, 문서용 예약 주소) → 502
  --device <IP>  : 기기와 함께 ― D1 ~ D3 응답, A6 중계, A7 · A8 방향별 결과, 기기 탭 답변(R10)

서버를 먼저 띄운 뒤 (터미널 1 : ../page61_기기연동/대시보드_기기연동.py), 다른 터미널에서 실행한다.

실행:
    python API_검증.py --quick                          # 기기 · 모델 없이 (몇 초)
    python API_검증.py                                  # 전체 (PC 모델 추론 포함, CPU 약 2분)
    python API_검증.py --device 192.168.0.10            # 전체 + 라즈베리파이 항목
"""
import argparse
import io
import json
import sys
import time
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_JPG = BASE_DIR.parent / "samples" / "sample.jpg"   # 3회차_day1/samples

# A5 는 A3 · A4 결과와 무관하게 같은 입력으로 확인한다 (2일차 대시보드 실측값)
YOLO_SUMMARY = "person 3개, bus 1개"
VLM_DESCRIPTION = "버스 앞에 두 명의 사람이 서 있습니다, 장애물 없음."

# (번호, 설명, 질문, 손 방향, 기대 도구, 기대 인자)
TOOL_CASES = [
    ("A5-1", "장면 질문 → describe", "앞에 뭐가 있어?", "unknown", "describe", {}),
    ("A5-2", "방향 · 칸 수 → move", "오른쪽으로 3칸 가", "unknown", "move",
     {"direction": "right", "steps": 3}),
    ("A5-3", "방향은 손 제스처 → move", "이쪽으로 2칸 이동해", "up", "move",
     {"direction": "up", "steps": 2}),
    ("A5-4", "제스처 시퀀스 입력 문구 → move", "왼쪽으로, 5칸 이동.", "unknown", "move",
     {"direction": "left", "steps": 5}),
    ("R3", "방향 근거 없음 → ask", "저쪽으로 가", "unknown", "ask", {"steps": 1}),
    ("R3", "방향 근거 없음 → ask", "버스 있는 쪽으로 가", "unknown", "ask", {"steps": 1}),
    ("R3", "'위' 는 방향어 → move", "위 2칸 가", "unknown", "move",
     {"direction": "up", "steps": 2}),
    ("R3", "'위치' 는 방향어 아님 → ask", "버스 위치로 가", "unknown", "ask", {"steps": 1}),
    ("A5-5", "프롬프트 방향어가 손 제스처보다 우선", "왼쪽으로 2칸 가", "up", "move",
     {"direction": "left", "steps": 2}),
    ("R3", "손 없음 · 방향어 없음 → ask", "이쪽으로 가", "none", "ask", {"steps": 1}),
    ("개선4", "'말고' 앞 방향어는 지운다 → move", "왼쪽 말고 오른쪽으로 2칸 가", "unknown", "move",
     {"direction": "right", "steps": 2}),
    ("개선4", "부정된 방향어만 있음 → ask", "왼쪽 말고 가", "unknown", "ask", {"steps": 1}),
]

# 연결할 수 없는 기기 주소 (TEST-NET-1, 문서용 예약 주소 ― 아무 장치도 응답하지 않는다)
UNREACHABLE_IP = "192.0.2.1"
OLED_TEXT = {"left": "LEFT", "right": "RIGHT", "up": "UP", "down": "DOWN"}  # OLED는 네 방향 (R8)

results = []


def check(item_id, title, ok, detail=""):
    results.append((item_id, bool(ok)))
    mark = "PASS" if ok else "FAIL"
    print(f"  {mark}  [{item_id:<4}] {title}" + (f"  ― {detail}" if detail else ""), flush=True)


def error_code(response):
    try:
        return response.json().get("error")
    except ValueError:
        return None


def llm(client, prompt, gesture="unknown", history=None, source=None, ip=None):
    body = {"prompt": prompt, "yolo_summary": YOLO_SUMMARY, "vlm_description": VLM_DESCRIPTION,
            "gesture_direction": gesture, "history": history or []}
    if source:                         # 3회차 ― 넣지 않으면 2회차 요청과 똑같다
        body["source"] = source
    if ip:
        body["ip"] = ip
    t0 = time.perf_counter()
    response = client.post("/api/llm-answer", json=body)
    return response, time.perf_counter() - t0


def no_grid_talk(data):
    """[R10] 기기 탭 답변에 시뮬레이터식 표현(칸 수 · 로봇 · 시뮬레이터 · 격자)이 없다."""
    message = data.get("message", "")
    return bool(message) and not any(word in message for word in ("칸", "로봇", "시뮬레이터", "격자"))


def check_shape(data):
    """A5 응답 형식 + R1 · R2 · R4 ― 모든 LLM 응답에 공통으로 적용한다."""
    missing = {"tool", "args", "need_more_info", "message", "user_content"} - set(data)
    check("A5", "응답 필드 5개", not missing, f"없음: {sorted(missing)}" if missing else "")
    tool, args = data.get("tool"), data.get("args")
    check("R1", "tool 은 move / describe / ask 중 하나", tool in ("move", "describe", "ask"),
          f"tool={tool!r}")
    if tool == "move":
        ok = args.get("direction") in ("up", "down", "left", "right") \
            and isinstance(args.get("steps"), int) and 1 <= args["steps"] <= 10
    elif tool == "ask":                # {} 또는 {"steps": 이미 아는 칸 수, "guess": LLM 이 추측한 방향(개선 ②)}
        ok = isinstance(args, dict) and set(args) <= {"steps", "guess"} \
            and args.get("guess", "up") in ("up", "down", "left", "right")
    else:                              # describe 는 {}
        ok = args == {}
    check("R2", "도구별 인자 형식", ok, f"args={args}")
    check("R4", "need_more_info == (tool == ask)",
          data.get("need_more_info") is (tool == "ask"), f"need_more_info={data.get('need_more_info')}")


def run_quick(client):
    print("\n[A1 · A2] 화면과 정적 파일")
    r = client.get("/")
    check("A1", "GET / → index.html", r.status_code == 200 and "시뮬레이터" in r.text,
          f"status={r.status_code}")
    for path in ("/mediapipe/vision_bundle.mjs", "/mediapipe/gesture_recognizer.task"):
        r = client.get(path)
        check("A2", f"GET {path}", r.status_code == 200 and len(r.content) > 1000,
              f"{r.status_code}, {len(r.content):,} bytes")

    print("\n[A3 · A4 · A5] 잘못된 요청 → 약속된 400")
    for path, item in (("/api/yolo-detect", "A3"), ("/api/vlm-describe", "A4")):
        r = client.post(path, content=b"")
        check(item, f"{path} 빈 본문 → empty_image", error_code(r) == "empty_image",
              f"{r.status_code} {error_code(r)}")
        r = client.post(path, content=b"not an image")
        check(item, f"{path} 이미지 아님 → invalid_image", error_code(r) == "invalid_image",
              f"{r.status_code} {error_code(r)}")
    r = client.post("/api/llm-answer", content=b"{broken", headers={"Content-Type": "application/json"})
    check("A5", "JSON 아님 → invalid_json", error_code(r) == "invalid_json",
          f"{r.status_code} {error_code(r)}")
    r = client.post("/api/llm-answer", json={"prompt": "   "})
    check("A5", "빈 prompt → empty_prompt", error_code(r) == "empty_prompt",
          f"{r.status_code} {error_code(r)}")

    print(f"\n[A6 ~ A8 · R6 · R8] 3회차 중계 ― 잘못된 요청 → 400, 연결할 수 없는 기기({UNREACHABLE_IP}) → 502")
    r = client.get("/api/camera-stream")
    check("A6", "ip 없음 → invalid_request", error_code(r) == "invalid_request",
          f"{r.status_code} {error_code(r)}")
    r = client.get("/api/camera-stream", params={"ip": UNREACHABLE_IP})
    check("A6", "연결 불가 → 502 camera_unreachable",
          r.status_code == 502 and error_code(r) == "camera_unreachable", f"{r.status_code} {error_code(r)}")
    for path, item in (("/api/robot-signal", "A7"), ("/api/oled-display", "A8")):
        r = client.post(path, content=b"{broken", headers={"Content-Type": "application/json"})
        check(item, f"{path} JSON 아님 → invalid_json", error_code(r) == "invalid_json",
              f"{r.status_code} {error_code(r)}")
        r = client.post(path, json={"ip": UNREACHABLE_IP, "direction": "front"})
        check(item, f"{path} 없는 방향 → invalid_request", error_code(r) == "invalid_request",
              f"{r.status_code} {error_code(r)}")
        r = client.post(path, json={"ip": UNREACHABLE_IP, "direction": "left"})
        check(item, f"{path} 연결 불가 → 502 device_unreachable",
              r.status_code == 502 and error_code(r) == "device_unreachable", f"{r.status_code} {error_code(r)}")
    for d in ("up", "down"):
        payload = {"ip": UNREACHABLE_IP, "direction": d}
        r = client.post("/api/robot-signal", json=payload)
        check("R8", f"LED는 좌우만 지원 ― A7 {d} → 400 invalid_request",
              r.status_code == 400 and error_code(r) == "invalid_request",
              f"{r.status_code} {error_code(r)}")
        r = client.post("/api/oled-display", json=payload)
        check("R8", f"OLED는 상하도 지원 ― A8 {d}, 연결 불가 → 502 device_unreachable",
              r.status_code == 502 and error_code(r) == "device_unreachable",
              f"{r.status_code} {error_code(r)}")


def run_models(client):
    image = SAMPLE_JPG.read_bytes()
    from PIL import Image
    width, height = Image.open(io.BytesIO(image)).size

    print(f"\n[A3 · A4] 인식 ({SAMPLE_JPG.name} {width}x{height})")
    t0 = time.perf_counter()
    r = client.post("/api/yolo-detect", content=image)
    objects = r.json().get("objects") if r.status_code == 200 else None
    ok = isinstance(objects, list) and all(
        0 <= o["confidence"] <= 1 and len(o["box"]) == 4
        and 0 <= o["box"][0] <= o["box"][2] <= width and 0 <= o["box"][1] <= o["box"][3] <= height
        for o in objects)
    check("A3", "objects : label · confidence · box(픽셀 좌표)", ok,
          f"{time.perf_counter() - t0:.1f}s  " + ", ".join(o["label"] for o in objects or []))
    t0 = time.perf_counter()
    r = client.post("/api/vlm-describe", content=image)
    text = r.json().get("description") if r.status_code == 200 else None
    check("A4", "description 문자열", isinstance(text, str) and text.strip(),
          f"{time.perf_counter() - t0:.1f}s  {text!r}")

    print("\n[A5 · R3] 의도 파악 → 도구 선택")
    for item_id, title, prompt, gesture, tool, args in TOOL_CASES:
        r, sec = llm(client, prompt, gesture)
        data = r.json() if r.status_code == 200 else {}
        got = f"{data.get('tool')} {data.get('args', '')}"
        got_args = {k: v for k, v in data.get("args", {}).items() if k != "guess"}  # guess 는 LLM 추측이라 비교하지 않는다
        check(item_id, f"{title} : {prompt!r}",
              data.get("tool") == tool and got_args == args, f"{sec:.1f}s → {got}")
        if data:
            check_shape(data)

    print("\n[R5] 되묻기 → 방향을 답하면 이어서 이동")
    r, _ = llm(client, "저쪽으로 2칸 가")
    first = r.json() if r.status_code == 200 else {}
    check("R5", "1턴 '저쪽으로 2칸 가' → ask", first.get("tool") == "ask",
          f"→ {first.get('tool')} {first.get('args', '')}")
    history = [{"role": "user", "content": first.get("user_content", "")},
               {"role": "assistant", "content": json.dumps(
                   {k: first.get(k) for k in ("tool", "args", "message")}, ensure_ascii=False)}]
    r, sec = llm(client, "왼쪽", history=history)
    second = r.json() if r.status_code == 200 else {}
    check("R5", "2턴 '왼쪽' → move(left, 2)",
          second.get("tool") == "move" and second.get("args") == {"direction": "left", "steps": 2},
          f"{sec:.1f}s → {second.get('tool')} {second.get('args', '')}")

    print("\n[A5-6] 이전 턴 질문이 손 제스처보다 우선 (방어용 ― 우선순위 구현 확인)")
    # 실제 화면 흐름에서는 생기지 않는 입력이다. 방향어가 있는 질문은 R3 로 항상 move 가 되고,
    # history 는 ask 로 끝난 턴만 남으므로 '방향어가 든 이전 턴' 이 전달되지 않는다.
    # 우선순위(프롬프트 방향어 → 이전 턴 질문 → 손 제스처) 구현이 맞는지만 보려고, ask 로 끝난 이전 턴을 직접 만들어 보낸다.
    history = [{"role": "user", "content": f"[YOLO 객체 인식] {YOLO_SUMMARY}\n"
                                           f"[VLM 장면 설명] {VLM_DESCRIPTION}\n"
                                           f"[손 제스처] 가리키는 방향: 손 없음\n\n"
                                           f"[사용자 질문] 왼쪽 2칸 가도 돼?"},
               {"role": "assistant", "content": json.dumps(
                   {"tool": "ask", "args": {"steps": 2}, "message": "어느 쪽으로 2칸 갈까요?"},
                   ensure_ascii=False)}]
    r, sec = llm(client, "이쪽으로 3칸 가", gesture="up", history=history)
    data = r.json() if r.status_code == 200 else {}
    check("A5-6", "이전 턴 '왼쪽' + 손 up + '이쪽으로 3칸 가' → move(left, 3)",
          data.get("tool") == "move" and data.get("args") == {"direction": "left", "steps": 3},
          f"{sec:.1f}s → {data.get('tool')} {data.get('args', '')}")


    print("\n[개선 ②] 제안(guess)에 '응' → 그 방향으로 이동")
    history = [{"role": "user", "content": f"[YOLO 객체 인식] {YOLO_SUMMARY}\n"
                                           f"[VLM 장면 설명] {VLM_DESCRIPTION}\n"
                                           f"[손 제스처] 가리키는 방향: 손 없음\n\n"
                                           f"[사용자 질문] 저쪽으로 2칸 가"},
               {"role": "assistant", "content": json.dumps(
                   {"tool": "ask", "args": {"steps": 2, "guess": "right"},
                    "message": "오른쪽으로 2칸 갈까요?"}, ensure_ascii=False)}]
    r, sec = llm(client, "응", history=history)
    data = r.json() if r.status_code == 200 else {}
    check("개선2", "ask(guess=right, steps=2) 뒤 '응' → move(right, 2)",
          data.get("tool") == "move" and data.get("args") == {"direction": "right", "steps": 2},
          f"{sec:.1f}s → {data.get('tool')} {data.get('args', '')}")

    print("\n[개선 ⑤] 연속 명령 → 첫 이동 + then")
    r, sec = llm(client, "오른쪽 2칸 가고 위로 1칸")
    data = r.json() if r.status_code == 200 else {}
    check("개선5", "'오른쪽 2칸 가고 위로 1칸' → move(right, 2) + then [up 1]",
          data.get("tool") == "move" and data.get("args") == {"direction": "right", "steps": 2}
          and data.get("then") == [{"direction": "up", "steps": 1}],
          f"{sec:.1f}s → {data.get('tool')} {data.get('args', '')} then={data.get('then')}")
    if data:
        check_shape(data)

    print("\n[R10] 출력 대상별 답변 문구 ― ip 가 있으면(기기 탭) 칸 수 없이 방향만")
    # 오늘 서버는 기기 탭 질문도 PC LLM 이 고른다 ― 기기에 연결하지 않으므로 아무 주소나 된다
    r1, _ = llm(client, "오른쪽으로 3칸 가")
    r2, _ = llm(client, "오른쪽으로 3칸 가", ip="127.0.0.1")
    a, b = (r.json() if r.status_code == 200 else {} for r in (r1, r2))
    check("R10", "로컬 PC 탭 · 기기 탭의 tool · args 가 같다",
          a and a.get("tool") == b.get("tool") and a.get("args") == b.get("args"),
          f"로컬 → {a.get('tool')} {a.get('args')} / 기기 → {b.get('tool')} {b.get('args')}")
    check("R10", "로컬 PC 탭(ip 없음) move → 칸 수 포함 (2회차 문구)", "3칸" in a.get("message", ""),
          f"{a.get('message')!r}")
    check("R10", "기기 탭(ip 있음) move → 칸 수 없음", no_grid_talk(b) and "오른쪽" in b.get("message", ""),
          f"{b.get('message')!r}")
    for prompt, tool in (("오른쪽 2칸 가고 위로 1칸", "move"), ("저쪽으로 2칸 가", "ask")):
        r, _ = llm(client, prompt, ip="127.0.0.1")
        data = r.json() if r.status_code == 200 else {}
        check("R10", f"기기 탭 {prompt!r} → {tool} · 칸 수 없음",
              data.get("tool") == tool and no_grid_talk(data),
              f"{data.get('tool')} {data.get('args', '')} then={data.get('then')} {data.get('message')!r}")


def output_move(client, ip, data):
    """화면(index.html)처럼 move 의 이동마다 A8(OLED) · A7(LED, 좌우만)을 호출한다. 표시한 글자 목록을 돌려준다."""
    shown = []
    if data.get("tool") != "move":
        return shown
    for move in [data["args"]] + data.get("then", []):
        r = client.post("/api/oled-display", json={"ip": ip, "direction": move["direction"]})
        if r.status_code == 200:
            shown.append(OLED_TEXT[move["direction"]])
        if move["direction"] in ("left", "right"):
            client.post("/api/robot-signal", json={"ip": ip, "direction": move["direction"]})
    return shown


def run_device(client, ip):
    device = f"http://{ip}:8080"
    print(f"\n[D1 ~ D3] 기기 서버 직접 확인 ({device})")
    try:
        with httpx.stream("GET", device + "/stream.mjpg", timeout=10) as r:
            head = next(r.iter_raw(), b"")
            ctype = r.headers.get("content-type", "")
    except httpx.HTTPError as exc:
        head, ctype = b"", type(exc).__name__
    check("D1", "/stream.mjpg → multipart MJPEG", "multipart/x-mixed-replace" in ctype and b"--FRAME" in head,
          ctype)
    r = httpx.get(device + "/gpio-blink", params={"pin": 17}, timeout=10)
    check("D2", "/gpio-blink?pin=17 → {ok: true}", r.status_code == 200 and r.json().get("ok") is True,
          f"{r.status_code} {r.text[:60]}")
    r = httpx.get(device + "/gpio-blink", params={"pin": "abc"}, timeout=10)
    check("D2", "/gpio-blink?pin=abc → 400", r.status_code == 400, f"{r.status_code}")
    r = httpx.get(device + "/oled-display", params={"text": "RIGHT"}, timeout=10)
    check("D3", "/oled-display?text=RIGHT → 200", r.status_code == 200, f"{r.status_code} {r.text[:60]}")
    r = httpx.get(device + "/oled-display", timeout=10)
    check("D3", "/oled-display 글자 없음 → 400", r.status_code == 400, f"{r.status_code}")

    print("\n[A6 ~ A8 · R8] PC 중계")
    try:
        with client.stream("GET", "/api/camera-stream", params={"ip": ip}) as r:
            head = next(r.iter_raw(), b"")
            status = r.status_code
    except httpx.HTTPError:
        head, status = b"", None
    check("A6", "중계 스트림에 MJPEG 프레임", status == 200 and b"--FRAME" in head, f"status={status}")
    for d in ("left", "right"):
        r = client.post("/api/robot-signal", json={"ip": ip, "direction": d})
        check("A7", f"LED {d} → {{ok: true}}", r.status_code == 200 and r.json().get("ok") is True,
              f"{r.status_code}")
    for d in OLED_TEXT:
        r = client.post("/api/oled-display", json={"ip": ip, "direction": d})
        check("R8", f"OLED {d} → {OLED_TEXT[d]}", r.status_code == 200 and r.json().get("ok") is True,
              f"{r.status_code}")

    print("\n[F104 · R8 · R10] 기기 탭 질문 → move 를 OLED · LED 로 (화면과 같은 순서)")
    for prompt, expected in (("오른쪽으로 3칸 가", ["RIGHT"]), ("위로 2칸 가", ["UP"]),
                             ("오른쪽 2칸 가고 위로 1칸", ["RIGHT", "UP"])):
        r, sec = llm(client, prompt, ip=ip)
        data = r.json() if r.status_code == 200 else {}
        shown = output_move(client, ip, data)
        check("R8", f"{prompt!r} → OLED {' → '.join(expected) or '없음'}", shown == expected,
              f"{sec:.1f}s → {data.get('tool')} {data.get('args', '')} then={data.get('then')} OLED={shown}")
        check("R10", "기기 탭 답변에 칸 수 없음", no_grid_talk(data), f"{data.get('message')!r}")
    r, _ = llm(client, "저쪽으로 가", ip=ip)
    data = r.json() if r.status_code == 200 else {}
    check("F104", "'저쪽으로 가' → ask (OLED · LED 출력 없음)",
          data.get("tool") == "ask" and output_move(client, ip, data) == [],
          f"{data.get('tool')} {data.get('args', '')} {data.get('message')!r}")


def summarize():
    print("\n" + "-" * 60)
    by_item = {}
    for item_id, ok in results:
        by_item.setdefault(item_id.split("-")[0], []).append(ok)
    print("  ".join(f"{k} {sum(v)}/{len(v)}" for k, v in sorted(by_item.items())))
    passed = sum(ok for _, ok in results)
    print(f"전체 {passed}/{len(results)} PASS" +
          ("" if passed == len(results) else "  ― FAIL 번호를 명세서의 'API 및 규칙 명세' 표에서 찾는다"))
    return passed == len(results)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--quick", action="store_true", help="모델 추론 없이 화면 · 파일 · 오류 응답만")
    parser.add_argument("--device", metavar="IP", help="라즈베리파이 IP ― 기기가 필요한 항목(D1~D3, A6~A8)도 실행")
    args = parser.parse_args()
    with httpx.Client(base_url=args.url, timeout=600) as client:
        try:
            client.get("/")
        except httpx.ConnectError:
            sys.exit(f"서버에 연결할 수 없습니다: {args.url}  ― 터미널 1 에서 서버 먼저")
        run_quick(client)
        if not args.quick:
            run_models(client)
        if args.device:
            run_device(client, args.device)
        ok = summarize()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
