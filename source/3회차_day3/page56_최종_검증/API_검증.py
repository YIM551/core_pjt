# -*- coding: utf-8 -*-
"""[page 56] 최종 검증 ― A1 ~ A9 · D1 ~ D5 · R1 ~ R10 을 스크립트 하나로 (F304).

page32_API_검증 의 검증 스크립트에 F301(도구별 시나리오) · F302(음성 되묻기) 항목을 더했다.
번호는 명세서(16-C-3-03) 'API 및 규칙 명세' 표 번호다. FAIL 이면 번호로 원인을 좁힌다 ―
A 번호 = PC 코드, D 번호 = 기기 서버 · 배선, R 번호 = 규칙 함수.

서버를 먼저 띄운 뒤 (터미널 1 : ../page30_음성경로_통합/대시보드_음성통합.py), 다른 터미널에서 실행한다.

실행:
    python API_검증.py --offline                        # 모의 모델·기기 응답으로 규칙, 형식, 장애 처리
    python API_검증.py --timings --device 192.168.0.10  # PC 모델과 선택한 Pi 모델의 HTTP 응답 시간만 측정
    python API_검증.py --quick                          # 기기 없이 ― 화면, 정적 파일, 400 · 502
    python API_검증.py                                  # PC 모델 추론 및 기존 응답 호환성 포함
    python API_검증.py --device 192.168.0.10            # 전체 + 라즈베리파이 항목
    python API_검증.py --quick --device 192.168.0.10    # PC 인식 모델 없이 라즈베리파이 항목만 더한다
"""
import argparse
import io
import json
import sys
import time
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_JPG = BASE_DIR.parents[1] / "3회차_day1" / "samples" / "sample.jpg"

# A5 는 A3 · A4 결과와 무관하게 같은 입력으로 확인한다 (2일차 대시보드 실측값)
YOLO_SUMMARY = "person 3개, bus 1개"
VLM_DESCRIPTION = "버스 앞에 두 명의 사람이 서 있습니다, 장애물 없음."
EXPECTED_SCENE = f"감지된 물체: {YOLO_SUMMARY}. {VLM_DESCRIPTION}"

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
DIRECTIONS = ("up", "down", "left", "right")
OLED_TEXT = {"left": "LEFT", "right": "RIGHT", "up": "UP", "down": "DOWN"}

results = []


def check(item_id, title, ok, detail=""):
    results.append((item_id, bool(ok)))
    mark = "PASS" if ok else "FAIL"
    print(f"  {mark}  [{item_id:<4}] {title}" + (f"  ― {detail}" if detail else ""), flush=True)


def json_object(response):
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def error_code(response):
    return json_object(response).get("error")


def args_without_guess(data):
    args = data.get("args")
    if isinstance(args, dict):
        return {k: v for k, v in args.items() if k != "guess"}
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
    return isinstance(message, str) and bool(message) and not any(
        word in message for word in ("칸", "로봇", "시뮬레이터", "격자"))


