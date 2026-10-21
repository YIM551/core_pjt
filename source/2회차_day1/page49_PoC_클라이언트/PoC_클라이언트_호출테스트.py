# -*- coding: utf-8 -*-
"""[page 49] 실습 4-2 ― PoC 서버 동작 확인 클라이언트.

같은 이미지 1장을 두 엔드포인트에 보내고, 결과와 소요 시간을 나란히 출력한다.

확인 항목 (강의 자료 page 49~50)
  1. 두 결과가 같은 장면을 서로 다른 방식으로 설명하고 있는가?
  2. YOLO가 놓친 것을 VLM이 잡았는가? 그 반대는?
  3. 각각 몇 ms 걸렸는가?  → 2일차 병렬 실행 설계의 근거가 된다.

사전 준비:
    uvicorn PoC_FastAPI서버:app --port 8000

실행:
    python PoC_클라이언트_호출테스트.py
    python PoC_클라이언트_호출테스트.py --yolo-only      # 빠른 확인
    python PoC_클라이언트_호출테스트.py --parallel       # 2일차 미리보기
"""
import argparse
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day1 (공용 자료)
DEFAULT_IMAGE = DAY_DIR / "samples" / "sample.jpg"


def post_image(base_url: str, endpoint: str, image_bytes: bytes,
               timeout: float) -> dict:
    """raw JPEG 바이트를 그대로 POST 한다 (멀티파트 아님)."""
    url = f"{base_url.rstrip('/')}{endpoint}"
    response = httpx.post(
        url, content=image_bytes,
        headers={"Content-Type": "image/jpeg"}, timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--image", default=str(DEFAULT_IMAGE))
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--yolo-only", action="store_true")
    parser.add_argument("--parallel", action="store_true",
                        help="두 엔드포인트를 동시에 호출 (2일차 병렬 실행 미리보기)")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"이미지를 찾을 수 없습니다: {image_path}")
    image_bytes = image_path.read_bytes()

    try:
        health = httpx.get(f"{args.url}/api/health", timeout=5.0).json()
    except httpx.HTTPError:
        raise SystemExit(
            f"서버에 연결할 수 없습니다: {args.url}\n"
            '  먼저 실행하세요 →  uvicorn "PoC_FastAPI서버:app" --port 8000'
        )
    print(f"서버 상태   : {health}")
    print(f"입력 이미지 : {image_path.name} ({len(image_bytes) / 1024:.0f} KB)\n")

    print("[1] POST /api/yolo-detect")
    yolo = post_image(args.url, "/api/yolo-detect", image_bytes, args.timeout)
    print(f"    summary : {yolo['summary']}")
    print(f"    elapsed : {yolo['elapsed_ms']} ms\n")

    if args.yolo_only:
        print("(--yolo-only) VLM 호출은 건너뜁니다.")
        return

    if args.parallel:
        print("[2] 두 엔드포인트 동시 호출 (병렬)")
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_yolo = pool.submit(post_image, args.url, "/api/yolo-detect",
                                 image_bytes, args.timeout)
            f_vlm = pool.submit(post_image, args.url, "/api/vlm-describe",
                                image_bytes, args.timeout)
            yolo, vlm = f_yolo.result(), f_vlm.result()
        total = (time.perf_counter() - t0) * 1000
        print(f"    YOLO : {yolo['elapsed_ms']} ms ― {yolo['summary']}")
        print(f"    VLM  : {vlm['elapsed_ms']} ms ― {vlm['description']}")
        print(f"    전체 : {total:.0f} ms (직렬이면 "
              f"{yolo['elapsed_ms'] + vlm['elapsed_ms']} ms)")
    else:
        print("[2] POST /api/vlm-describe  (CPU 추론이라 1~2분 걸립니다)")
        vlm = post_image(args.url, "/api/vlm-describe", image_bytes, args.timeout)
        print(f"    description : {vlm['description']}")
        print(f"    elapsed     : {vlm['elapsed_ms']} ms\n")
        print("VLM이 전체 응답 시간을 지배합니다 "
              "→ 2일차에 두 모델을 병렬로 실행하는 이유입니다.")


if __name__ == "__main__":
    main()
