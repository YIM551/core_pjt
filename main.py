# -*- coding: utf-8 -*-
"""웹 대시보드 서버 (완성 : 의도 파악 + 도구 호출 + 조건 분기).

source\\2회차_day3\\page39_대시보드_완성\\대시보드_완성.py 와 같은 코드다 (경로만 이 폴더 기준).
  - LLM 이 도구(move | describe | ask)와 인자를 고르고, 코드가 규칙을 보장한다
    → 프런트가 move 면 시뮬레이터 로봇을 움직이고, ask 면 되묻는다

주석의 [A1]~[A5], [R1]~[R5] 는 README 의 API · 규칙 표 번호다.

실행:
    uvicorn main:app --host 127.0.0.1 --port 8000    # 브라우저에서 http://127.0.0.1:8000
"""
import os

# torch(GPU)와 llama.cpp(ggml-cuda)가 한 프로세스에 있으면 충돌한다 → CPU 로 고정
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

import base64
import hashlib
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
from perception_consistency import analyze_detections, reconcile, grounded_description
from inference_optimization import ExactResultCache, is_simple_scene_question, bounded_setting, choose_vlm_side

BASE_DIR = Path(__file__).resolve().parent          # 이 폴더 (main.py · index.html · mediapipe/ · models/)
WEB_DIR = BASE_DIR                                  # 제공된 프런트 (index.html, mediapipe/)

YOLO_MODEL_PATH = Path(os.environ.get("CORE_YOLO_MODEL", str(BASE_DIR / "yolo11n.pt"))).resolve()
VLM_GGUF_PATH = BASE_DIR / "models" / "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
VLM_MMPROJ_PATH = BASE_DIR / "models" / "mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf"
GESTURE_MODEL_PATH = BASE_DIR / "models" / "gesture_recognizer.task"
LLM_GGUF_PATH = BASE_DIR / "models" / "Qwen3-4B-Q4_K_M.gguf"

VLM_PROMPT = (
    "이 이미지를 한국어 한 문장으로 설명해줘. 40자 이내로 쓰고, 문장 끝에 "
    "'장애물 있음' 또는 '장애물 없음' 을 붙여줘. "
    "형식 예: 복도에 의자 두 개가 놓여 있다, 장애물 있음."
)
VLM_MAX_TOKENS = bounded_setting(os.environ.get("CORE_VLM_MAX_TOKENS", "60"), "CORE_VLM_MAX_TOKENS", 16, 256)
VLM_MAX_SIDE = bounded_setting(os.environ.get("CORE_VLM_MAX_SIDE", "420"), "CORE_VLM_MAX_SIDE", 112, 1024)
VLM_DETAIL_SIDE = bounded_setting(os.environ.get("CORE_VLM_DETAIL_SIDE", "448"), "CORE_VLM_DETAIL_SIDE", 112, 1024)
VLM_ADAPTIVE = os.environ.get("CORE_VLM_ADAPTIVE", "1") == "1"
VLM_MAX_CHARS = 40
# 설치한 llama-cpp 빌드에 따라 한자가 섞일 때가 있다 ― 그때만 이 system 메시지를 붙여 다시 묻는다
VLM_KOREAN_SYSTEM = "너는 이미지를 한국어(한글)로만 설명한다. 한자 · 일본어 · 중국어를 절대 쓰지 않는다."

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
    "너는 가정용 집사형 로봇의 격자 시뮬레이터를 조종하는 어시스턴트다. 인식 모델이 만든 Text 블록과 "
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
SCENE_FAST_PATH = os.environ.get("CORE_SCENE_FAST_PATH", "1") == "1"
_vlm_result_cache = ExactResultCache(capacity=max(0, min(32, int(os.environ.get("CORE_VLM_CACHE_SIZE", "8")))), ttl=60)
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