def check_shape(data):
    """A5 응답 형식 + R1 · R2 · R4 ― 모든 LLM 응답에 공통으로 적용한다."""
    missing = {"tool", "args", "need_more_info", "message", "user_content"} - set(data)
    check("A5", "응답 필드 5개", not missing, f"없음: {sorted(missing)}" if missing else "")
    tool, args = data.get("tool"), data.get("args")
    check("R1", "tool 은 move / describe / ask 중 하나", tool in ("move", "describe", "ask"),
          f"tool={tool!r}")
    if tool == "move":
        ok = isinstance(args, dict) and args.get("direction") in DIRECTIONS \
            and type(args.get("steps")) is int and 1 <= args["steps"] <= 10
    elif tool == "ask":                # {} 또는 {"steps": 이미 아는 칸 수, "guess": LLM 이 추측한 방향(개선 ②)}
        ok = isinstance(args, dict) and set(args) <= {"steps", "guess"} \
            and args.get("guess", "up") in DIRECTIONS \
            and ("steps" not in args or (type(args["steps"]) is int and 1 <= args["steps"] <= 10))
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
        check(item, f"{path} 빈 본문 → empty_image", r.status_code == 400 and error_code(r) == "empty_image",
              f"{r.status_code} {error_code(r)}")
        r = client.post(path, content=b"not an image")
        check(item, f"{path} 이미지 아님 → invalid_image", r.status_code == 400 and error_code(r) == "invalid_image",
              f"{r.status_code} {error_code(r)}")
    r = client.post("/api/llm-answer", content=b"{broken", headers={"Content-Type": "application/json"})
    check("A5", "JSON 아님 → invalid_json", r.status_code == 400 and error_code(r) == "invalid_json",
          f"{r.status_code} {error_code(r)}")
    r = client.post("/api/llm-answer", json={"prompt": "   "})
    check("A5", "빈 prompt → empty_prompt", r.status_code == 400 and error_code(r) == "empty_prompt",
          f"{r.status_code} {error_code(r)}")

    print(f"\n[A6 ~ A9 · R6 · R8] 3회차 중계 ― 잘못된 요청 → 400, 연결할 수 없는 기기({UNREACHABLE_IP}) → 502")
    r = client.get("/api/camera-stream")
    check("A6", "ip 없음 → invalid_request", r.status_code == 400 and error_code(r) == "invalid_request",
          f"{r.status_code} {error_code(r)}")
    r = client.get("/api/camera-stream", params={"ip": UNREACHABLE_IP})
    check("A6", "연결 불가 → 502 camera_unreachable",
          r.status_code == 502 and error_code(r) == "camera_unreachable", f"{r.status_code} {error_code(r)}")
    for path, item in (("/api/robot-signal", "A7"), ("/api/oled-display", "A8")):
        r = client.post(path, content=b"{broken", headers={"Content-Type": "application/json"})
        check(item, f"{path} JSON 아님 → invalid_json", r.status_code == 400 and error_code(r) == "invalid_json",
              f"{r.status_code} {error_code(r)}")
        r = client.post(path, json={"ip": UNREACHABLE_IP, "direction": "front"})
        check(item, f"{path} 없는 방향 → invalid_request", r.status_code == 400 and error_code(r) == "invalid_request",
              f"{r.status_code} {error_code(r)}")
        r = client.post(path, json={"ip": UNREACHABLE_IP, "direction": "left"})
        check(item, f"{path} 연결 불가 → 502 device_unreachable",
              r.status_code == 502 and error_code(r) == "device_unreachable", f"{r.status_code} {error_code(r)}")
    for d in ("up", "down"):
        r = client.post("/api/robot-signal", json={"ip": UNREACHABLE_IP, "direction": d})
        check("R8", f"LED 는 좌우만 ― A7 {d} → invalid_request", r.status_code == 400 and error_code(r) == "invalid_request",
              f"{r.status_code} {error_code(r)}")
    r = client.get("/api/voice-poll", params={"ip": UNREACHABLE_IP})
    check("A9", "연결 불가 → 502 device_unreachable",
          r.status_code == 502 and error_code(r) == "device_unreachable", f"{r.status_code} {error_code(r)}")
    r, _ = llm(client, "오른쪽으로 2칸 가", source="voice", ip=UNREACHABLE_IP)
    check("R6", "A5 voice + 연결 불가 → 502 device_llm_unreachable",
          r.status_code == 502 and error_code(r) == "device_llm_unreachable", f"{r.status_code} {error_code(r)}")
    r, _ = llm(client, "오른쪽으로 2칸 가", source="device", ip=UNREACHABLE_IP)
    check("R6", "A5 device(기기 탭 타이핑) + 연결 불가 → 502 device_llm_unreachable",
          r.status_code == 502 and error_code(r) == "device_llm_unreachable", f"{r.status_code} {error_code(r)}")


def valid_detection(obj, width, height):
    if not isinstance(obj, dict) or not isinstance(obj.get("label"), str) or not obj["label"].strip():
        return False
    confidence, box = obj.get("confidence"), obj.get("box")
    if type(confidence) not in (int, float) or not 0 <= confidence <= 1:
        return False
    if not isinstance(box, list) or len(box) != 4 or not all(type(n) in (int, float) for n in box):
        return False
    return 0 <= box[0] <= box[2] <= width and 0 <= box[1] <= box[3] <= height


