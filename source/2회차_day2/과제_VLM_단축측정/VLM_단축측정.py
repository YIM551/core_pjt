# -*- coding: utf-8 -*-
"""[기능 구현 ③] VLM 응답 시간을 줄이는 레버를 하나씩 측정한다 (강의자료 Part 3 'VLM 을 줄이는 레버').

1일차 결론: 전체 시간의 99.9% 가 VLM 한 곳 → 병렬화보다 VLM 단축이 먼저.
CPU 에서 당길 수 있는 레버 두 개를 한 번에 하나씩 바꿔 가며 잰다.

  A  기준        : 원본 이미지 + 1일차 프롬프트 + max_tokens 200
  B  출력 줄이기 : 규격 프롬프트(한 문장 40자) + max_tokens 60
  C  입력 줄이기 : B + 이미지 긴 변을 448px 로 축소

VLM 은 이미지를 수백~수천 개의 토큰으로 바꿔 읽는다. 이미지를 줄이면
'읽는 시간', max_tokens 를 줄이면 '쓰는 시간'이 준다.

실행:
    python VLM_단축측정.py
    python VLM_단축측정.py --only C        # 한 설정만
결과는 vlm_speed.csv 로 저장된다.
"""
import argparse
import base64
import csv
import io
import os
import textwrap
import time
from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day2 (공용 자료)
PROJECT_ROOT = DAY_DIR.parents[1]
DEFAULT_IMAGE = DAY_DIR / "samples" / "sample.jpg"
CSV_PATH = BASE_DIR / "vlm_speed.csv"

VLM_GGUF_PATH = PROJECT_ROOT / "models" / "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
VLM_MMPROJ_PATH = PROJECT_ROOT / "models" / "mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf"

DAY1_PROMPT = "이 이미지에 무엇이 보이는지 한국어로 간결하게 설명해줘."
SPEC_PROMPT = (
    "이 이미지를 한국어 한 문장으로 설명해줘. 40자 이내로 쓰고, 문장 끝에 "
    "'장애물 있음' 또는 '장애물 없음' 을 붙여줘. "
    "형식 예: 복도에 의자 두 개가 놓여 있다, 장애물 있음."
)

# (이름, 설명, 프롬프트, max_tokens, 이미지 긴 변 상한 ― None 이면 원본)
CONFIGS = [
    ("A", "기준", DAY1_PROMPT, 200, None),
    ("B", "출력 줄이기", SPEC_PROMPT, 60, None),
    ("C", "입력 줄이기", SPEC_PROMPT, 60, 448),
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


def shrink(image: Image.Image, max_side):
    """긴 변이 max_side 를 넘으면 비율을 유지한 채 줄인다."""
    if max_side is None or max(image.size) <= max_side:
        return image
    scale = max_side / max(image.size)
    return image.resize((round(image.width * scale), round(image.height * scale)))


def to_data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def run(model, image: Image.Image, prompt: str, max_tokens: int):
    t0 = time.perf_counter()
    response = model.create_chat_completion(
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": to_data_url(image)}},
                {"type": "text", "text": prompt},
            ],
        }],
        max_tokens=max_tokens,
        temperature=0.0,
    )
    elapsed = time.perf_counter() - t0
    out_tok = response.get("usage", {}).get("completion_tokens", 0)
    text = (response["choices"][0]["message"]["content"] or "").strip(" :\n")
    return text, elapsed, out_tok


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default=str(DEFAULT_IMAGE))
    parser.add_argument("--only", choices=[c[0] for c in CONFIGS])
    args = parser.parse_args()

    path = Path(args.image)
    if not path.exists():
        raise SystemExit(f"이미지를 찾을 수 없습니다: {path}")
    original = Image.open(path).convert("RGB")

    print(f"입력 이미지 : {path.name} ({original.width}x{original.height})")
    print("모델 로딩 중...")
    model = load_vlm()
    # 첫 추론에는 초기화 비용이 섞인다 ― 작은 입력으로 한 번 버리고 잰다
    run(model, shrink(original, 224), "안녕", 1)

    rows = []
    for name, label, prompt, max_tokens, max_side in CONFIGS:
        if args.only and name != args.only:
            continue
        image = shrink(original, max_side)
        text, elapsed, out_tok = run(model, image, prompt, max_tokens)
        rows.append({
            "config": name, "label": label,
            "image": f"{image.width}x{image.height}", "max_tokens": max_tokens,
            "output_tokens": out_tok,
            "seconds": round(elapsed, 1), "output": text,
        })
        print(f"\n[{name}] {label}  이미지 {image.width}x{image.height}, "
              f"max_tokens {max_tokens}")
        print(f"  출력 토큰 {out_tok} / {elapsed:.1f}s")
        print("  출력 : " + textwrap.fill(text, 44, subsequent_indent=" " * 9))

    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print("\n[요약]")
    print(f"  {'설정':<14}{'이미지':>10}{'출력토큰':>9}{'시간':>9}")
    for r in rows:
        print(f"  {r['config'] + ' ' + r['label']:<14}{r['image']:>10}"
              f"{r['output_tokens']:>9}{r['seconds']:>8.1f}s")
    if len(rows) > 1:
        base, best = rows[0]["seconds"], rows[-1]["seconds"]
        print(f"\n  {rows[0]['config']} → {rows[-1]['config']} : "
              f"{base:.1f}s → {best:.1f}s ({base / best:.1f}배 빨라짐)")
    print(f"\nCSV 저장: {CSV_PATH.name}")


if __name__ == "__main__":
    main()
