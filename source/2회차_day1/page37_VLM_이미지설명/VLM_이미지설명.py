# -*- coding: utf-8 -*-
"""[page 37] 실습 3-1 ― VLM(Qwen2.5-VL-3B, GGUF Q4_K_M) 로드 및 이미지 설명.

강의 포인트
  - VLM은 본체 GGUF + mmproj(비전 프로젝터) 두 파일이 모두 있어야 이미지를 볼 수 있다.
  - 이미지는 base64 data URL 로 만들어 messages 안에 끼워 넣는다.
  - temperature=0.0 으로 고정해야 같은 이미지에 항상 같은 설명이 나와
    모델 간/프롬프트 간 성능 비교가 가능하다.

주의: CPU 추론이라 첫 실행은 수십 초 걸릴 수 있다.

실행:
    python VLM_이미지설명.py
    python VLM_이미지설명.py --image ../samples/sample2.jpg --max-tokens 120
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
VLM_CONTEXT_SIZE = 4096
VLM_DESCRIBE_PROMPT = "이 이미지에 무엇이 보이는지 한국어로 간결하게 설명해줘."


def load_vlm():
    """VLM 모델을 로드한다. mmproj가 빠지면 이미지 입력이 동작하지 않는다."""
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
        n_ctx=VLM_CONTEXT_SIZE,
        n_threads=os.cpu_count(),
        verbose=False,
    )


def to_data_url(image: Image.Image) -> str:
    """PIL 이미지를 base64 data URL 로 변환한다."""
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "data:image/jpeg;base64," + encoded


def describe(model, image: Image.Image, prompt: str, max_tokens: int) -> str:
    response = model.create_chat_completion(
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": to_data_url(image)}},
                {"type": "text", "text": prompt},
            ],
        }],
        max_tokens=max_tokens,
        temperature=0.0,   # 재현 가능한 출력을 위해 고정
    )
    content = response["choices"][0]["message"]["content"]
    return content.strip() if content else ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default=str(DEFAULT_IMAGE))
    parser.add_argument("--prompt", default=VLM_DESCRIBE_PROMPT)
    parser.add_argument("--max-tokens", type=int, default=200)
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"이미지를 찾을 수 없습니다: {image_path}")
    image = Image.open(image_path).convert("RGB")

    print(f"입력 이미지 : {image_path.name} ({image.width}x{image.height})")
    print("모델 로딩 중... (CPU 추론이라 시간이 걸립니다)")
    t0 = time.perf_counter()
    model = load_vlm()
    print(f"모델 로딩   : {time.perf_counter() - t0:.1f}s")

    print(f"\n프롬프트    : {args.prompt}")
    t0 = time.perf_counter()
    description = describe(model, image, args.prompt, args.max_tokens)
    elapsed = time.perf_counter() - t0

    print(f"\n[VLM 설명]\n{description}")
    print(f"\n추론 시간   : {elapsed:.1f}s")
    print("\n이 시간이 전체 응답 시간을 지배합니다.")
    print("→ 2일차에 YOLO와 VLM을 '병렬로' 실행하는 이유입니다.")


if __name__ == "__main__":
    main()