def measure_endpoint(client, name, url, validate, **request):
    """같은 본문을 네 번 POST한다. JSON 확인은 타이머 밖에서 수행한다."""
    elapsed = []
    for attempt in range(4):
        start = time.perf_counter()
        response = client.post(url, **request)
        elapsed.append(time.perf_counter() - start)
        data = json_object(response)
        if response.status_code != 200 or not validate(data):
            trial = "워밍업" if attempt == 0 else f"{attempt}회"
            raise ValueError(f"{name} {trial} 응답 검증 실패 (HTTP {response.status_code}, {response.text[:240]})")
    average = sum(elapsed[1:]) / 3
    print(f"| {name} | " + " | ".join(f"{value:.3f}" for value in (*elapsed, average)) + " |", flush=True)
    return data


def run_timings(client, ip):
    from PIL import Image

    image = SAMPLE_JPG.read_bytes()
    with Image.open(io.BytesIO(image)) as sample:
        width, height = sample.size
    prompt = "오른쪽으로 3칸 가"
    print(f"입력: {SAMPLE_JPG.name} ({width}×{height}), 도구 선택 질문 {prompt!r}, 빈 history.")
    print("단위는 초. 동일 입력으로 순차 요청하며 HTTP 송수신·서버 처리·추론 시간을 포함합니다.")
    print("| 모델과 API | 워밍업 (평균 제외) | 1회 | 2회 | 3회 | 평균 |")
    print("| --- | ---: | ---: | ---: | ---: | ---: |", flush=True)

    def has_detections(data):
        found = data.get("objects")
        return isinstance(found, list) and bool(found) and all(valid_detection(obj, width, height) for obj in found)

    def moves_right(data):
        return data.get("tool") == "move" and data.get("args") == {"direction": "right", "steps": 3}

    measure_endpoint(client, "YOLO11n · PC A3", "/api/yolo-detect", has_detections, content=image)
    measure_endpoint(client, "Qwen2.5-VL-3B · PC A4", "/api/vlm-describe",
                     lambda data: isinstance(data.get("description"), str) and data["description"].strip(),
                     content=image)
    body = {"prompt": prompt, "yolo_summary": YOLO_SUMMARY, "vlm_description": VLM_DESCRIPTION,
            "gesture_direction": "unknown", "history": []}
    last_pc = measure_endpoint(client, "Qwen3-4B · PC A5", "/api/llm-answer",
                               lambda data: moves_right(data) and isinstance(data.get("user_content"), str)
                               and bool(data["user_content"].strip()), json=body)
    if ip:
        # A5가 실제 추론에 사용한 문자열을 그대로 Pi에 보낸다.
        measure_endpoint(client, "Qwen3-1.7B · Pi D5", f"http://{ip}:8080/llm-infer", moves_right,
                         json={"user_content": last_pc["user_content"], "history": []})


