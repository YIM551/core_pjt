# -*- coding: utf-8 -*-
"""[도전 문제 4] 규칙 한 줄(RULE_6)을 추가해, 출처끼리 다를 때 그 사실까지 알리게 하시오.

지금은 YOLO 는 4명, VLM 은 '남성' 한 명이라고 하는데 답에는 VLM 얘기가 없다.

    ① 개수는 여전히 YOLO 를 따른다
    ② VLM 이 어떻게 말했는지 덧붙인다
    ③ VLM 의 말을 지어내면 안 된다 ― 원문에 없는 말을 VLM 이 했다고 하면 실패

고칠 곳은 RULE_6 한 줄이다. 입력과 질문은 고정되어 있다.
①② 는 자동으로 확인하고, ③ 은 답을 직접 읽고 판단한다.
같은 답이 나오는지 두 번 실행해 본다 (temperature 0 이어도 흔들릴 수 있다).
정답 : LLM_통합답변_도전4_정답.py

실행:
    python LLM_통합답변_도전4.py
"""
import os
import re
import textwrap
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day2 (공용 자료)
PROJECT_ROOT = DAY_DIR.parents[1]
LLM_GGUF_PATH = PROJECT_ROOT / "models" / "Qwen3-4B-Q4_K_M.gguf"

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
RULE_6 = ""     # TODO ― 규칙 한 줄

# 출처끼리 다른 입력 (고정)
PERCEPTION = {
    "yolo": "person 4개, bus 1개",
    "vlm": "버스 앞에 남성이 서 있다, 장애물 없음.",
    "gesture": "손 없음",
}
QUESTION = "사람이 몇 명이야?"

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
    system_prompt = SYSTEM_PROMPT + (f"\n6. {RULE_6}" if RULE_6 else "")
    user_content = build_user_content(PERCEPTION, QUESTION)
    print(textwrap.fill(f"추가 규칙 : 6. {RULE_6 or '(없음)'}", 48,
                        subsequent_indent=" " * 15))
    print("\n[LLM 입력]\n" + user_content)

    model = load_llm()
    t0 = time.perf_counter()
    answer, _ = ask(model, user_content, system_prompt)
    print(f"\n[LLM 답변]  ({time.perf_counter() - t0:.1f}s)\n" + textwrap.fill(answer, 48))

    vlm_quote = PERCEPTION["vlm"].split(",")[0]
    print("\n[자동 확인]")
    print(f"  {'O' if '4명' in answer else 'X'}  ① 개수는 YOLO (4명)")
    print(f"  {'O' if vlm_quote in answer else 'X'}  ② VLM 원문 인용 ('{vlm_quote}')")
    print("  ?  ③ 지어낸 말이 없는지는 직접 읽고 판단한다")


if __name__ == "__main__":
    main()
