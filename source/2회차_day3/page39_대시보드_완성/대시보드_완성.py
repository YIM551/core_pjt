# -*- coding: utf-8 -*-
"""[page 39] 실습 4-1 ― 웹 대시보드 서버 (완성 : 의도 파악 + 도구 호출 + 조건 분기).

2일차 실습 4-3 서버에서 /api/llm-answer 하나만 바뀐다.
  - 2일차 : LLM 이 설명 문장만 돌려줬다 → 로봇은 움직이지 않았다
  - 오늘   : LLM 이 도구(move | describe | ask)와 인자를 고르고, 코드가 규칙을 보장한다
            → 프런트가 move 면 시뮬레이터 로봇을 움직이고, ask 면 되묻는다

API 명세는 ../API_설계.md ― 주석의 [A1]~[A5], [R1]~[R5] 가 명세 번호다.

실행:
    python 대시보드_완성.py         # 브라우저에서 http://127.0.0.1:8000
확인 (다른 터미널):
    cd ..\\page16_API_검증  &&  python API_검증.py
"""
import os

# torch(GPU)와 llama.cpp(ggml-cuda)가 한 프로세스에 있으면 충돌한다 → CPU 로 고정
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

import base64
import io
import json
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
DAY_DIR = BASE_DIR.parent                           # 2회차_day3
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

# ---------------------------------------------------------------------------
# 도구 정의 (실습 2-1 과 같다)
# ---------------------------------------------------------------------------
TOOLS = ("move", "describe", "ask")
DIRECTIONS = ("up", "down", "left", "right")
DIRECTION_KO = {"up": "위", "down": "아래", "left": "왼쪽", "right": "오른쪽"}
DIRECTION_TO = {"up": "위로", "down": "아래로", "left": "왼쪽으로", "right": "오른쪽으로"}
DIRECTION_ALIASES = {"위": "up", "아래": "down", "왼쪽": "left", "오른쪽": "right"}
MAX_STEPS = 10
ASK_MESSAGE = "어느 쪽으로 갈까요? 방향을 말하거나 손으로 가리켜 주세요."
FALLBACK_MESSAGE = "답변을 생성하지 못했습니다."

SYSTEM_PROMPT = (
    "너는 격자 시뮬레이터의 로봇을 조종하는 어시스턴트다. 인식 모델이 만든 Text 블록과 "
    "사용자 질문을 보고 사용자의 의도를 파악해 도구 하나를 고른다.\n"
    "도구:\n"
    "- move(direction, steps): 로봇 이동. direction 은 up|down|left|right, steps 는 1~10 정수\n"
    "- describe(): 이동 없이 장면에 대한 질문에 답한다\n"
    "- ask(): 이동하라는데 방향을 알 수 없을 때 사용자에게 되묻는다\n"
    "규칙:\n"
    "- 방향은 [사용자 질문]에 있으면 그것을, 없으면 [손 제스처]를 따른다. "
    "둘 다 없으면 move 가 아니라 ask 를 고른다.\n"
    "- 칸 수가 없으면 1 이다.\n"
    "- 사람 · 물체의 개수는 반드시 [YOLO 객체 인식] 의 숫자를 쓴다. "
    "[VLM 장면 설명] 에 나온 개수는 쓰지 않는다.\n"
    "- 상황과 분위기는 [VLM 장면 설명] 을 참고한다.\n"
    "반드시 아래 JSON 한 개로만 답하고, 다른 글은 쓰지 마라. "
    "args 는 move 일 때만 채우고 나머지 도구는 {} 로 둔다.\n"
    '{"tool": "move|describe|ask", "args": {"direction": "up", "steps": 1}, '
    '"message": "<사용자에게 보일 한두 문장>"}'
)
LLM_MAX_TOKENS = 200
_THINK_RE = re.compile(r"<think>.*?(?:</think>|\Z)", re.DOTALL)

app = FastAPI(title="2회차 3일차 ― 웹 대시보드 서버 (완성)")

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
# 인식 ― 2일차 대시보드 서버 그대로
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


# ---------------------------------------------------------------------------
# 의도 파악 + 도구 호출 (실습 2-1) + 조건 분기 (실습 3-1)
# ---------------------------------------------------------------------------
def build_user_content(prompt: str, yolo_summary: str, vlm_description: str,
                       gesture_direction: str) -> str:
    """출처별 블록 + 질문 (2일차 실습 4-1 과 같은 형식). 방향을 모르면 '인식 불가'."""
    direction = DIRECTION_KO.get(gesture_direction, "인식 불가")
    return (
        f"[YOLO 객체 인식] {yolo_summary.strip() or '없음'}\n"
        f"[VLM 장면 설명] {vlm_description.strip() or '없음'}\n"
        f"[손 제스처] 가리키는 방향: {direction}\n\n"
        f"[사용자 질문] {prompt}"
    )


