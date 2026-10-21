# -*- coding: utf-8 -*-
"""[page 39] 실습 3-2 ― 프롬프트에 따른 VLM 출력 차이 비교.

같은 이미지에 프롬프트만 바꿔 넣고, 출력 길이·내용·소요 시간이 어떻게
달라지는지 직접 확인한다.

관찰 포인트
  - "설명해줘"  → 장황한 문단. 길이 제어가 안 되어 LLM 입력으로 부적합.
  - "간결하게"  → 2~3문장. 이 프로젝트가 채택한 형태.
  - "개수와 함께 나열" → 개수가 자주 틀린다. 개수는 YOLO가 담당해야 할 영역.
  - "있는지만 답해줘" → 판단은 LLM에 맡기고 VLM은 서술만 하게 한다.

주의: CPU 추론이라 프롬프트 1개당 1~2분 걸린다.
      시간이 없으면 --limit 2 --max-tokens 60 으로 줄여서 실행한다.

실행:
    python VLM_프롬프트비교.py --limit 2 --max-tokens 60
    python VLM_프롬프트비교.py                 # 4종 전체 비교
    python VLM_프롬프트비교.py --only 3               # 3번째 프롬프트만
    (도전 문제 2 는 ../page42_VLM_프롬프트비교 폴더에서 한다)
"""
import argparse
import base64
import io
import os
import time
from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day1 (공용 자료)
PROJECT_ROOT = DAY_DIR.parents[1]
DEFAULT_IMAGE = DAY_DIR / "samples" / "sample.jpg"

VLM_GGUF_PATH = PROJECT_ROOT / "models" / "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
VLM_MMPROJ_PATH = PROJECT_ROOT / "models" / "mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf"

PROMPTS = [
    ("자유 설명", "이 이미지를 설명해줘."),
    ("간결 설명", "이 이미지에 무엇이 보이는지 한국어로 간결하게 설명해줘."),
    ("개수 나열", "보이는 물체를 개수와 함께 나열해줘."),
    ("판단 요구", "장애물이 있는지만 한국어로 짧게 답해줘."),
]


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


def ask(model, data_url: str, prompt: str, max_tokens: int) -> str:
    response = model.create_chat_completion(
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": prompt},
            ],
        }],
        max_tokens=max_tokens,
        temperature=0.0,
    )
    content = response["choices"][0]["message"]["content"]
    return (content or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default=str(DEFAULT_IMAGE))
    parser.add_argument("--max-tokens", type=int, default=150)
    parser.add_argument("--limit", type=int, default=len(PROMPTS),
                        help="앞에서부터 N개 프롬프트만 실행")
    parser.add_argument("--only", type=int, help="N번째 프롬프트 하나만 실행 (1부터)")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"이미지를 찾을 수 없습니다: {image_path}")
    image = Image.open(image_path).convert("RGB")

    if args.only:
        if not 1 <= args.only <= len(PROMPTS):
            raise SystemExit(f"--only 는 1 ~ {len(PROMPTS)} 사이여야 합니다")
        targets = [PROMPTS[args.only - 1]]
    else:
        targets = PROMPTS[:max(1, args.limit)]
    print(f"입력 이미지 : {image_path.name}")
    print(f"비교할 프롬프트 : {len(targets)}개 (CPU 추론이라 시간이 걸립니다)\n")

    model = load_vlm()
    data_url = to_data_url(image)

    results = []
    for label, prompt in targets:
        print(f"--- [{label}] {prompt}")
        t0 = time.perf_counter()
        answer = ask(model, data_url, prompt, args.max_tokens)
        elapsed = time.perf_counter() - t0
        results.append((label, answer, elapsed))
        print(f"{answer}\n    ({elapsed:.1f}s, {len(answer)}자)\n")

    print("=" * 70)
    print(f"{'프롬프트':<12} {'글자수':>6} {'소요(s)':>8}")
    print("-" * 70)
    for label, answer, elapsed in results:
        print(f"{label:<12} {len(answer):>6} {elapsed:>8.1f}")

    print("\n정리: VLM에게는 '서술'만 시키고, '판단'과 '집계'는 다른 모듈에 맡긴다.")
    print("      프롬프트와 max_tokens를 고정해야 2일차 LLM 통합 결과가 재현된다.")


if __name__ == "__main__":
    main()