def run_models(client):
    image = SAMPLE_JPG.read_bytes()
    from PIL import Image
    width, height = Image.open(io.BytesIO(image)).size

    print(f"\n[A3 · A4] 인식 ({SAMPLE_JPG.name} {width}x{height})")
    t0 = time.perf_counter()
    r = client.post("/api/yolo-detect", content=image)
    objects = json_object(r).get("objects") if r.status_code == 200 else None
    ok = isinstance(objects, list) and bool(objects) and all(valid_detection(o, width, height) for o in objects)
    check("A3", "objects : label · confidence · box(픽셀 좌표)", ok,
          f"{time.perf_counter() - t0:.1f}s  " + (", ".join(o["label"] for o in objects) if ok else repr(objects)))
    t0 = time.perf_counter()
    r = client.post("/api/vlm-describe", content=image)
    text = json_object(r).get("description") if r.status_code == 200 else None
    check("A4", "description 문자열", isinstance(text, str) and text.strip(),
          f"{time.perf_counter() - t0:.1f}s  {text!r}")

    print("\n[A5 · R3] 의도 파악 → 도구 선택")
    for item_id, title, prompt, gesture, tool, args in TOOL_CASES:
        r, sec = llm(client, prompt, gesture)
        data = json_object(r) if r.status_code == 200 else {}
        got = f"{data.get('tool')} {data.get('args', '')}"
        got_args = args_without_guess(data)  # guess 는 LLM 추측이라 비교하지 않는다
        check(item_id, f"{title} : {prompt!r}",
              data.get("tool") == tool and got_args == args, f"{sec:.1f}s → {got}")
        if data:
            check_shape(data)

    print("\n[R5] 되묻기 → 방향을 답하면 이어서 이동")
    r, _ = llm(client, "저쪽으로 2칸 가")
    first = json_object(r) if r.status_code == 200 else {}
    check("R5", "1턴 '저쪽으로 2칸 가' → ask", first.get("tool") == "ask",
          f"→ {first.get('tool')} {first.get('args', '')}")
    history = [{"role": "user", "content": first.get("user_content", "")},
               {"role": "assistant", "content": json.dumps(
                   {k: first.get(k) for k in ("tool", "args", "message")}, ensure_ascii=False)}]
    r, sec = llm(client, "왼쪽", history=history)
    second = json_object(r) if r.status_code == 200 else {}
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
    data = json_object(r) if r.status_code == 200 else {}
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
    data = json_object(r) if r.status_code == 200 else {}
    check("개선2", "ask(guess=right, steps=2) 뒤 '응' → move(right, 2)",
          data.get("tool") == "move" and data.get("args") == {"direction": "right", "steps": 2},
          f"{sec:.1f}s → {data.get('tool')} {data.get('args', '')}")

    print("\n[개선 ⑤] 연속 명령 → 첫 이동 + then")
    r, sec = llm(client, "오른쪽 2칸 가고 위로 1칸")
    data = json_object(r) if r.status_code == 200 else {}
    check("개선5", "'오른쪽 2칸 가고 위로 1칸' → move(right, 2) + then [up 1]",
          data.get("tool") == "move" and data.get("args") == {"direction": "right", "steps": 2}
          and data.get("then") == [{"direction": "up", "steps": 1}],
          f"{sec:.1f}s → {data.get('tool')} {data.get('args', '')} then={data.get('then')}")
    if data:
        check_shape(data)

    print("\n[R9] source 없는 요청 = source 'text' 요청 (2회차와 같은 경로)")
    r1, _ = llm(client, "오른쪽으로 3칸 가")
    r2, _ = llm(client, "오른쪽으로 3칸 가", source="text", ip="127.0.0.1")
    a, b = (json_object(r) if r.status_code == 200 else {} for r in (r1, r2))
    check("R9", "같은 tool · args", a and a.get("tool") == b.get("tool") and a.get("args") == b.get("args"),
          f"없음 → {a.get('tool')} {a.get('args')} / text → {b.get('tool')} {b.get('args')}")

    print("\n[R10] 출력 대상별 답변 문구 ― ip 가 있으면(기기 탭) 칸 수 없이 방향만")
    # ip 만 있고 source 가 text 면 PC LLM 을 쓴다 ― 기기에 연결하지 않으므로 아무 주소나 된다
    check("R10", "로컬 PC 탭(ip 없음) move → 칸 수 포함 (2회차 문구)", "3칸" in a.get("message", ""),
          f"{a.get('message')!r}")
    check("R10", "기기 탭(ip 있음) move → 칸 수 없음", no_grid_talk(b) and "오른쪽" in b.get("message", ""),
          f"{b.get('message')!r}")
    for prompt, tool in (("오른쪽 2칸 가고 위로 1칸", "move"), ("저쪽으로 2칸 가", "ask")):
        r, _ = llm(client, prompt, source="text", ip="127.0.0.1")
        data = json_object(r) if r.status_code == 200 else {}
        check("R10", f"기기 탭 {prompt!r} → {tool} · 칸 수 없음",
              data.get("tool") == tool and no_grid_talk(data),
              f"{data.get('tool')} {data.get('args', '')} then={data.get('then')} {data.get('message')!r}")


def history_of(data):
    """화면처럼 이번 턴(user_content + 도구 호출)을 history 로 만든다."""
    return [{"role": "user", "content": data.get("user_content", "")},
            {"role": "assistant", "content": json.dumps(
                {k: data.get(k) for k in ("tool", "args", "message")}, ensure_ascii=False)}]