def ask_llm(messages: list) -> str:
    """사고 모드를 끄고(/no_think) 답을 받는다. history 에는 /no_think 를 남기지 않는다."""
    model = _get("llm", _load_llm)
    last = {"role": "user", "content": messages[-1]["content"] + " /no_think"}
    with _run_locks["llm"]:
        response = model.create_chat_completion(
            messages=messages[:-1] + [last], max_tokens=LLM_MAX_TOKENS, temperature=0.0)
    return _THINK_RE.sub("", response["choices"][0]["message"]["content"] or "").strip()


def extract_json(text: str):
    """첫 '{' ~ 마지막 '}' 만 잘라 파싱한다 (2일차 실습 4-2)."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def to_direction(value) -> str:
    value = str(value).strip().lower()
    value = DIRECTION_ALIASES.get(value, value)
    return value if value in DIRECTIONS else "unknown"


def to_steps(value) -> int:
    """[R2] 1 ~ MAX_STEPS 정수로 맞춘다. 읽을 수 없으면 1."""
    try:
        steps = int(value)
    except (TypeError, ValueError):
        return 1
    return min(max(steps, 1), MAX_STEPS)


def parse_tool_call(raw: str) -> dict:
    """[R1][R2] 모델이 무엇을 내놓든 {tool, args, message} 모양을 보장한다."""
    data = extract_json(raw)
    if data is None:                       # JSON 이 아니면 설명으로 본다
        return {"tool": "describe", "args": {}, "message": raw or FALLBACK_MESSAGE}
    tool = str(data.get("tool", "")).strip().lower()
    if tool not in TOOLS:                  # 없는 도구 → describe
        tool = "describe"
    message = str(data.get("message", "")).strip()
    args = {}
    if tool == "move":
        raw_args = data["args"] if isinstance(data.get("args"), dict) else data
        direction = to_direction(raw_args.get("direction"))
        if direction == "unknown":         # 방향 없는 move → ask
            tool = "ask"
        else:
            args = {"direction": direction,
                    "steps": to_steps(raw_args.get("steps"))}
    if tool == "ask" and not message:
        message = ASK_MESSAGE
    return {"tool": tool, "args": args, "message": message or FALLBACK_MESSAGE}


# 방향어 목록 ― 위 : 위쪽 · 위로 · '위 '(위 + 공백) · 문장 끝의 위($),  아래 : 아래쪽 · 아래로 포함
# ('위치' · '위험' · '위에' 는 방향이 아니다)
_DIRECTION_WORD_RE = re.compile(
    r"오른쪽|오른편|우측|왼쪽|왼편|좌측|아래|밑|위쪽|위로|위 |위$|\b(?:up|down|left|right)\b", re.I)
# 방향어 앞글자 → 방향 ('오른쪽 · 오른편', '아래쪽 · 아래로' 처럼 뒤가 달라도 같은 방향)
_WORD_TO_DIRECTION = {"오른": "right", "우측": "right", "왼": "left", "좌측": "left",
                      "아래": "down", "밑": "down", "위": "up"}
_STEPS_RE = re.compile(r"(\d+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*칸")
_KOREAN_NUMBER = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5,
                  "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
_QUESTION_RE = re.compile(r"\[사용자 질문\] (.*)")


def said_direction(text: str):
    """질문에 적힌 방향어 → up / down / left / right. 없으면 None."""
    match = _DIRECTION_WORD_RE.search(text)
    if not match:
        return None
    word = match.group(0).lower()
    return next((d for head, d in _WORD_TO_DIRECTION.items() if word.startswith(head)), word)


def said_steps(text: str):
    """질문에 적힌 칸 수 ('3칸', '세 칸'). 없으면 None."""
    match = _STEPS_RE.search(text)
    return to_steps(_KOREAN_NUMBER.get(match.group(1), match.group(1))) if match else None


def has_direction_evidence(prompt: str, history: list, gesture_direction: str) -> bool:
    """[R3] 방향의 근거가 입력에 있는가 ― 질문(이전 턴 포함)의 방향어 또는 손 제스처."""
    if gesture_direction in DIRECTIONS:
        return True
    questions = [prompt] + [m.group(1) for turn in history if turn["role"] == "user"
                            for m in [_QUESTION_RE.search(turn["content"])] if m]
    return any(_DIRECTION_WORD_RE.search(q) for q in questions)


def ask_for_direction(steps: int) -> dict:
    """[R3] 방향만 모른다 → 되묻는다. 이미 아는 칸 수는 args 에 기억해 둔다."""
    return {"tool": "ask", "args": {"steps": steps},
            "message": f"어느 쪽으로 {steps}칸 갈까요? 방향을 말하거나 손으로 가리켜 주세요."}


def move_with_steps(direction: str, steps: int) -> dict:
    """코드가 확정한 이동 ― 안내 문장도 확정한 인자에 맞춰 다시 쓴다."""
    return {"tool": "move", "args": {"direction": direction, "steps": steps},
            "message": f"{DIRECTION_TO[direction]} {steps}칸 이동합니다."}


def pending_steps(history: list):
    """[R5] 직전 답이 ask 였다면 그때 기억해 둔 칸 수. 아니면 None."""
    for turn in reversed(history):
        if turn["role"] == "assistant":
            data = extract_json(turn["content"]) or {}
            args = data.get("args") if isinstance(data.get("args"), dict) else {}
            if data.get("tool") == "ask" and "steps" in args:
                return to_steps(args["steps"])
            return None
    return None


def apply_rules(call: dict, prompt: str, history: list, gesture_direction: str) -> dict:
    """[R3][R5] LLM 이 고른 도구를, 입력에 실제로 적힌 근거로 확정한다."""
    said = said_direction(prompt)
    steps = said_steps(prompt)
    pending = pending_steps(history)
    if call["tool"] == "move":
        if not has_direction_evidence(prompt, history, gesture_direction):
            return ask_for_direction(steps or call["args"]["steps"])       # [R3] 근거 없는 이동
        return move_with_steps(said or call["args"]["direction"],          # [R3] 적힌 방향이 먼저
                               steps or pending or call["args"]["steps"])  # [R5] 칸 수: 질문 → 기억 → LLM
    if call["tool"] == "ask":
        if pending and said:
            return move_with_steps(said, steps or pending)                  # [R5] 방향만 답해도 이동
        return ask_for_direction(steps or pending or 1)                     # [R3] 칸 수를 기억해 되묻기
    return call


def decide_tool(prompt: str, yolo_summary: str, vlm_description: str,
                gesture_direction: str, history: list):
    """LLM 이 도구를 고르고, 코드가 조건 분기를 보장한다. (도구 호출, user_content) 반환."""
    user_content = build_user_content(prompt, yolo_summary, vlm_description, gesture_direction)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history,
                {"role": "user", "content": user_content}]
    call = parse_tool_call(ask_llm(messages))
    return apply_rules(call, prompt, history, gesture_direction), user_content


def _log(name, t0, detail):
    """요청마다 한 줄 ― 시작 시각과 소요 시간을 남긴다."""
    start = time.strftime("%H:%M:%S", time.localtime(t0))
    print(f"[{name:<4}] 시작 {start}  {(time.time() - t0) * 1000:6.0f} ms  {detail}", flush=True)


# ---------------------------------------------------------------------------
# 라우트
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    """[A1] 대시보드 화면."""
    return FileResponse(WEB_DIR / "index.html")


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.get("/mediapipe/gesture_recognizer.task")
def gesture_model():
    """[A2] 제스처 모델 ― 가중치는 models\\ 한 곳에만 둔다."""
    return FileResponse(GESTURE_MODEL_PATH)


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
    """[A3] 이미지 → {objects: [{label, confidence, box}]}"""
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
    """[A4] 이미지 → {description}"""
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


def _read_history(raw) -> list:
    """[R5] 되묻기 이후의 후속 턴이면 화면이 이전 대화를 보낸다. 형식이 틀린 항목은 버린다."""
    history = []
    for turn in raw if isinstance(raw, list) else []:
        if isinstance(turn, dict) and turn.get("role") in ("user", "assistant") \
                and str(turn.get("content", "")).strip():
            history.append({"role": turn["role"], "content": str(turn["content"]).strip()})
    return history


@app.post("/api/llm-answer")
async def llm_answer(request: Request):
    """[A5] 인식 Text + 질문 → {tool, args, need_more_info, message, user_content}"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        return JSONResponse({"error": "empty_prompt"}, status_code=400)

    t0 = time.time()
    try:
        call, user_content = await run_in_threadpool(
            decide_tool,
            prompt,
            str(body.get("yolo_summary", "")),
            str(body.get("vlm_description", "")),
            to_direction(body.get("gesture_direction", "unknown")),
            _read_history(body.get("history")))
    except Exception as exc:
        _log("llm", t0, f"실패 ({type(exc).__name__})")
        return JSONResponse({"error": "llm_failed"}, status_code=500)
    _log("tool", t0, f"Q. {prompt} → {call['tool']} {call['args'] or ''}  {call['message']}")
    return {**call,
            "need_more_info": call["tool"] == "ask",     # [R4]
            "user_content": user_content}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
