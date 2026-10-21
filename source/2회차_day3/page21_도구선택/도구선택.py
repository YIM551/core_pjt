# -*- coding: utf-8 -*-
"""[page 21] 실습 2-1 ― 의도 파악 = 도구 고르기. LLM 이 move / describe / ask 중 하나를 고른다.

2일차 실습 4-2 에서 답을 JSON 으로 받았다. 오늘은 그 JSON 이 '호출할 도구와 인자' 다.
  - move(direction, steps) : 로봇 이동
  - describe()             : 이동 없이 장면 설명
  - ask()                  : 이동하라는데 방향을 모르면 되묻기

같은 인식 결과(2일차 대시보드 실측)에 질문 8개를 던져, 고른 도구가 기대와 같은지 채점한다.

실행:
    python 도구선택.py
    python 도구선택.py --rule "..."         # 시스템 프롬프트에 규칙 한 줄 추가 (도전 문제 1)
    python 도구선택.py --question "위 2칸 가" --gesture unknown
"""
import argparse
import json
import os
import re
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[2]
LLM_GGUF_PATH = PROJECT_ROOT / "models" / "Qwen3-4B-Q4_K_M.gguf"

TOOLS = ("move", "describe", "ask")
DIRECTIONS = ("up", "down", "left", "right")
DIRECTION_KO = {"up": "위", "down": "아래", "left": "왼쪽", "right": "오른쪽"}
DIRECTION_ALIASES = {"위": "up", "아래": "down", "왼쪽": "left", "오른쪽": "right"}
MAX_STEPS = 10
ASK_MESSAGE = "어느 쪽으로 갈까요? 방향을 말하거나 손으로 가리켜 주세요."
FALLBACK_MESSAGE = "답변을 생성하지 못했습니다."

SYSTEM_PROMPT = (
    "너는 격자 시뮬레이터의 로봇을 조종하는 어시스턴트다. 인식 모델이 만든 Text 블록과 "
    "사용자 질문을 보고 사용자의 의도를 파악해 도구 하나를 고른다.\n"
    "도구:\n"
    "- move(direction, steps): 로봇 이동. direction 은 up|down|left|right, steps 는 1~10 정수\n"
    "- describe(): 이동 없이 장면에 대한 질문에 답한다\n"
    "- ask(): 이동하라는데 방향을 알 수 없을 때 사용자에게 되묻는다\n"
    "규칙:\n"
    "- 방향은 [사용자 질문]에 있으면 그것을, 없으면 [손 제스처]를 따른다. "
    "둘 다 없으면 move 가 아니라 ask 를 고른다.\n"
    "- 칸 수가 없으면 1 이다.\n"
    "- 사람 · 물체의 개수는 반드시 [YOLO 객체 인식] 의 숫자를 쓴다. "
    "[VLM 장면 설명] 에 나온 개수는 쓰지 않는다.\n"
    "- 상황과 분위기는 [VLM 장면 설명] 을 참고한다.\n"
    "반드시 아래 JSON 한 개로만 답하고, 다른 글은 쓰지 마라. "
    "args 는 move 일 때만 채우고 나머지 도구는 {} 로 둔다.\n"
    '{"tool": "move|describe|ask", "args": {"direction": "up", "steps": 1}, '
    '"message": "<사용자에게 보일 한두 문장>"}'
)

# 2일차 실습 4-3 대시보드의 실측 인식 결과 (sample.jpg)
YOLO_SUMMARY = "person 3개, bus 1개"
VLM_DESCRIPTION = "버스 앞에 두 명의 사람이 서 있습니다, 장애물 없음."

# (질문, 손 방향, 기대 도구, 기대 인자)
CASES = [
    ("앞에 뭐가 있어?", "unknown", "describe", {}),
    ("사람이 몇 명이야?", "unknown", "describe", {}),
    ("오른쪽으로 3칸 가", "unknown", "move", {"direction": "right", "steps": 3}),
    ("아래로 한 칸만 가줘", "unknown", "move", {"direction": "down", "steps": 1}),
    ("왼쪽으로, 5칸 이동.", "unknown", "move", {"direction": "left", "steps": 5}),
    ("이쪽으로 2칸 이동해", "up", "move", {"direction": "up", "steps": 2}),
    ("저쪽으로 가", "unknown", "ask", {}),
    ("버스 있는 쪽으로 가", "unknown", "ask", {}),
]

_THINK_RE = re.compile(r"<think>.*?(?:</think>|\Z)", re.DOTALL)


