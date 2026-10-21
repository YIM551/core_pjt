# -*- coding: utf-8 -*-
"""[page 64] 실습 4-3 ― 웹 대시보드 서버 (2단계 : + LLM 답변).

실습 3-1 의 대시보드 서버에 /api/llm-answer 하나를 더한다.
  - 입력 : 프런트가 보낸 질문 + YOLO 요약 + VLM 설명 + 손 방향
  - 처리 : 실습 4-1 의 출처별 블록과 규칙 그대로 LLM 에 넣는다
  - 출력 : {need_more_info, message, user_content}

오늘은 '설명' 까지만 한다. 로봇을 움직일지 고르는 도구 호출(tool call)은 3일차에
이 응답에 tool 필드를 더해서 만든다 ― 그래서 지금은 시뮬레이터 로봇이 움직이지 않는다.

실행:
    python 대시보드_LLM연결.py      # 브라우저에서 http://127.0.0.1:8000
"""
import os

# torch(GPU)와 llama.cpp(ggml-cuda)가 한 프로세스에 있으면 충돌한다 → CPU 로 고정
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

import base64
import io
import re
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
LLM_GGUF_PATH = PROJECT_ROOT / "models" / "Qwen3-4B-Q4_K_M.gguf"

VLM_PROMPT = (
    "이 이미지를 한국어 한 문장으로 설명해줘. 40자 이내로 쓰고, 문장 끝에 "
    "'장애물 있음' 또는 '장애물 없음' 을 붙여줘. "
    "형식 예: 복도에 의자 두 개가 놓여 있다, 장애물 있음."
)
VLM_MAX_TOKENS = 60
VLM_MAX_SIDE = 448

# 실습 4-1 의 규칙 그대로 ― 블록 이름은 아래 build_user_content 와 글자까지 같다
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
LLM_MAX_TOKENS = 256
DIRECTION_KO = {"up": "위", "down": "아래", "left": "왼쪽", "right": "오른쪽"}
_THINK_RE = re.compile(r"<think>.*?(?:</think>|\Z)", re.DOTALL)

app = FastAPI(title="2회차 2일차 ― 웹 대시보드 서버 (+ LLM)")

# ---------------------------------------------------------------------------
# 지연 로딩 + 락 (1일차 Part 2 의 double-checked locking)
# ---------------------------------------------------------------------------
_models = {"yolo": None, "vlm": None, "llm": None}
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


def _load_llm():
    from llama_cpp import Llama

    return Llama(model_path=str(LLM_GGUF_PATH), n_ctx=4096,
                 n_threads=os.cpu_count(), verbose=False)


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


def build_user_content(prompt: str, yolo_summary: str, vlm_description: str,
                       gesture_direction: str) -> str:
    """출처별 블록 + 질문 (실습 4-1 과 같은 형식). 방향을 모르면 '인식 불가'."""
    direction = DIRECTION_KO.get(gesture_direction, "인식 불가")
    return (
        f"[YOLO 객체 인식] {yolo_summary.strip() or '없음'}\n"
        f"[VLM 장면 설명] {vlm_description.strip() or '없음'}\n"
        f"[손 제스처] 가리키는 방향: {direction}\n\n"
        f"[사용자 질문] {prompt}"
    )


def answer(user_content: str) -> str:
    model = _get("llm", _load_llm)
    with _run_locks["llm"]:
        response = model.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content + " /no_think"},
            ],
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.0,
        )
    raw = response["choices"][0]["message"]["content"] or ""
    return _THINK_RE.sub("", raw).strip() or "답변을 생성하지 못했습니다."


def _log(name, t0, detail):
    """요청마다 한 줄 ― 시작 시각과 소요 시간을 남긴다."""
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


@app.post("/api/llm-answer")
async def llm_answer(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        return JSONResponse({"error": "empty_prompt"}, status_code=400)

    user_content = build_user_content(
        prompt,
        str(body.get("yolo_summary", "")),
        str(body.get("vlm_description", "")),
        str(body.get("gesture_direction", "unknown")))
    print("[llm ] 입력\n" + "\n".join("        " + ln for ln in user_content.splitlines()),
          flush=True)
    t0 = time.time()
    try:
        message = await run_in_threadpool(answer, user_content)
    except Exception as exc:
        _log("llm", t0, f"실패 ({type(exc).__name__})")
        return JSONResponse({"error": "llm_failed"}, status_code=500)
    _log("llm", t0, message)
    # 오늘은 설명만 한다 ― 되묻기(need_more_info)와 도구 호출은 3일차
    return {"need_more_info": False,
            "message": message,
            "user_content": user_content}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
