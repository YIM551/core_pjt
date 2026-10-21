# -*- coding: utf-8 -*-
"""[page 31] 실습 3-1 ― 조건 분기는 코드로 보장한다 (근거 없는 move → ask, 되묻기 후 이어서).

실습 2-1 에서 LLM 은 방향을 모를 때 되묻지 않고 '오른쪽' 으로 추측했다 (6/8).
프롬프트에 규칙을 더해도 그대로였다 (도전 1). 그래서 판단을 코드로 옮긴다.
  [R3] LLM 이 move 를 골라도, 방향의 근거가 입력에 없으면 ask 로 바꾼다
       근거 = 질문(이전 턴 포함)의 방향어  또는  손 제스처 방향
  [R5] ask 로 되물은 뒤 사용자가 방향을 답하면, 이전 대화(history)와 함께 다시 판단한다.
       칸 수는 LLM 에게 기억시키지 않는다 ― ask 가 args 에 담아 둔 값을 코드가 이어 쓴다

실행:
    python 조건분기.py                           # 8문항 채점 + 되묻기 2턴
    python 조건분기.py --question "위 2칸 가"     # 한 문항만
    (도전 문제 2 는 ../page33_조건분기 폴더에서 한다)
"""
import argparse
import json
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[2]
LLM_GGUF_PATH = PROJECT_ROOT / "models" / "Qwen3-4B-Q4_K_M.gguf"

TOOLS = ("move", "describe", "ask")
DIRECTIONS = ("up", "down", "left", "right")
DIRECTION_KO = {"up": "위", "down": "아래", "left": "왼쪽", "right": "오른쪽"}
DIRECTION_TO = {"up": "위로", "down": "아래로", "left": "왼쪽으로", "right": "오른쪽으로"}
DIRECTION_ALIASES = {"위": "up", "아래": "down", "왼쪽": "left", "오른쪽": "right"}
MAX_STEPS = 10
ASK_MESSAGE = "어느 쪽으로 갈까요? 방향을 말하거나 손으로 가리켜 주세요."
FALLBACK_MESSAGE = "답변을 생성하지 못했습니다."

# 실습 2-1 과 같은 시스템 프롬프트 ― 프롬프트는 바꾸지 않고 코드만 더한다
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

YOLO_SUMMARY = "person 3개, bus 1개"
VLM_DESCRIPTION = "버스 앞에 두 명의 사람이 서 있습니다, 장애물 없음."

CASES = [
    ("앞에 뭐가 있어?", "unknown", "describe", {}),
    ("사람이 몇 명이야?", "unknown", "describe", {}),
    ("오른쪽으로 3칸 가", "unknown", "move", {"direction": "right", "steps": 3}),
    ("아래로 한 칸만 가줘", "unknown", "move", {"direction": "down", "steps": 1}),
    ("왼쪽으로, 5칸 이동.", "unknown", "move", {"direction": "left", "steps": 5}),
    ("이쪽으로 2칸 이동해", "up", "move", {"direction": "up", "steps": 2}),
    ("저쪽으로 가", "unknown", "ask", {"steps": 1}),
    ("버스 있는 쪽으로 가", "unknown", "ask", {"steps": 1}),
]

_THINK_RE = re.compile(r"<think>.*?(?:</think>|\Z)", re.DOTALL)


def load_llm():
    if not LLM_GGUF_PATH.exists():
        raise SystemExit(f"LLM 파일이 없습니다: {LLM_GGUF_PATH}")
    from llama_cpp import Llama

    return Llama(model_path=str(LLM_GGUF_PATH), n_ctx=4096,
                 n_threads=os.cpu_count(), verbose=False)


def build_user_content(prompt: str, gesture_direction: str) -> str:
    direction = DIRECTION_KO.get(gesture_direction, "인식 불가")
    return (
        f"[YOLO 객체 인식] {YOLO_SUMMARY}\n"
        f"[VLM 장면 설명] {VLM_DESCRIPTION}\n"
        f"[손 제스처] 가리키는 방향: {direction}\n\n"
        f"[사용자 질문] {prompt}"
    )


def ask_llm(model, messages: list) -> str:
    """history 까지 담긴 messages 로 묻는다. /no_think 는 마지막 질문에만 붙인다."""
    last = {"role": "user", "content": messages[-1]["content"] + " /no_think"}
    response = model.create_chat_completion(
        messages=messages[:-1] + [last], max_tokens=200, temperature=0.0)
    return _THINK_RE.sub("", response["choices"][0]["message"]["content"] or "").strip()


# ---------------------------------------------------------------------------
# 방어 파싱 ― 실습 2-1 과 같다
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


# ---------------------------------------------------------------------------
# 조건 분기 ― LLM 이 고른 도구를 코드가 한 번 더 검사한다
# ---------------------------------------------------------------------------
_DIRECTION_WORD_RE = re.compile(r"오른쪽|왼쪽|위쪽|위로|아래|\b(?:up|down|left|right)\b", re.I)
# 방향어 앞글자 → 방향 ('오른쪽 · 오른편', '아래쪽 · 아래로' 처럼 뒤가 달라도 같은 방향)
_WORD_TO_DIRECTION = {"오른": "right", "우측": "right", "왼": "left", "좌측": "left",
                      "아래": "down", "밑": "down", "위": "up"}
_STEPS_RE = re.compile(r"(\d+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*칸")
_KOREAN_NUMBER = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5,
                  "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
_QUESTION_RE = re.compile(r"\[사용자 질문\] (.*)")


def said_direction(text: str):
    """질문에 적힌 방향어 → up / down / left / right. 없으면 None."""
    match = _DIRECTION_WORD_RE.search(text)
    if not match:
        return None
    word = match.group(0).lower()
    return next((d for head, d in _WORD_TO_DIRECTION.items() if word.startswith(head)), word)


