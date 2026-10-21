# -*- coding: utf-8 -*-
"""[page 61] 실습 4-2 ― LLM 답변을 JSON 으로 받고, 깨진 출력도 안전하게 파싱한다.

3일차에는 LLM 의 판단으로 도구(tool)를 호출한다. 그러려면 답변을
'사람이 읽는 문장' 이 아니라 '코드가 읽는 구조' 로 받아야 한다.

소형 LLM(4B)은 JSON 지시를 자주 어긴다. 실제 프로젝트에서 겪은 실패 유형:
  - JSON 앞뒤에 설명 문장이나 ```json 코드펜스가 붙는다
  - true/false 대신 문자열 "false" 를 쓴다   → bool("false") 는 True 다!
  - <think> 블록이 닫히지 않은 채 잘린다
  - 정해진 값(up/down/...) 밖의 값을 쓴다
→ 모델을 믿지 말고, 파서가 형식을 보장한다.

실행:
    python LLM_JSON파싱.py              # [A] LLM 실제 호출 + [B] 파서 자체 점검
    python LLM_JSON파싱.py --skip-llm   # [B] 만 (LLM 없이 몇 초)
"""
import argparse
import json
import os
import re
import textwrap
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day2 (공용 자료)
PROJECT_ROOT = DAY_DIR.parents[1]
LLM_GGUF_PATH = PROJECT_ROOT / "models" / "Qwen3-4B-Q4_K_M.gguf"
PERCEPTION_JSON = DAY_DIR / "page56_LLM_통합답변" / "perception.json"   # 실습 4-1 에서 처음 쓴 입력

FALLBACK = {                    # ../page56_LLM_통합답변/perception.json 과 같은 내용 (pointing_up.jpg 인식 결과)
    "yolo": "person 1개, tie 1개",
    "vlm": "여성이 손가락으로 1을 가리키고 있다, 장애물 없음.",
    "gesture": "Pointing_Up, 가리키는 방향: 위",
}
QUESTION = "지금 상황을 정리해줘."

SYSTEM_PROMPT = (
    "너는 카메라 장면을 설명하는 로봇 어시스턴트다. 인식 모델이 만든 Text 블록만 근거로 한다. "
    "개수는 [YOLO 객체 인식], 상황은 [VLM 장면 설명], 방향은 [손 제스처] 를 따른다.\n"
    "반드시 아래 JSON 한 개로만 답하고, 다른 글은 쓰지 마라.\n"
    '{"objects": "<물체와 개수>", "obstacle": <true 또는 false>, '
    '"direction": "<up|down|left|right|none>", "summary": "<한 문장 상황 요약>"}'
)

DIRECTIONS = {"up", "down", "left", "right", "none"}
DIRECTION_ALIASES = {"위": "up", "아래": "down", "왼쪽": "left", "오른쪽": "right"}
_THINK_RE = re.compile(r"<think>.*?(?:</think>|\Z)", re.DOTALL)