def load_llm():
    if not LLM_GGUF_PATH.exists():
        raise SystemExit(f"LLM 파일이 없습니다: {LLM_GGUF_PATH}")
    from llama_cpp import Llama

    return Llama(model_path=str(LLM_GGUF_PATH), n_ctx=4096,
                 n_threads=os.cpu_count(), verbose=False)


def build_user_content(prompt: str, gesture_direction: str) -> str:
    """출처별 블록 + 질문 (2일차 실습 4-1 과 같은 형식)."""
    direction = DIRECTION_KO.get(gesture_direction, "인식 불가")
    return (
        f"[YOLO 객체 인식] {YOLO_SUMMARY}\n"
        f"[VLM 장면 설명] {VLM_DESCRIPTION}\n"
        f"[손 제스처] 가리키는 방향: {direction}\n\n"
        f"[사용자 질문] {prompt}"
    )


def ask_llm(model, system_prompt: str, user_content: str) -> str:
    response = model.create_chat_completion(
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": user_content + " /no_think"}],
        max_tokens=200, temperature=0.0)
    return _THINK_RE.sub("", response["choices"][0]["message"]["content"] or "").strip()


# ---------------------------------------------------------------------------
# 방어 파싱 ― 2일차 실습 4-2 의 파서를 도구 호출용으로 넓힌 것
# ---------------------------------------------------------------------------
def extract_json(text: str):
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def to_direction(value) -> str:
    value = str(value).strip().lower()
    value = DIRECTION_ALIASES.get(value, value)
    return value if value in DIRECTIONS else "unknown"


def to_steps(value) -> int:
    try:
        steps = int(value)
    except (TypeError, ValueError):
        return 1
    return min(max(steps, 1), MAX_STEPS)


def parse_tool_call(raw: str) -> dict:
    """모델이 무엇을 내놓든 {tool, args, message} 모양을 보장한다."""
    data = extract_json(raw)
    if data is None:                       # JSON 이 아니면 설명으로 본다
        return {"tool": "describe", "args": {}, "message": raw or FALLBACK_MESSAGE}
    tool = str(data.get("tool", "")).strip().lower()
    if tool not in TOOLS:                  # 없는 도구 → describe
        tool = "describe"
    message = str(data.get("message", "")).strip()
    args = {}
    if tool == "move":
        raw_args = data["args"] if isinstance(data.get("args"), dict) else data
        direction = to_direction(raw_args.get("direction"))
        if direction == "unknown":         # 방향 없는 move → ask
            tool = "ask"
        else:
            args = {"direction": direction,
                    "steps": to_steps(raw_args.get("steps"))}
    if tool == "ask" and not message:
        message = ASK_MESSAGE
    return {"tool": tool, "args": args, "message": message or FALLBACK_MESSAGE}


def fmt(call) -> str:
    a = call["args"]
    return f"{call['tool']}({a['direction']}, {a['steps']})" if a else f"{call['tool']}()"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rule", help="시스템 프롬프트 규칙 끝에 한 줄 추가")
    parser.add_argument("--question", help="이 질문 하나만 실행")
    parser.add_argument("--gesture", default="unknown", choices=DIRECTIONS + ("unknown",))
    args = parser.parse_args()

    system_prompt = SYSTEM_PROMPT
    if args.rule:
        system_prompt = SYSTEM_PROMPT.replace("반드시 아래 JSON", f"- {args.rule}\n반드시 아래 JSON")
        print(f"추가 규칙 : {args.rule}\n")
    cases = [(args.question, args.gesture, None, None)] if args.question else CASES

    print("모델 로딩 중...")
    model = load_llm()
    print(f"[인식 결과] YOLO: {YOLO_SUMMARY} / VLM: {VLM_DESCRIPTION}\n")

    correct = 0
    for question, gesture, want_tool, want_args in cases:
        t0 = time.perf_counter()
        call = parse_tool_call(ask_llm(model, system_prompt, build_user_content(question, gesture)))
        sec = time.perf_counter() - t0
        if want_tool is None:
            mark, expect = "  ", ""
        else:
            ok = call["tool"] == want_tool and call["args"] == want_args
            correct += ok
            mark = "O " if ok else "X "
            expect = "" if ok else f"   (기대 {fmt({'tool': want_tool, 'args': want_args})})"
        hand = "" if gesture == "unknown" else f" [손: {DIRECTION_KO[gesture]}]"
        print(f"{mark}{sec:4.1f}s  {question}{hand}")
        print(f"      → {fmt(call)}  \"{call['message'][:34]}\"{expect}")
    if not args.question:
        print(f"\n정답 {correct}/{len(cases)}")


if __name__ == "__main__":
    main()