def output_move(client, ip, data):
    """화면과 같은 순서로 요청한다. 반환값은 A8이 수락한 글자이며 실물 표시는 별도로 확인한다."""
    shown = []
    if data.get("tool") != "move":
        return shown
    then = data.get("then", [])
    if not isinstance(then, list):
        check("R8", "then은 후속 이동 목록", False, repr(then))
        return shown
    for move in [data.get("args"), *then]:
        direction = move.get("direction") if isinstance(move, dict) else None
        if direction not in DIRECTIONS:
            check("R8", "출력할 이동 방향", False, repr(move))
            continue
        body = {"ip": ip, "direction": direction}
        r = client.post("/api/oled-display", json=body)
        if r.status_code == 200 and json_object(r).get("ok") is True:
            shown.append(OLED_TEXT[direction])
        if direction in ("left", "right"):
            r = client.post("/api/robot-signal", json=body)
            check("R8", f"연속 출력 중 LED {direction} 요청 수락",
                  r.status_code == 200 and json_object(r).get("ok") is True, f"HTTP {r.status_code}")
    return shown


def has_frame_boundary(response):
    if response.status_code != 200:
        return False
    head = b""
    for chunk in response.iter_raw():
        head += chunk[:256 - len(head)]
        if b"--FRAME" in head:
            return True
        if len(head) >= 256:
            break
    return False


def check_voice_payload(item_id, response):
    data = json_object(response)
    seq, transcript = data.get("seq"), data.get("text")
    sequence = seq if type(seq) is int else None
    length = len(transcript) if isinstance(transcript, str) else None
    check(item_id, "음성 응답 {seq: int, text: str}",
          response.status_code == 200 and sequence is not None and length is not None,
          f"HTTP {response.status_code}, seq={sequence}, 글자 수={length}")


