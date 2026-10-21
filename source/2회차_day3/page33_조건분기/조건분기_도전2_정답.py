# -*- coding: utf-8 -*-
"""[도전 문제 2 ― 정답] '위 2칸 가' 도 move 가 되도록 방향어 검사(DIRECTION_WORD_RE)를 고친 것.

    ① '위 2칸 가'     → move(up, 2)
    ② '버스 위치로 가' → 여전히 ask   ('위치' 에도 '위' 가 들어 있다)
    ③ 기존 8문항은 8/8 그대로
    (참고) '위에 뭐 있어?' 는 describe

실습 3-1 의 조건분기.py 를 그대로 불러 쓰고, 방향어 정규식만 바꿔 끼운다.
문제 파일(조건분기_도전2.py)과 DIRECTION_WORD_RE 만 다르다.
'위쪽|위로' 는 '위' 한 글자를 놓치고, '위' 만 쓰면 '위치' 도 방향이 된다 ―
방향어 목록에 '위 '(위 + 공백)와 문장 끝의 '위' 를 더한다.

실행:
    python 조건분기_도전2_정답.py
"""
import re
import sys
from pathlib import Path

# 실습 3-1 폴더(../page31_조건분기)의 원본을 불러 쓴다
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "page31_조건분기"))
import 조건분기 as base  # noqa: E402

# 방향어 목록 ― 위 : 위쪽 · 위로 · '위 '(위 + 공백) · 문장 끝의 위($),  아래 : 아래쪽 · 아래로 포함
# ('위치', '위에' 는 방향이 아니다)
DIRECTION_WORD_RE = re.compile(
    r"오른쪽|오른편|우측|왼쪽|왼편|좌측|아래|밑|위쪽|위로|위 |위$|\b(?:up|down|left|right)\b", re.I)


# ---------------------------------------------------------------------------
# 채점 (고치지 않는다)
# ---------------------------------------------------------------------------
CHALLENGE_CASES = [
    ("위 2칸 가", "unknown", "move", {"direction": "up", "steps": 2}),
    ("버스 위치로 가", "unknown", "ask", {"steps": 1}),
    ("위에 뭐 있어?", "unknown", "describe", {}),
]


def grade(model, cases) -> int:
    correct = 0
    for question, gesture, want_tool, want_args in cases:
        llm_call, call, _ = base.decide(model, question, gesture, [])
        ok = call["tool"] == want_tool and call["args"] == want_args
        correct += ok
        hand = "" if gesture == "unknown" else f" [손: {base.DIRECTION_KO[gesture]}]"
        print(f"  {'O' if ok else 'X'}  {question}{hand}")
        print(f"       LLM {base.fmt(llm_call):<16} → 최종 {base.fmt(call)}")
    return correct


def main() -> None:
    base._DIRECTION_WORD_RE = DIRECTION_WORD_RE      # 조건분기.py 의 방향어 검사를 바꿔 끼운다
    print("모델 로딩 중...")
    model = base.load_llm()

    print("\n[도전 2] 세 문항")
    passed = grade(model, CHALLENGE_CASES)
    print(f"  {passed}/{len(CHALLENGE_CASES)}")

    print("\n[기존 8문항]")
    passed = grade(model, base.CASES)
    print(f"  {passed}/{len(base.CASES)}")


if __name__ == "__main__":
    main()