def describe_scene(image: Image.Image, max_side=None) -> str:
    model = _get("vlm", _load_vlm)
    side = VLM_MAX_SIDE if max_side is None else max_side
    if max(image.size) > side:                 # 입력 줄이기 (VLM 레버)
        scale = side / max(image.size)
        image = image.resize((round(image.width * scale), round(image.height * scale)))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    url = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    text = _ask_vlm(model, url)
    failed = [name for name, ok in check(text) if not ok]
    if failed:
        retry = _ask_vlm(model, url, system=VLM_KOREAN_SYSTEM)
        print(f"[vlm ] 규격 재시도 : {text} → {retry}", flush=True)
        if dict(check(retry))["한국어"]:
            text = retry
            failed = [name for name, ok in check(text) if not ok]
    # Preserve the model's obstacle statement while shortening only its description.
    # A missing statement or non-Korean output is a failure, never fabricated evidence.
    text = compact_vlm_text(text)
    failed = [name for name, ok in check(text) if not ok]
    if failed:
        raise ValueError("VLM output format failed: " + ", ".join(failed))
    return text


def describe_scene_cached(image):
    side = VLM_MAX_SIDE
    if VLM_ADAPTIVE:
        try:
            side = choose_vlm_side(detect_objects(image), VLM_MAX_SIDE, VLM_DETAIL_SIDE)
        except Exception:
            side = max(VLM_MAX_SIDE, VLM_DETAIL_SIDE)
    # Exact decoded pixels + shape/config. A different live frame always gets a new key.
    digest = hashlib.sha256(image.tobytes()).hexdigest()
    key = (digest, image.size, image.mode, VLM_PROMPT, side, VLM_MAX_TOKENS)
    description, hit = _vlm_result_cache.get_or_compute(key, lambda: describe_scene(image, max_side=side))
    return description, hit, side


def _ask_vlm(model, url: str, system: str = None) -> str:
    """이미지 1장 + 규격 프롬프트로 한 번 묻고 normalize 한 문장을 돌려준다."""
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": url}},
        {"type": "text", "text": VLM_PROMPT},
    ]})
    with _run_locks["vlm"]:
        response = model.create_chat_completion(
            messages=messages, max_tokens=VLM_MAX_TOKENS, temperature=0.0)
    return normalize(response["choices"][0]["message"]["content"] or "")


def normalize(text: str) -> str:
    """앞 잡문자(':' '.')와 줄바꿈을 없애고 첫 문장만 남긴다 (2일차 실습 1-2).
    '장애물 있음/없음' 을 두 번째 문장으로 따로 쓰면 첫 문장 끝으로 옮긴다."""
    text = " ".join(text.split()).lstrip(":. ")
    first = re.split(r"(?<=[.!?。])\s", text, maxsplit=1)[0].strip()
    obstacle = re.search(r"장애물 (있음|없음)", text)
    if obstacle and "장애물" not in first:
        first = f"{first.rstrip(' .')}, {obstacle.group(0)}."
    return first


def check(text: str) -> list:
    """규격 확인 ― 한국어 · 40자 이내 · 끝에 '장애물 있음/없음' (2일차 실습 1-2)."""
    hangul = len(re.findall(r"[가-힣]", text))
    letters = len(re.findall(r"[A-Za-z가-힣]", text)) or 1
    cjk = re.search(r"[぀-ヿ一-鿿]", text)       # 한자 · 가나가 섞이면 NG
    return [
        ("한국어", hangul / letters >= 0.8 and not cjk),
        (f"{VLM_MAX_CHARS}자 이내", len(text) <= VLM_MAX_CHARS),
        ("장애물 표기", bool(re.search(r"장애물 (있음|없음)\.?$", text))),
    ]


def compact_vlm_text(text: str) -> str:
    obstacle = re.search(r"장애물 (있음|없음)", text)
    if not obstacle or not dict(check(text))["한국어"] or len(text) <= VLM_MAX_CHARS:
        return text
    suffix = ", " + obstacle.group(0) + "."
    description = re.sub(r"장애물 (있음|없음).*", "", text).rstrip(" .,，")
    budget = VLM_MAX_CHARS - len(suffix) - 1
    shortened = description[:budget].rstrip(" .,，")
    if " " in shortened and len(shortened.rsplit(" ", 1)[0]) >= budget // 2:
        shortened = shortened.rsplit(" ", 1)[0]
    return shortened + "…" + suffix


