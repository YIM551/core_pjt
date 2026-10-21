# -*- coding: utf-8 -*-
"""[page 18] 실습 1-2 ― VLM 설명을 'LLM 입력 규격'에 맞춘다.

1일차 도전 문제 2 의 답을 규격으로 고정한다.
  - 한국어 / 한 문장 / 40자 이내      → 프롬프트로 건다
  - 장애물 유무                        → 문장 끝 '장애물 있음/없음' 형식 + 형식 예시
  - 길이 상한                          → max_tokens 로 한 번 더 건다
  - 같은 이미지 → 같은 문장            → temperature=0.0
  - 입력은 긴 변 448px 로 줄여서 넣는다 → 1회 약 10초 (이유는 Part 3 'VLM 을 줄이는 레버')

모델이 규격을 어길 때를 대비해, 출력 뒤에서 다듬고(normalize) 검사한다(check).
길이를 넘겼다고 코드로 자르면 끝의 '장애물 없음' 이 잘린다 ― 자르지 말고 검사만 한다.

실행:
    python VLM_출력규격.py
    python VLM_출력규격.py --image ../samples/victory.jpg --repeat 1
"""
import argparse
import base64
import io
import os
import re
import textwrap
import time
from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day2 (공용 자료)
PROJECT_ROOT = DAY_DIR.parents[1]
DEFAULT_IMAGE = DAY_DIR / "samples" / "sample.jpg"

VLM_GGUF_PATH = PROJECT_ROOT / "models" / "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
VLM_MMPROJ_PATH = PROJECT_ROOT / "models" / "mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf"

# 규격을 '문장으로' 적는다. 조건 하나당 한 구절.
SPEC_PROMPT = (
    "이 이미지를 한국어 한 문장으로 설명해줘. 40자 이내로 쓰고, 문장 끝에 "
    "'장애물 있음' 또는 '장애물 없음' 을 붙여줘. "
    "형식 예: 복도에 의자 두 개가 놓여 있다, 장애물 있음."
)
SPEC_MAX_CHARS = 40
SPEC_MAX_TOKENS = 60
MAX_SIDE = 448                    # 대시보드 서버(Part 3)와 같은 입력 크기


def load_vlm():
    for path, label in ((VLM_GGUF_PATH, "VLM 본체"), (VLM_MMPROJ_PATH, "mmproj")):
        if not path.exists():
            raise SystemExit(f"{label} 파일이 없습니다: {path}")

    from llama_cpp import Llama
    from llama_cpp.llama_chat_format import Qwen25VLChatHandler

    chat_handler = Qwen25VLChatHandler(
        clip_model_path=str(VLM_MMPROJ_PATH), verbose=False
    )
    return Llama(
        model_path=str(VLM_GGUF_PATH),
        chat_handler=chat_handler,
        n_ctx=4096,
        n_threads=os.cpu_count(),
        verbose=False,
    )


def to_data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def describe(model, image: Image.Image) -> str:
    response = model.create_chat_completion(
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": to_data_url(image)}},
                {"type": "text", "text": SPEC_PROMPT},
            ],
        }],
        max_tokens=SPEC_MAX_TOKENS,   # 길이는 프롬프트 + max_tokens 양쪽에서 건다
        temperature=0.0,              # 재현성
    )
    content = response["choices"][0]["message"]["content"]
    return content.strip() if content else ""


def shrink(image: Image.Image) -> Image.Image:
    if max(image.size) <= MAX_SIDE:
        return image
    scale = MAX_SIDE / max(image.size)
    return image.resize((round(image.width * scale), round(image.height * scale)))


def normalize(text: str) -> str:
    """규격 위반을 뒤에서 한 번 더 다듬는다.

    앞에 붙는 잡문자(':' '.')와 줄바꿈을 없애고, 첫 문장만 남긴다.
    '장애물 있음/없음' 을 두 번째 문장으로 따로 쓰면 첫 문장 끝으로 옮긴다.
    모델을 믿지 말고 형식은 코드로 보장한다.
    """
    text = " ".join(text.split()).lstrip(":. ")
    first = re.split(r"(?<=[.!?。])\s", text, maxsplit=1)[0].strip()
    obstacle = re.search(r"장애물 (있음|없음)", text)
    if obstacle and "장애물" not in first:
        first = f"{first.rstrip(' .')}, {obstacle.group(0)}."
    return first


def check(text: str) -> list:
    hangul = len(re.findall(r"[가-힣]", text))
    letters = len(re.findall(r"[A-Za-z가-힣]", text)) or 1
    cjk = re.search(r"[぀-ヿ一-鿿]", text)       # 한자 · 가나가 섞이면 NG
    return [
        ("한국어", hangul / letters >= 0.8 and not cjk),
        (f"{SPEC_MAX_CHARS}자 이내", len(text) <= SPEC_MAX_CHARS),
        ("장애물 표기", bool(re.search(r"장애물 (있음|없음)\.?$", text))),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default=str(DEFAULT_IMAGE))
    parser.add_argument("--repeat", type=int, default=2,
                        help="같은 이미지로 몇 번 돌려 재현성을 볼지")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"이미지를 찾을 수 없습니다: {image_path}")
    image = shrink(Image.open(image_path).convert("RGB"))

    print(f"입력 이미지 : {image_path.name} → {image.width}x{image.height}")
    print("프롬프트    : " + textwrap.fill(SPEC_PROMPT, 40, subsequent_indent=" " * 14))
    print(f"max_tokens  : {SPEC_MAX_TOKENS} / temperature : 0.0\n")
    model = load_vlm()

    outputs = []
    for i in range(1, args.repeat + 1):
        t0 = time.perf_counter()
        raw = describe(model, image)
        elapsed = time.perf_counter() - t0
        text = normalize(raw)
        outputs.append(text)
        print(f"[{i}회차] {elapsed:.1f}s")
        print(f"  원문     : {raw}")
        print(f"  규격화   : {text}  ({len(text)}자)")
        print("  검사     : " + " / ".join(
            f"{name} {'OK' if ok else 'NG'}" for name, ok in check(text)))

    if len(outputs) > 1:
        same = len(set(outputs)) == 1
        print(f"\n재현성 : {'같은 문장' if same else '다른 문장'} ({len(outputs)}회)")

    print("\n이 한 문장이 [VLM 장면 설명] 블록으로 LLM 에 들어갑니다.")


if __name__ == "__main__":
    main()
