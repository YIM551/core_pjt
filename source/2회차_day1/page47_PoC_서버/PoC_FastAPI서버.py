# -*- coding: utf-8 -*-
"""[page 47~53] 실습 4 ― YOLO + VLM 을 하나의 FastAPI 서버로 묶은 PoC.

page 47     두 엔드포인트를 '이미지 in → 텍스트 out' 으로 인터페이스 통일
page 48     추론은 블로킹 작업 → run_in_threadpool 로 위임, 지연 로딩 + 락으로 보호
page 49~50  같은 이미지로 두 엔드포인트를 호출해 결과 비교

오늘 하는 것 : 이미지 1장 → YOLO 결과 / VLM 설명, 각 단계 소요 시간 로그
오늘 안 하는 것 : LLM 통합 판단(2일차), 의도 파악·도구 호출(3일차), 카메라 스트리밍

실행 (반드시 이 파일이 있는 폴더에서):
    python PoC_FastAPI서버.py
    또는
    uvicorn PoC_FastAPI서버:app --port 8000

확인:
    python PoC_클라이언트_호출테스트.py
"""
import base64
import io
import os
import threading
import time
from collections import Counter
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError

# 규칙: 경로는 실행 디렉터리(cwd)에 의존하지 않도록 __file__ 기준 절대경로로 만든다.
BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day1 (공용 자료)
PROJECT_ROOT = DAY_DIR.parents[1]

YOLO_MODEL_PATH = PROJECT_ROOT / "yolo11n.pt"
VLM_GGUF_PATH = PROJECT_ROOT / "models" / "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
VLM_MMPROJ_PATH = PROJECT_ROOT / "models" / "mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf"

VLM_CONTEXT_SIZE = 4096
VLM_MAX_NEW_TOKENS = 200
VLM_DESCRIBE_PROMPT = "이 이미지에 무엇이 보이는지 한국어로 간결하게 설명해줘."

app = FastAPI(title="2회차 1일차 PoC ― YOLO + VLM")

# ---------------------------------------------------------------------------
# page 48 : 지연 로딩(lazy loading) + 락(lock)
#   - 서버는 즉시 기동하고, 첫 요청 때 모델을 올린다.
#   - 동시 요청이 각각 모델을 로드하면 메모리가 배로 드므로 초기화 구간을 잠근다.
# ---------------------------------------------------------------------------
_yolo_model = None
_yolo_init_lock = threading.Lock()
_vlm_model = None
_vlm_init_lock = threading.Lock()


def _resolve_device() -> str:
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def get_yolo_model():
    global _yolo_model
    if _yolo_model is None:
        with _yolo_init_lock:
            if _yolo_model is None:
                from ultralytics import YOLO

                model = YOLO(str(YOLO_MODEL_PATH))
                model.to(_resolve_device())
                _yolo_model = model
    return _yolo_model


def get_vlm_model():
    global _vlm_model
    if _vlm_model is None:
        with _vlm_init_lock:
            if _vlm_model is None:
                from llama_cpp import Llama
                from llama_cpp.llama_chat_format import Qwen25VLChatHandler

                chat_handler = Qwen25VLChatHandler(
                    clip_model_path=str(VLM_MMPROJ_PATH), verbose=False
                )
                _vlm_model = Llama(
                    model_path=str(VLM_GGUF_PATH),
                    chat_handler=chat_handler,
                    n_ctx=VLM_CONTEXT_SIZE,
                    n_threads=os.cpu_count(),
                    verbose=False,
                )
    return _vlm_model


# ---------------------------------------------------------------------------
# 추론 함수 (모두 동기·블로킹 ― 반드시 스레드풀에서 호출할 것)
# ---------------------------------------------------------------------------
def _run_yolo_inference(image: Image.Image) -> str:
    """검출 결과를 'person 2개, chair 1개' 형태의 한 문장으로 돌려준다."""
    model = get_yolo_model()
    results = model.predict(image, verbose=False,
                            half=(_resolve_device() == "cuda"))
    counter = Counter(model.names[int(b.cls)] for b in results[0].boxes)
    if not counter:
        return "인식된 객체 없음"
    return ", ".join(f"{name} {count}개" for name, count in counter.most_common())


def _run_vlm_inference(image: Image.Image) -> str:
    model = get_vlm_model()
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    data_url = "data:image/jpeg;base64," + base64.b64encode(
        buffer.getvalue()).decode("ascii")

    response = model.create_chat_completion(
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": VLM_DESCRIBE_PROMPT},
            ],
        }],
        max_tokens=VLM_MAX_NEW_TOKENS,
        temperature=0.0,
    )
    content = response["choices"][0]["message"]["content"]
    return content.strip() if content else ""


async def _read_image(request: Request) -> Image.Image:
    """raw body(JPEG 바이트)를 PIL 이미지로 디코딩한다.

    멀티파트(UploadFile) 대신 raw body 를 쓰면 프런트엔드가
    fetch(url, { body: blob }) 한 줄로 보낼 수 있다.
    """
    body = await request.body()
    if not body:
        raise ValueError("이미지 본문이 비어 있습니다")
    return Image.open(io.BytesIO(body)).convert("RGB")


# ---------------------------------------------------------------------------
# page 47 : 엔드포인트 ― 둘 다 '이미지 in → 텍스트 out'
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "device": _resolve_device(),
        "yolo_loaded": _yolo_model is not None,
        "vlm_loaded": _vlm_model is not None,
    }


@app.post("/api/yolo-detect")
async def yolo_detect(request: Request):
    try:
        image = await _read_image(request)
    except (ValueError, UnidentifiedImageError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    t0 = time.perf_counter()
    summary = await run_in_threadpool(_run_yolo_inference, image)
    elapsed_ms = round((time.perf_counter() - t0) * 1000)
    print(f"[yolo] {elapsed_ms}ms  {summary}")
    return {"summary": summary, "elapsed_ms": elapsed_ms}


@app.post("/api/vlm-describe")
async def vlm_describe(request: Request):
    try:
        image = await _read_image(request)
    except (ValueError, UnidentifiedImageError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    t0 = time.perf_counter()
    description = await run_in_threadpool(_run_vlm_inference, image)
    elapsed_ms = round((time.perf_counter() - t0) * 1000)
    print(f"[vlm ] {elapsed_ms}ms  {description[:40]}...")
    return {"description": description, "elapsed_ms": elapsed_ms}


if __name__ == "__main__":
    import uvicorn

    # python PoC_FastAPI서버.py 로 바로 띄울 수 있게 app 객체를 직접 넘긴다.
    uvicorn.run(app, host="127.0.0.1", port=8000)
