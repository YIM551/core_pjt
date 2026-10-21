# -*- coding: utf-8 -*-
"""[page 56] 실습 4-1 ― 인식 Text 세 줄 + 사용자 질문 → LLM 이 상황을 이해해 답한다.

LLM(Qwen3-4B)은 이미지를 보지 않는다. 인식 모델이 만든 Text 만 읽는다.
그래서 입력 템플릿이 곧 LLM 이 보는 '세상' 이다.

  - 입력은 출처별 블록으로 나눈다   [YOLO 객체 인식] / [VLM 장면 설명] / [손 제스처]
  - 출처별 신뢰 규칙을 시스템 프롬프트에 적는다  (개수는 YOLO, 맥락은 VLM, 방향은 제스처)
  - Qwen3 의 사고(thinking) 모드는 끈다  (/no_think + <think> 블록 제거)

입력은 이 폴더의 perception.json (예시 인식 결과) 을 쓴다. 없으면 내장 예시를 쓴다.

실행:
    python LLM_통합답변.py
    python LLM_통합답변.py --question "사람이 몇 명이야?"
    python LLM_통합답변.py --yolo "person 4개, bus 1개" --vlm "두 사람이 버스 앞에 서 있다."
    python LLM_통합답변.py --rule "블록끼리 충돌하면 ..."     # 규칙 한 줄 추가
    (도전 문제 4 는 ../page67_LLM_통합답변 폴더에서 한다)
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
PERCEPTION_JSON = BASE_DIR / "perception.json"

# perception.json 이 없을 때 쓰는 예시 (pointing_up.jpg 의 인식 결과 형식)
FALLBACK = {                    # perception.json 과 같은 내용 (pointing_up.jpg 인식 결과)
    "yolo": "person 1개, tie 1개",
    "vlm": "여성이 손가락으로 1을 가리키고 있다, 장애물 없음.",
    "gesture": "Pointing_Up, 가리키는 방향: 위",
}

SYSTEM_PROMPT = (
    "너는 카메라 장면을 설명하는 로봇 어시스턴트다. 이미지를 직접 볼 수 없고, "
    "인식 모델이 만든 Text 블록만 근거로 답한다.\n"
    "규칙:\n"
    "1. 물체의 종류와 개수는 [YOLO 객체 인식] 을 따른다.\n"
    "2. 장면의 분위기·관계·상황은 [VLM 장면 설명] 을 참고한다.\n"
    "3. 사용자가 가리키는 방향은 [손 제스처] 를 따른다.\n"
    "4. 블록에 없는 내용은 지어내지 말고 '알 수 없다' 고 말한다.\n"
    "5. 한국어로 두세 문장으로 답한다."
)
DEFAULT_QUESTION = "지금 앞에 무엇이 있고, 내가 어느 쪽을 가리키고 있어?"

_THINK_RE = re.compile(r"<think>.*?(?:</think>|\Z)", re.DOTALL)


def load_llm():
    if not LLM_GGUF_PATH.exists():
        raise SystemExit(f"LLM 파일이 없습니다: {LLM_GGUF_PATH}")
    from llama_cpp import Llama

    # VLM 과 같은 llama_cpp 로 로드한다. 채팅 템플릿은 GGUF 안에 들어 있다.
    return Llama(model_path=str(LLM_GGUF_PATH), n_ctx=4096,
                 n_threads=os.cpu_count(), verbose=False)


def build_user_content(perception: dict, question: str) -> str:
    """출처별 블록 + 질문. 블록 이름은 시스템 프롬프트의 규칙과 글자까지 같아야 한다."""
    return (
        f"[YOLO 객체 인식] {perception['yolo']}\n"
        f"[VLM 장면 설명] {perception['vlm']}\n"
        f"[손 제스처] {perception['gesture']}\n\n"
        f"[사용자 질문] {question}"
    )


def ask(model, user_content: str, system_prompt: str = SYSTEM_PROMPT,
        max_tokens: int = 256):
    """Qwen3 사고 모드를 끄고(/no_think) 답을 받는다."""
    response = model.create_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content + " /no_think"},
        ],
        max_tokens=max_tokens,
        temperature=0.0,
    )
    raw = response["choices"][0]["message"]["content"] or ""
    # 빈 <think></think> 가 붙어 나오거나, 잘린 사고 블록이 남을 수 있다
    return _THINK_RE.sub("", raw).strip(), response["usage"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--yolo")
    parser.add_argument("--vlm")
    parser.add_argument("--gesture")
    parser.add_argument("--rule", help="시스템 프롬프트 끝에 규칙 한 줄 추가")
    args = parser.parse_args()

    if PERCEPTION_JSON.exists():
        perception = json.loads(PERCEPTION_JSON.read_text(encoding="utf-8"))
        source = PERCEPTION_JSON.name
    else:
        perception, source = dict(FALLBACK), "내장 예시"
    for key in ("yolo", "vlm", "gesture"):          # 명령행 값이 있으면 덮어쓴다
        if getattr(args, key):
            perception[key] = getattr(args, key)
            source = "명령행 지정"

    user_content = build_user_content(perception, args.question)
    system_prompt = SYSTEM_PROMPT + (f"\n6. {args.rule}" if args.rule else "")
    print(f"입력 출처 : {source}\n")
    if args.rule:
        print(textwrap.fill(f"추가 규칙 : 6. {args.rule}", 48,
                            subsequent_indent=" " * 15) + "\n")
    print("[LLM 입력]")
    print(user_content)

    print("\n모델 로딩 중...")
    t0 = time.perf_counter()
    model = load_llm()
    print(f"모델 로딩 : {time.perf_counter() - t0:.1f}s")

    t0 = time.perf_counter()
    answer, usage = ask(model, user_content, system_prompt)
    elapsed = time.perf_counter() - t0

    print("\n[LLM 답변]\n" + textwrap.fill(answer, 48))
    print(f"\n추론 시간 : {elapsed:.1f}s  (입력 {usage['prompt_tokens']} 토큰 / "
          f"출력 {usage['completion_tokens']} 토큰)")


if __name__ == "__main__":
    main()