def run_device(client, ip):
    device = f"http://{ip}:8080"
    print(f"\n[D1 ~ D5] 기기 서버 직접 확인 ({device})")
    try:
        with httpx.stream("GET", device + "/stream.mjpg", timeout=10) as r:
            boundary = has_frame_boundary(r)
            ctype = r.headers.get("content-type", "")
    except httpx.HTTPError as exc:
        boundary, ctype = False, type(exc).__name__
    check("D1", "/stream.mjpg → multipart MJPEG", "multipart/x-mixed-replace" in ctype and boundary,
          ctype)
    r = httpx.get(device + "/gpio-blink", params={"pin": 17}, timeout=10)
    check("D2", "/gpio-blink?pin=17 → {ok: true}", r.status_code == 200 and json_object(r).get("ok") is True,
          f"{r.status_code} {r.text[:60]}")
    r = httpx.get(device + "/gpio-blink", params={"pin": "abc"}, timeout=10)
    check("D2", "/gpio-blink?pin=abc → 400", r.status_code == 400, f"{r.status_code}")
    r = httpx.get(device + "/oled-display", params={"text": "RIGHT"}, timeout=10)
    check("D3", "/oled-display?text=RIGHT → 200", r.status_code == 200, f"{r.status_code} {r.text[:60]}")
    check("D3", "연결된 OLED 드라이버의 표시 결과 → shown",
          json_object(r).get("oled") == "shown", f"oled={json_object(r).get('oled')!r}")
    r = httpx.get(device + "/oled-display", timeout=10)
    check("D3", "/oled-display 글자 없음 → 400", r.status_code == 400, f"{r.status_code}")
    r = httpx.get(device + "/voice-text", timeout=10)
    check_voice_payload("D4", r)
    r = httpx.post(device + "/llm-infer", json={}, timeout=10)
    check("D5", "/llm-infer user_content 없음 → empty_user_content", r.status_code == 400 and error_code(r) == "empty_user_content",
          f"{r.status_code} {error_code(r)}")
    r = httpx.post(device + "/llm-infer", content=b"{broken", timeout=10)
    check("D5", "/llm-infer JSON 아님 → invalid_json", r.status_code == 400 and error_code(r) == "invalid_json",
          f"{r.status_code} {error_code(r)}")
    t0 = time.perf_counter()
    r = httpx.post(device + "/llm-infer", timeout=180, json={
        "user_content": f"[YOLO 객체 인식] {YOLO_SUMMARY}\n[VLM 장면 설명] {VLM_DESCRIPTION}\n"
                        f"[손 제스처] 가리키는 방향: 손 없음\n\n[사용자 질문] 앞에 뭐가 있어?",
        "history": []})
    data = json_object(r) if r.status_code == 200 else {}
    check("D5", "/llm-infer → 도구·인자와 빈 message 반환",
          data.get("tool") in ("move", "describe", "ask") and isinstance(data.get("args"), dict)
          and data.get("message") == "", f"{time.perf_counter() - t0:.1f}s → {data}")

    print("\n[A6 ~ A9 · R8] PC 중계")
    try:
        with client.stream("GET", "/api/camera-stream", params={"ip": ip}) as r:
            boundary = has_frame_boundary(r)
            status = r.status_code
    except httpx.HTTPError:
        boundary, status = False, None
    check("A6", "중계 스트림에 MJPEG 프레임", status == 200 and boundary, f"status={status}")
    for d in ("left", "right"):
        r = client.post("/api/robot-signal", json={"ip": ip, "direction": d})
        check("A7", f"LED {d} → {{ok: true}}", r.status_code == 200 and json_object(r).get("ok") is True,
              f"{r.status_code}")
    for d in DIRECTIONS:
        r = client.post("/api/oled-display", json={"ip": ip, "direction": d})
        check("R8", f"OLED {d} → {OLED_TEXT[d]}", r.status_code == 200 and json_object(r).get("ok") is True,
              f"{r.status_code}")
    r = client.get("/api/voice-poll", params={"ip": ip})
    check_voice_payload("A9", r)

    print("\n[F301 · R9] 음성 경로(source=voice) ― 텍스트와 같은 규칙 · 같은 응답 형식")
    for item_id, title, prompt, gesture, tool, args in TOOL_CASES:
        r, sec = llm(client, prompt, gesture, source="voice", ip=ip)
        data = json_object(r) if r.status_code == 200 else {}
        got_args = args_without_guess(data)
        check("R9", f"[voice] {title} : {prompt!r}", data.get("tool") == tool and got_args == args,
              f"{sec:.1f}s → {data.get('tool')} {data.get('args', '')}")
        if tool == "describe":
            check("F301", "[voice] 장면 설명이 전송한 YOLO·VLM 결과와 일치",
                  data.get("message") == EXPECTED_SCENE, repr(data.get("message")))
        if data:
            check_shape(data)
            check("R10", "[voice] 기기 탭 답변에 칸 수 없음", no_grid_talk(data), f"{data.get('message')!r}")
    r, sec = llm(client, "오른쪽 2칸 가고 위로 1칸", source="voice", ip=ip)
    data = json_object(r) if r.status_code == 200 else {}
    shown = output_move(client, ip, data)
    check("F301", "[voice] '오른쪽 2칸 가고 위로 1칸' → OLED 요청 RIGHT → UP",
          data.get("args") == {"direction": "right", "steps": 2}
          and data.get("then") == [{"direction": "up", "steps": 1}] and shown == ["RIGHT", "UP"],
          f"{sec:.1f}s → {data.get('tool')} {data.get('args', '')} then={data.get('then')} OLED={shown}")
    r, sec = llm(client, "아래로 2칸 가", source="voice", ip=ip)
    data = json_object(r) if r.status_code == 200 else {}
    shown = output_move(client, ip, data)
    check("F301", "[voice] '아래로 2칸 가' → OLED 요청 DOWN (LED 없음)",
          data.get("args") == {"direction": "down", "steps": 2} and shown == ["DOWN"],
          f"{sec:.1f}s → {data.get('tool')} {data.get('args', '')} OLED={shown}")

    print("\n[F302 · R5] 음성 되묻기 대화")
    r, _ = llm(client, "저쪽으로 2칸 가", source="voice", ip=ip)
    first = json_object(r) if r.status_code == 200 else {}
    check("F302", "[voice] '저쪽으로 2칸 가' → ask", first.get("tool") == "ask",
          f"→ {first.get('tool')} {first.get('args', '')}")
    r, sec = llm(client, "왼쪽", history=history_of(first), source="voice", ip=ip)
    second = json_object(r) if r.status_code == 200 else {}
    shown = output_move(client, ip, second)
    check("F302", "[voice] 이어서 '왼쪽' → move(left, 2) · OLED LEFT",
          second.get("args") == {"direction": "left", "steps": 2} and shown == ["LEFT"],
          f"{sec:.1f}s → {second.get('tool')} {second.get('args', '')} OLED={shown}")
    guess_turn = {"tool": "ask", "args": {"steps": 2, "guess": "right"},
                  "message": "오른쪽으로 2칸 갈까요?", "user_content": first.get("user_content", "")}
    r, sec = llm(client, "응", history=history_of(guess_turn), source="voice", ip=ip)
    data = json_object(r) if r.status_code == 200 else {}
    shown = output_move(client, ip, data)
    check("F302", "[voice] 제안(right) 뒤 '응' → move(right, 2) · OLED RIGHT",
          data.get("args") == {"direction": "right", "steps": 2} and shown == ["RIGHT"],
          f"{sec:.1f}s → {data.get('tool')} {data.get('args', '')} OLED={shown}")
    # 음성 턴과 텍스트 턴이 섞여도 같은 history 로 이어진다 (R7 ― history 는 화면이 갖는다)
    # 기기 탭에서 타이핑한 질문은 source="device" ― 음성과 같은 기기 LLM 경로를 탄다
    r, sec = llm(client, "위", history=history_of(first), source="device", ip=ip)
    data = json_object(r) if r.status_code == 200 else {}
    check("R7", "음성 ask의 history를 타이핑 요청에 전달 → move(up, 2)",
          data.get("tool") == "move" and data.get("args") == {"direction": "up", "steps": 2},
          f"{sec:.1f}s → {data.get('tool')} {data.get('args', '')}")

    print("\n[R9 · R10] 기기 탭 타이핑(source=device) ― 음성과 같은 기기 LLM · 같은 규칙 · 칸 수 없는 답변")
    for item_id, title, prompt, gesture, tool, args in TOOL_CASES[:3]:
        r, sec = llm(client, prompt, gesture, source="device", ip=ip)
        data = json_object(r) if r.status_code == 200 else {}
        got_args = args_without_guess(data)
        check("R9", f"[device] {title} : {prompt!r}", data.get("tool") == tool and got_args == args,
              f"{sec:.1f}s → {data.get('tool')} {data.get('args', '')}")
        if tool == "describe":
            check("F301", "[device] 장면 설명이 전송한 YOLO·VLM 결과와 일치",
                  data.get("message") == EXPECTED_SCENE, repr(data.get("message")))
        if data:
            check("R10", "[device] 기기 탭 답변에 칸 수 없음", no_grid_talk(data), f"{data.get('message')!r}")


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
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--offline", action="store_true", help="모델·라즈베리파이·서버 없이 규칙과 장애 처리 검증")
    modes.add_argument("--quick", action="store_true", help="모델 추론 없이 화면 · 파일 · 오류 응답만")
    modes.add_argument("--timings", action="store_true", help="모델별 HTTP 응답 시간만 측정 (워밍업 1회, 측정 3회)")
    parser.add_argument("--device", metavar="IP", help="라즈베리파이 IP ― 기기가 필요한 항목(D1~D5, 음성 경로, F301 · F302 시나리오)도 실행")
    args = parser.parse_args()
    if args.offline:
        if args.device:
            parser.error("--offline은 단독으로 사용하세요.")
        from offline_checks import run_offline
        run_offline(check)
        sys.exit(0 if summarize() else 1)
    with httpx.Client(base_url=args.url, timeout=600) as client:
        if args.timings:
            try:
                run_timings(client, args.device)
            except (httpx.HTTPError, ValueError, OSError) as exc:
                sys.exit(f"측정 실패: {exc}")
            return
        try:
            client.get("/")
        except httpx.ConnectError:
            sys.exit(f"서버에 연결할 수 없습니다: {args.url}  ― 터미널 1 에서 서버 먼저")
        try:
            run_quick(client)
            if not args.quick:
                run_models(client)
            if args.device:
                run_device(client, args.device)
        except httpx.HTTPError as exc:
            check("HTTP", "연결 오류로 검증 중단", False, str(exc))
        ok = summarize()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