# ---------------------------------------------------------------------------
# 방어 파싱 ― 모델이 어떤 걸 내놓든 항상 같은 모양의 dict 를 돌려준다
# ---------------------------------------------------------------------------
def extract_json(text: str):
    """첫 '{' ~ 마지막 '}' 만 잘라 파싱한다. 앞뒤 잡텍스트·코드펜스를 무시한다."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def to_bool(value) -> bool:
    """문자열 "false" 도 False 로. bool("false") 는 True 라서 그대로 쓰면 안 된다."""
    if isinstance(value, str):
        return value.strip().lower() not in ("", "false", "0", "no", "none", "null")
    return bool(value)


def to_direction(value) -> str:
    value = str(value).strip().lower()
    value = DIRECTION_ALIASES.get(value, value)
    return value if value in DIRECTIONS else "none"


def parse_llm_output(raw: str) -> dict:
    text = _THINK_RE.sub("", raw).strip()           # 1) 사고 블록 제거
    data = extract_json(text)                        # 2) JSON 구간만 추출
    if data is None:                                 # 3) 실패해도 형식은 유지
        return {"ok": False, "objects": "", "obstacle": False,
                "direction": "none", "summary": text or "답변 없음"}
    return {                                         # 4) 필드별로 타입 보정
        "ok": True,
        "objects": str(data.get("objects", "")).strip(),
        "obstacle": to_bool(data.get("obstacle", False)),
        "direction": to_direction(data.get("direction", "none")),
        "summary": str(data.get("summary", "")).strip(),
    }


# 실제로 겪은 깨진 출력들 ― 파서가 전부 같은 모양으로 받아내야 한다
BROKEN_SAMPLES = [
    ("정상", '{"objects": "person 1개", "obstacle": false, "direction": "up", '
             '"summary": "한 사람이 위를 가리킨다."}'),
    ("코드펜스", '```json\n{"objects": "person 1개", "obstacle": false, '
                '"direction": "up", "summary": "위를 가리킨다."}\n```'),
    ("앞뒤 잡글", '네, 정리하면 다음과 같습니다. {"objects": "bus 1개", "obstacle": true, '
                 '"direction": "none", "summary": "버스가 길을 막고 있다."} 참고하세요.'),
    ("문자열 bool", '{"objects": "person 4개", "obstacle": "false", '
                   '"direction": "left", "summary": "왼쪽을 가리킨다."}'),
    ("한글 방향", '{"objects": "없음", "obstacle": false, "direction": "오른쪽", '
                 '"summary": "오른쪽을 가리킨다."}'),
    ("잘린 think", '<think>사용자가 위를 가리키고 있으니 먼저 방향을 정리하면'),
]


def self_test() -> None:
    print("[B] 파서 자체 점검 ― 깨진 출력 6종")
    print(f"  {'유형':<10}{'ok':<7}{'obstacle':<10}{'direction':<10}summary")
    for label, raw in BROKEN_SAMPLES:
        r = parse_llm_output(raw)
        print(f"  {label:<10}{str(r['ok']):<7}{str(r['obstacle']):<10}"
              f"{r['direction']:<10}{r['summary'][:24]}")
    naive = bool(json.loads(BROKEN_SAMPLES[3][1])["obstacle"])
    print(f"\n  참고: 파서 없이 bool(\"false\") 로 읽으면 obstacle = {naive}  ← 정반대가 된다")


def run_llm() -> None:
    from llama_cpp import Llama

    if not LLM_GGUF_PATH.exists():
        raise SystemExit(f"LLM 파일이 없습니다: {LLM_GGUF_PATH}")
    perception = (json.loads(PERCEPTION_JSON.read_text(encoding="utf-8"))
                  if PERCEPTION_JSON.exists() else FALLBACK)
    user_content = (f"[YOLO 객체 인식] {perception['yolo']}\n"
                    f"[VLM 장면 설명] {perception['vlm']}\n"
                    f"[손 제스처] {perception['gesture']}\n\n"
                    f"[사용자 질문] {QUESTION}")

    model = Llama(model_path=str(LLM_GGUF_PATH), n_ctx=4096,
                  n_threads=os.cpu_count(), verbose=False)
    t0 = time.perf_counter()
    response = model.create_chat_completion(
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": user_content + " /no_think"}],
        max_tokens=200,
        temperature=0.0,
    )
    elapsed = time.perf_counter() - t0
    raw = response["choices"][0]["message"]["content"] or ""

    print("[A] LLM 실제 호출")
    print(f"  입력 :\n    " + user_content.replace("\n", "\n    "))
    print(f"\n  원문 ({elapsed:.1f}s) :")
    for line in raw.strip().splitlines():            # 화면 폭에 맞춰 접어서 보여준다
        print(textwrap.fill(line, 56, initial_indent="    ", subsequent_indent="    ")
              if line.strip() else "")
    print("\n  파싱 결과 :")
    for key, value in parse_llm_output(raw).items():
        print(f"    {key:<10}: {value}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-llm", action="store_true")
    args = parser.parse_args()

    if not args.skip_llm:
        run_llm()
    self_test()
    print("\n형식은 모델이 아니라 파서가 보장한다 → 3일차 도구 호출의 입력이 된다.")


if __name__ == "__main__":
    main()
