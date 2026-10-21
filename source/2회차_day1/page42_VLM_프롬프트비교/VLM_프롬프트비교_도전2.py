# -*- coding: utf-8 -*-
"""[도전 문제 2] 출력을 통제하는 다섯 번째 프롬프트를 쓰시오.

출력이 만족해야 할 조건
    ① 한국어로만 답한다
    ② 한 문장, 40자 이내
    ③ 장애물이 있는지/없는지가 반드시 포함된다
    ④ 같은 이미지에 두 번 돌리면 같은 문장이 나온다

실습 3-2 의 VLM_프롬프트비교.py 에서 모델 로딩만 빌려 쓴다.
고칠 곳은 PROMPT_5 · MAX_TOKENS · ask() 세 군데다. 나머지는 채점용이다.
같은 프롬프트를 두 번 돌려 ① ~ ④ 를 자동으로 확인한다 (CPU 1회 약 90초).
정답 : VLM_프롬프트비교_도전2_정답.py

실행:
    python VLM_프롬프트비교_도전2.py
"""
import re
import sys
import time
from pathlib import Path

from PIL import Image

# 실습 3-2 폴더(../page39_VLM_프롬프트비교)의 원본을 불러 쓴다
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "page39_VLM_프롬프트비교"))
import VLM_프롬프트비교 as base  # noqa: E402

PROMPT_5 = ""        # TODO ― 다섯 번째 프롬프트
MAX_TOKENS = 150     # TODO ― 길이 상한 (지금은 실습 3-2 의 기본값)


def ask(model, data_url: str, prompt: str, max_tokens: int) -> str:
    # TODO ― ④ 는 프롬프트가 아니라 파라미터로 잡는다
    response = model.create_chat_completion(
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": prompt},
            ],
        }],
        max_tokens=max_tokens,
    )
    content = response["choices"][0]["message"]["content"]
    return (content or "").strip()


# ---------------------------------------------------------------------------
# 채점 (고치지 않는다)
# ---------------------------------------------------------------------------
MAX_CHARS = 40


def check(text: str) -> list:
    hangul = len(re.findall(r"[가-힣]", text))
    letters = len(re.findall(r"[A-Za-z가-힣]", text)) or 1
    cjk = re.search(r"[぀-ヿ一-鿿]", text)       # 한자 · 가나가 섞이면 X
    body = text.strip().lstrip(":. ")                  # 앞에 붙는 잡문자는 문장으로 세지 않는다
    sentences = [s for s in re.split(r"(?<=[.!?。])\s+", body) if s]
    return [
        ("① 한국어로만", hangul / letters >= 0.8 and not cjk),
        (f"② 한 문장, {MAX_CHARS}자 이내", len(sentences) == 1 and len(text) <= MAX_CHARS),
        ("③ 장애물 있음/없음 포함", bool(re.search(r"장애물\s*(있음|없음)", text))),
    ]


def main() -> None:
    if not PROMPT_5:
        raise SystemExit("PROMPT_5 에 다섯 번째 프롬프트를 먼저 적으시오")

    image = Image.open(base.DEFAULT_IMAGE).convert("RGB")
    model = base.load_vlm()
    data_url = base.to_data_url(image)
    print(f"입력 이미지 : {base.DEFAULT_IMAGE.name} / max_tokens {MAX_TOKENS}")
    print(f"프롬프트    : {PROMPT_5}\n")

    answers = []
    for run in (1, 2):
        t0 = time.perf_counter()
        answer = ask(model, data_url, PROMPT_5, MAX_TOKENS)
        answers.append(answer)
        print(f"[{run}회차] {answer}\n    ({time.perf_counter() - t0:.1f}s, {len(answer)}자)")

    print("\n[자동 확인] 1회차 기준")
    for name, ok in check(answers[0]):
        print(f"  {'O' if ok else 'X'}  {name}")
    print(f"  {'O' if answers[0] == answers[1] else 'X'}  ④ 두 번 같은 문장")


if __name__ == "__main__":
    main()