def said_steps(text: str):
    """질문에 적힌 칸 수 ('3칸', '세 칸'). 없으면 None."""
    match = _STEPS_RE.search(text)
    return to_steps(_KOREAN_NUMBER.get(match.group(1), match.group(1))) if match else None


def has_direction_evidence(prompt: str, history: list, gesture_direction: str) -> bool:
    """[R3] 방향의 근거가 입력에 있는가 ― 질문(이전 턴 포함)의 방향어 또는 손 제스처."""
    if gesture_direction in DIRECTIONS:
        return True
    questions = [prompt] + [m.group(1) for turn in history if turn["role"] == "user"
                            for m in [_QUESTION_RE.search(turn["content"])] if m]
    return any(_DIRECTION_WORD_RE.search(q) for q in questions)


def ask_for_direction(steps: int) -> dict:
    """[R3] 방향만 모른다 → 되묻는다. 이미 아는 칸 수는 args 에 기억해 둔다."""
    return {"tool": "ask", "args": {"steps": steps},
            "message": f"어느 쪽으로 {steps}칸 갈까요? 방향을 말하거나 손으로 가리켜 주세요."}


def move_with_steps(direction: str, steps: int) -> dict:
    """코드가 확정한 이동 ― 안내 문장도 확정한 인자에 맞춰 다시 쓴다."""
    return {"tool": "move", "args": {"direction": direction, "steps": steps},
            "message": f"{DIRECTION_TO[direction]} {steps}칸 이동합니다."}


def pending_steps(history: list):
    """[R5] 직전 답이 ask 였다면 그때 기억해 둔 칸 수. 아니면 None."""
    for turn in reversed(history):
        if turn["role"] == "assistant":
            data = extract_json(turn["content"]) or {}
            args = data.get("args") if isinstance(data.get("args"), dict) else {}
            if data.get("tool") == "ask" and "steps" in args:
                return to_steps(args["steps"])
            return None
    return None


def apply_rules(call: dict, prompt: str, history: list, gesture_direction: str) -> dict:
    """[R3][R5] LLM 이 고른 도구를, 입력에 실제로 적힌 근거로 확정한다."""
    said = said_direction(prompt)
    steps = said_steps(prompt)
    pending = pending_steps(history)
    if call["tool"] == "move":
        if not has_direction_evidence(prompt, history, gesture_direction):
            return ask_for_direction(steps or call["args"]["steps"])       # [R3] 근거 없는 이동
        return move_with_steps(said or call["args"]["direction"],          # [R3] 적힌 방향이 먼저
                               steps or pending or call["args"]["steps"])  # [R5] 칸 수: 질문 → 기억 → LLM
    if call["tool"] == "ask":
        if pending and said:
            return move_with_steps(said, steps or pending)                  # [R5] 방향만 답해도 이동
        return ask_for_direction(steps or pending or 1)                     # [R3] 칸 수를 기억해 되묻기
    return call


def decide(model, prompt: str, gesture_direction: str, history: list):
    """LLM 이 고르고 → 파서가 모양을 보장하고 → 코드가 규칙을 보장한다."""
    user_content = build_user_content(prompt, gesture_direction)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history,
                {"role": "user", "content": user_content}]
    llm_call = parse_tool_call(ask_llm(model, messages))
    return llm_call, apply_rules(llm_call, prompt, history, gesture_direction), user_content


def fmt(call) -> str:
    a = call["args"]
    if call["tool"] == "move":
        return f"move({a['direction']}, {a['steps']})"
    return f"{call['tool']}({', '.join(f'{k}={v}' for k, v in a.items())})"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--question", help="이 질문 하나만 실행")
    parser.add_argument("--gesture", default="unknown", choices=DIRECTIONS + ("unknown",))
    args = parser.parse_args()
    cases = [(args.question, args.gesture, None, None)] if args.question else CASES

    print("모델 로딩 중...")
    model = load_llm()

    print("\n[1] 채점 ― LLM 이 고른 것 → 규칙 적용 후")
    correct = 0
    for question, gesture, want_tool, want_args in cases:
        llm_call, call, _ = decide(model, question, gesture, [])
        changed = ("  ← 코드가 바꿈"
                   if (call["tool"], call["args"]) != (llm_call["tool"], llm_call["args"]) else "")
        if want_tool is None:
            mark = "  "
        else:
            ok = call["tool"] == want_tool and call["args"] == want_args
            correct += ok
            mark = "O " if ok else "X "
        hand = "" if gesture == "unknown" else f" [손: {DIRECTION_KO[gesture]}]"
        print(f"{mark}{question}{hand}")
        print(f"      LLM {fmt(llm_call):<16} → 최종 {fmt(call)}{changed}")
    if args.question:
        return
    print(f"\n정답 {correct}/{len(cases)}")

    print("\n[2] 되묻기 → 방향을 답하면 이어서 (history)")
    history = []
    for turn, question in enumerate(["저쪽으로 2칸 가", "왼쪽"], 1):
        _, call, user_content = decide(model, question, "unknown", history)
        print(f"  {turn}턴  Q. {question:<12} → {fmt(call)}  \"{call['message'][:24]}\"")
        # 화면이 하는 일 : 이번 턴의 입력과 답을 대화 기록에 붙여 다음 요청에 함께 보낸다
        history += [{"role": "user", "content": user_content},
                    {"role": "assistant", "content": json.dumps(call, ensure_ascii=False)}]
        if call["tool"] != "ask":
            break
    print(f"  대화 기록 {len(history)}개 → 방향은 2턴째 답에서, 칸 수는 1턴째 ask 가 기억한 값에서")


if __name__ == "__main__":
    main()