# ---------------------------------------------------------------------------
# 의도 파악 + 도구 호출 (실습 2-1) + 조건 분기 (실습 3-1)
# ---------------------------------------------------------------------------
def build_user_content(prompt: str, yolo_summary: str, vlm_description: str,
                       gesture_direction: str) -> str:
    """출처별 블록 + 질문 (2일차 실습 4-1 과 같은 형식).
    손이 없으면('none') '손 없음', 손은 있는데 방향을 모르면 '인식 불가'."""
    direction = DIRECTION_KO.get(gesture_direction,
                                 "손 없음" if gesture_direction == "none" else "인식 불가")
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
    except (TypeError, ValueError, OverflowError):
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


# 방향어 ― '위' 는 뒤에 띄어쓰기 · '로' · '쪽' 이 올 때만 방향이다 ('위치' · '위험' · '위에' 는 아님)
_DIRECTION_WORD_RE = re.compile(r"오른쪽|왼쪽|(?<![가-힣A-Za-z])위(?=\s|로|쪽|$)|아래|\b(?:up|down|left|right)\b", re.I)
_WORD_TO_DIRECTION = {"오른쪽": "right", "왼쪽": "left", "아래": "down"}
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
    return _WORD_TO_DIRECTION.get(word, "up" if word.startswith("위") else word)


def said_steps(text: str):
    """질문에 적힌 칸 수 ('3칸', '세 칸'). 없으면 None."""
    match = _STEPS_RE.search(text)
    return to_steps(_KOREAN_NUMBER.get(match.group(1), match.group(1))) if match else None


def previous_direction(history: list):
    """이전 턴 질문에 적힌 방향어 (가장 최근 턴부터). 없으면 None.
    화면 흐름에서는 ask 로 끝난 턴(방향어 없음)만 history 에 남아 보통 None ― 명세 우선순위를 위한 방어 단계."""
    for turn in reversed(history):
        if turn["role"] == "user":
            match = _QUESTION_RE.search(turn["content"])
            if match and said_direction(match.group(1)):
                return said_direction(match.group(1))
    return None


def resolve_direction(prompt: str, history: list, gesture_direction: str):
    """[R3] 우선순위 : 프롬프트 방향어 → 이전 턴 질문 → 손 제스처. LLM 이 고른 방향은 쓰지 않는다."""
    return (said_direction(prompt) or previous_direction(history)
            or (gesture_direction if gesture_direction in DIRECTIONS else None))


def has_direction_evidence(prompt: str, history: list, gesture_direction: str) -> bool:
    """[R3] 셋 다 없으면 근거 없음 → 되묻는다."""
    return resolve_direction(prompt, history, gesture_direction) is not None


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
    direction = resolve_direction(prompt, history, gesture_direction)
    steps = said_steps(prompt)
    pending = pending_steps(history)
    # A direction-only reply completes the already established movement request,
    # even when the LLM misclassifies this short answer as describe.
    direction_reply = re.fullmatch(
        r"(?:오른쪽|왼쪽|위(?:쪽)?|아래(?:쪽)?|up|down|left|right)(?:으로|로)?[.!?]?",
        prompt.strip(), re.I)
    if pending is not None and direction is not None and direction_reply:
        return move_with_steps(direction, steps or pending)
    if call["tool"] == "move":
        if not has_direction_evidence(prompt, history, gesture_direction):
            return ask_for_direction(steps or call["args"]["steps"])       # [R3] 근거 없는 이동
        return move_with_steps(direction,                                  # [R3] 프롬프트 방향어 → 이전 턴 질문 → 손 제스처
                               steps or pending or call["args"]["steps"])  # [R5] 칸 수: 질문 → 기억 → LLM
    if call["tool"] == "ask":
        if has_direction_evidence(prompt, history, gesture_direction):
            return move_with_steps(direction, steps or pending or 1)        # [R5] 근거가 있으면 이동
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


