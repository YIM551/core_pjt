# -*- coding: utf-8 -*-
"""[page 16] 실습 1-1 ― 서버가 API 설계(../API_설계.md)대로 동작하는지 번호별로 확인한다.

설계의 항목 번호(A1~A5, R1~R5)마다 요청을 보내고 PASS / FAIL 을 찍는다.
  - Part 1 : 2일차 서버(실습 4-3)에 돌려서 '오늘 무엇을 만들어야 하는지' 를 본다
  - Part 4 : 오늘 완성한 서버에 돌려서 '설계대로 만들었음' 을 확인한다

서버를 먼저 띄운 뒤 (터미널 1), 다른 터미널에서 실행한다.

실행:
    python API_검증.py            # 전체 (모델 추론 포함, CPU 약 2분)
    python API_검증.py --quick    # 모델 추론 없이 화면 · 파일 · 오류 응답만 (몇 초)
"""
import argparse
import io
import json
import sys
import time
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_JPG = BASE_DIR.parents[1] / "2회차_day2" / "samples" / "sample.jpg"

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
]

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


def llm(client, prompt, gesture="unknown", history=None):
    body = {"prompt": prompt, "yolo_summary": YOLO_SUMMARY, "vlm_description": VLM_DESCRIPTION,
            "gesture_direction": gesture, "history": history or []}
    t0 = time.perf_counter()
    response = client.post("/api/llm-answer", json=body)
    return response, time.perf_counter() - t0


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
    else:                              # describe 는 {}, ask 는 {} 또는 {"steps": 이미 아는 칸 수}
        ok = isinstance(args, dict) and set(args) <= ({"steps"} if tool == "ask" else set())
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
        check(item_id, f"{title} : {prompt!r}",
              data.get("tool") == tool and data.get("args") == args, f"{sec:.1f}s → {got}")
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


def summarize():
    print("\n" + "-" * 60)
    by_item = {}
    for item_id, ok in results:
        by_item.setdefault(item_id.split("-")[0], []).append(ok)
    print("  ".join(f"{k} {sum(v)}/{len(v)}" for k, v in sorted(by_item.items())))
    passed = sum(ok for _, ok in results)
    print(f"전체 {passed}/{len(results)} PASS" +
          ("" if passed == len(results) else "  ― FAIL 번호를 ../API_설계.md 에서 찾는다"))
    return passed == len(results)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--quick", action="store_true", help="모델 추론 없이 화면 · 파일 · 오류 응답만")
    args = parser.parse_args()
    with httpx.Client(base_url=args.url, timeout=600) as client:
        try:
            client.get("/")
        except httpx.ConnectError:
            sys.exit(f"서버에 연결할 수 없습니다: {args.url}  ― 터미널 1 에서 서버 먼저")
        run_quick(client)
        if not args.quick:
            run_models(client)
        ok = summarize()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
