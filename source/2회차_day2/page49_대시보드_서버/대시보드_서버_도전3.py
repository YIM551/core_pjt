# -*- coding: utf-8 -*-
"""[도전 문제 3] GET /api/health 로 어떤 모델이 메모리에 올라와 있는지 보이게 하시오.

    ① 응답 예 : {"status": "ok", "yolo_loaded": false, "vlm_loaded": false}
    ② 서버를 켠 직후에는 모두 false
    ③ [전송] 한 번 뒤에는 모두 true
    ④ 확인만 한다 ― 모델을 새로 올리지 않는다

실습 3-1 의 대시보드_서버.py 와 같은 서버다. 고칠 곳은 맨 아래 health() 하나다.
정답 : 대시보드_서버_도전3_정답.py

실행 · 확인:
    python 대시보드_서버_도전3.py
    브라우저 주소창에 127.0.0.1:8000/api/health → 대시보드에서 [전송] → 다시 새로 고침
"""
import os

# torch(GPU)와 llama.cpp(ggml-cuda)가 한 프로세스에 있으면 충돌한다 → CPU 로 고정
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

import base64
import io
import threading
import time
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 2회차_day2
WEB_DIR = DAY_DIR.parent / "2회차_web"              # 제공된 프런트 (index.html, mediapipe/)
PROJECT_ROOT = DAY_DIR.parents[1]

YOLO_MODEL_PATH = PROJECT_ROOT / "yolo11n.pt"
VLM_GGUF_PATH = PROJECT_ROOT / "models" / "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
VLM_MMPROJ_PATH = PROJECT_ROOT / "models" / "mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf"
GESTURE_MODEL_PATH = PROJECT_ROOT / "models" / "gesture_recognizer.task"

VLM_PROMPT = (
    "이 이미지를 한국어 한 문장으로 설명해줘. 40자 이내로 쓰고, 문장 끝에 "
    "'장애물 있음' 또는 '장애물 없음' 을 붙여줘. "
    "형식 예: 복도에 의자 두 개가 놓여 있다, 장애물 있음."
)
VLM_MAX_TOKENS = 60
VLM_MAX_SIDE = 448

app = FastAPI(title="2회차 2일차 ― 웹 대시보드 서버")

# ---------------------------------------------------------------------------
# 지연 로딩 + 락 (1일차 Part 2 의 double-checked locking)
# ---------------------------------------------------------------------------
_models = {"yolo": None, "vlm": None}
_init_locks = {name: threading.Lock() for name in _models}
# llama.cpp · YOLO 인스턴스는 한 번에 한 요청만 쓴다 (탭 두 개에서 동시에 보내도 안전하게)
_run_locks = {name: threading.Lock() for name in _models}


def _get(name, loader):
    if _models[name] is None:
        with _init_locks[name]:
            if _models[name] is None:
                _models[name] = loader()
    return _models[name]


def _load_yolo():
    from ultralytics import YOLO

    return YOLO(str(YOLO_MODEL_PATH))


def _load_vlm():
    from llama_cpp import Llama
    from llama_cpp.llama_chat_format import Qwen25VLChatHandler

    return Llama(
        model_path=str(VLM_GGUF_PATH),
        chat_handler=Qwen25VLChatHandler(clip_model_path=str(VLM_MMPROJ_PATH),
                                         verbose=False),
        n_ctx=4096,
        n_threads=os.cpu_count(),
        verbose=False,
    )


# ---------------------------------------------------------------------------
# 인식 ― 이미지 in, 결과 out (블로킹 → 라우트에서 스레드풀로 보낸다)
# ---------------------------------------------------------------------------
def detect_objects(image: Image.Image) -> list:
    model = _get("yolo", _load_yolo)
    with _run_locks["yolo"]:
        results = model.predict(image, conf=0.25, verbose=False)
    # box : 보낸 이미지의 픽셀 좌표 [x1, y1, x2, y2] ― 화면이 그대로 그린다
    return [
        {
            "label": model.names[int(box.cls)],
            "confidence": round(float(box.conf), 3),
            "box": [round(v, 1) for v in box.xyxy[0].tolist()],
        }
        for box in results[0].boxes
    ]


def describe_scene(image: Image.Image) -> str:
    model = _get("vlm", _load_vlm)
    if max(image.size) > VLM_MAX_SIDE:                 # 입력 줄이기 (VLM 레버)
        scale = VLM_MAX_SIDE / max(image.size)
        image = image.resize((round(image.width * scale), round(image.height * scale)))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    url = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    with _run_locks["vlm"]:
        response = model.create_chat_completion(
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": url}},
                {"type": "text", "text": VLM_PROMPT},
            ]}],
            max_tokens=VLM_MAX_TOKENS,
            temperature=0.0,
        )
    text = response["choices"][0]["message"]["content"] or ""
    return " ".join(text.split()).lstrip(":. ")     # 실습 1-2 normalize ― 앞 잡문자 제거


def _log(name, t0, detail):
    """요청마다 한 줄 ― 시작 시각과 소요 시간을 보면 두 요청이 겹쳐 도는지 알 수 있다."""
    start = time.strftime("%H:%M:%S", time.localtime(t0))
    print(f"[{name:<4}] 시작 {start}  {(time.time() - t0) * 1000:6.0f} ms  {detail}", flush=True)


# ---------------------------------------------------------------------------
# 라우트
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.get("/mediapipe/gesture_recognizer.task")
def gesture_model():
    return FileResponse(GESTURE_MODEL_PATH)          # 가중치는 models\ 한 곳에만 둔다


app.mount("/mediapipe", StaticFiles(directory=WEB_DIR / "mediapipe"), name="mediapipe")


async def _read_image(request: Request):
    """요청 본문(JPEG 바이트) → 이미지. 실패하면 (None, 400 응답)."""
    body = await request.body()
    if not body:
        return None, JSONResponse({"error": "empty_image"}, status_code=400)
    try:
        return Image.open(io.BytesIO(body)).convert("RGB"), None
    except (UnidentifiedImageError, OSError):
        return None, JSONResponse({"error": "invalid_image"}, status_code=400)


@app.post("/api/yolo-detect")
async def yolo_detect(request: Request):
    image, error = await _read_image(request)
    if error:
        return error
    t0 = time.time()
    try:
        objects = await run_in_threadpool(detect_objects, image)
    except Exception as exc:          # 부분 실패 ― VLM 요청은 따로 진행된다
        _log("yolo", t0, f"실패 ({type(exc).__name__})")
        return JSONResponse({"error": "yolo_failed"}, status_code=500)
    _log("yolo", t0, f"{image.width}x{image.height}  객체 {len(objects)}개")
    return {"objects": objects}


@app.post("/api/vlm-describe")
async def vlm_describe(request: Request):
    image, error = await _read_image(request)
    if error:
        return error
    t0 = time.time()
    try:
        description = await run_in_threadpool(describe_scene, image)
    except Exception as exc:
        _log("vlm", t0, f"실패 ({type(exc).__name__})")
        return JSONResponse({"error": "vlm_failed"}, status_code=500)
    _log("vlm", t0, description)
    return {"description": description}


@app.get("/api/health")
def health():
    # TODO ① ~ ④ ― 모델마다 메모리에 올라와 있는지 알려 준다
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