@app.get("/api/health")
def health():
    return {"status": "ok", "yolo_model": YOLO_MODEL_PATH.name,
            "vlm_settings": {"max_side": VLM_MAX_SIDE, "max_tokens": VLM_MAX_TOKENS,
                             "adaptive": VLM_ADAPTIVE, "detail_side": VLM_DETAIL_SIDE},
            "loaded": {name: model is not None for name, model in _models.items()}}


@app.get("/api/sample-image")
def sample_image(name: str = "sofa"):
    paths = {"sofa": BASE_DIR / "samples/furniture_v2_sofa.jpg",
             "pointing": BASE_DIR / "samples/pointing_up.jpg",
             "victory": BASE_DIR / "samples/victory.jpg"}
    path = paths.get(name)
    if path is None or not path.is_file():
        return JSONResponse({"error": "sample_not_found"}, status_code=404)
    return FileResponse(path, media_type="image/jpeg")


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
    return {"objects": objects, "analysis": analyze_detections(objects)}


@app.post("/api/vlm-describe")
async def vlm_describe(request: Request):
    """[A4] 이미지 → {description}"""
    image, error = await _read_image(request)
    if error:
        return error
    t0 = time.time()
    try:
        description, cache_hit, max_side = await run_in_threadpool(describe_scene_cached, image)
    except Exception as exc:
        _log("vlm", t0, f"실패 ({type(exc).__name__})")
        return JSONResponse({"error": "vlm_failed"}, status_code=500)
    _log("vlm", t0, description)
    return {"description": description, "cache_hit": cache_hit, "max_side": max_side,
            "max_tokens": VLM_MAX_TOKENS}


def _read_history(raw) -> list:
    """[R5] 되묻기 이후의 후속 턴이면 화면이 이전 대화를 보낸다. 형식이 틀린 항목은 버린다."""
    history = []
    for turn in raw if isinstance(raw, list) else []:
        if isinstance(turn, dict) and turn.get("role") in ("user", "assistant") \
                and str(turn.get("content", "")).strip():
            history.append({"role": turn["role"], "content": str(turn["content"]).strip()})
    return history


def _read_gesture(raw) -> str:
    """손 방향 → up / down / left / right, 손이 없으면 'none', 그 밖은 'unknown'."""
    return "none" if str(raw).strip().lower() == "none" else to_direction(raw)


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
    inference_path = "llm"
    try:
        if SCENE_FAST_PATH and is_simple_scene_question(prompt) and (
                str(body.get("yolo_summary", "")).strip() or str(body.get("vlm_description", "")).strip()):
            # F206 already constructs the final cited description deterministically.
            # Avoid generating an LLM message only to discard it immediately afterward.
            call = {"tool": "describe", "args": {}, "message": ""}
            user_content = build_user_content(prompt, str(body.get("yolo_summary", "")),
                str(body.get("vlm_description", "")), _read_gesture(body.get("gesture_direction", "unknown")))
            inference_path = "scene_evidence"
        else:
            call, user_content = await run_in_threadpool(
                decide_tool,
                prompt,
                str(body.get("yolo_summary", "")),
                str(body.get("vlm_description", "")),
                _read_gesture(body.get("gesture_direction", "unknown")),
                _read_history(body.get("history")))
    except Exception as exc:
        _log("llm", t0, f"실패 ({type(exc).__name__})")
        return JSONResponse({"error": "llm_failed"}, status_code=500)
    yolo_text = str(body.get("yolo_summary", ""))
    vlm_text = str(body.get("vlm_description", ""))
    consistency = reconcile(yolo_text, vlm_text)
    # Source attribution is enforced after generation rather than left to prompting.
    if call["tool"] == "describe" and (yolo_text or vlm_text):
        call["message"] = grounded_description(yolo_text, vlm_text, consistency)
    _log("tool", t0, f"Q. {prompt} → {call['tool']} {call['args'] or ''}  {call['message']}")
    return {**call,
            "need_more_info": call["tool"] == "ask",     # [R4]
            "user_content": user_content, "consistency": consistency, "inference_path": inference_path}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
