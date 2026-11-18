# -*- coding: utf-8 -*-
"""[page 61] A7 · A8 · R10 ― move 를 라즈베리파이 OLED · LED 로 출력한다 (PJT01 완성).

page47 서버에 더한다. A1 ~ A5 의 요청 · 응답 형식은 그대로다 (F101).
  - [A7] /api/robot-signal  {ip, direction} → 기기 /gpio-blink?pin= (D2)
  - [A8] /api/oled-display  {ip, direction} → 기기 /oled-display?text= (D3)
  - [R8] 방향 → 출력 매핑은 PC 가 정한다 ― LED right → 17, left → 27,
         OLED left → LEFT, right → RIGHT (좌우만 ― up · down 은 A7 · A8 400, 심화에서 추가)
  - [R10] A5 요청에 ip 가 있으면(기기 탭) 답변 문구만 칸 수 없이 ― tool · args · then 은 그대로
  - [R6] 기기 연결 실패 → 이 요청만 502 device_unreachable

기기 탭 질문도 오늘은 PC LLM(Qwen3-4B)이 도구를 고른다. 기기 LLM 은 2일차(PJT02)에 붙인다.

실행:
    python 대시보드_기기연동.py     # http://127.0.0.1:8000 → 기기 탭에서 '오른쪽으로 3칸 가'
확인 (다른 터미널):
    cd ..\\page71_API_검증  &&  python API_검증.py --device <PiIP>
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

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

BASE_DIR = Path(__file__).resolve().parent          # 이 실습 폴더
DAY_DIR = BASE_DIR.parent                           # 3회차_dayN
WEB_DIR = DAY_DIR.parent / "3회차_web"              # 제공된 프런트 (index.html, mediapipe/)
PROJECT_ROOT = DAY_DIR.parents[1]

YOLO_MODEL_PATH = PROJECT_ROOT / "yolo11n.pt"
VLM_GGUF_PATH = PROJECT_ROOT / "models" / "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
VLM_MMPROJ_PATH = PROJECT_ROOT / "models" / "mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf"
GESTURE_MODEL_PATH = PROJECT_ROOT / "models" / "gesture_recognizer.task"
LLM_GGUF_PATH = PROJECT_ROOT / "models" / "Qwen3-4B-Q4_K_M.gguf"

# [개선 ①] 한 문장(40자)에는 '어디에' 가 없다 → 색과 위치를 담아 2 ~ 3문장
VLM_PROMPT = (
    "이 이미지를 한국어 2 ~ 3문장으로 설명해줘. "
    "주요 물체마다 색과 위치(화면 왼쪽 · 가운데 · 오른쪽)를 쓰고, "
    "끝에 '장애물 있음' 또는 '장애물 없음' 을 붙여줘. "
    "형식 예: 화면 오른쪽에 파란 버스가 서 있다. 가운데에 사람 세 명이 걷고 있다, 장애물 없음."
)
VLM_MAX_TOKENS = 150                                    # 60 → 150 : 문장이 길어진 만큼 늘린다
VLM_MAX_SIDE = 448
VLM_MAX_SENTENCES = 3
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
NO_SCENE_MESSAGE = "카메라 영상이 없어 주변을 설명할 수 없습니다."
# 답변에 시뮬레이터식 표현이 남았는지 본다 ('버스가 이동한다' 같은 장면 묘사는 통과)
_GRID_TALK_RE = re.compile(r"칸|로봇|시뮬레이터|격자|(?:쪽|위|아래)으?로\s*이동")

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

# ---------------------------------------------------------------------------
# 라즈베리파이 기기 서버 (3회차) ― 기기 서버(camera_server.py)의 포트 · 경로와 같아야 한다
# ---------------------------------------------------------------------------
DEVICE_PORT = 8080
DEVICE_STREAM_PATH = "/stream.mjpg"        # [D1]
DEVICE_GPIO_PATH = "/gpio-blink"           # [D2]
DEVICE_OLED_PATH = "/oled-display"         # [D3]
# [R8] 방향 → 출력. 매핑은 PC 가 정하고 기기는 받은 핀 · 글자만 쓴다. LED 는 좌우 2개뿐이다.
DIRECTION_GPIO_PIN = {"right": 17, "left": 27}
DIRECTION_OLED_TEXT = {"left": "LEFT", "right": "RIGHT", "up": "UP", "down": "DOWN",}
DEVICE_CONNECT_TIMEOUT = 3.0
STREAM_READ_TIMEOUT = 10.0                 # [F105] 데이터만 끊기는 '조용한 단절' 감지
DEVICE_SIGNAL_TIMEOUT = 5.0                # LED 3회 점멸(약 1.8초)을 기다린다
_DEVICE_HOST_RE = re.compile(r"^[A-Za-z0-9.-]{1,253}$")   # IP 또는 호스트 이름만 (경로 끼워넣기 방지)

app = FastAPI(title="3회차 1일차 ― 기기 연동 (PJT01 완성)")

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
    text = _ask_vlm(model, url)
    failed = [name for name, ok in check(text) if not ok]
    if "한국어" in failed:                             # 한자 · 가나가 섞이면 한글로만 쓰라고 한 번 더 묻는다
        retry = _ask_vlm(model, url, system=VLM_KOREAN_SYSTEM)
        print(f"[vlm ] 한국어 아님 → 다시 물음 : {text} → {retry}", flush=True)
        if dict(check(retry))["한국어"]:
            text = retry
            failed = [name for name, ok in check(text) if not ok]
    if failed:                                         # 자르지 않는다 ― '장애물 있음/없음' 이 잘릴 수 있다
        print(f"[vlm ] 규격 벗어남 ({', '.join(failed)}) : {text}", flush=True)
    return text


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
    """앞 잡문자(':' '.')와 줄바꿈을 없애고 한 줄로 만든다 (2일차 실습 1-2).
    [개선 ①] 2 ~ 3문장을 모두 남긴다 ― 첫 문장만 자르면 위치 · 색 설명이 사라진다."""
    return " ".join(text.split()).lstrip(":. ")


def check(text: str) -> list:
    """규격 확인 ― 한국어 · 3문장 이내 · 끝에 '장애물 있음/없음' (2일차 실습 1-2, 개선 ①)."""
    hangul = len(re.findall(r"[가-힣]", text))
    letters = len(re.findall(r"[A-Za-z가-힣]", text)) or 1
    cjk = re.search(r"[぀-ヿ一-鿿]", text)       # 한자 · 가나가 섞이면 NG
    sentences = [s for s in re.split(r"(?<=[.!?。])\s+", text) if s.strip()]
    return [
        ("한국어", hangul / letters >= 0.8 and not cjk),
        (f"{VLM_MAX_SENTENCES}문장 이내", len(sentences) <= VLM_MAX_SENTENCES),
        ("장애물 표기", bool(re.search(r"장애물 (있음|없음)\.?$", text))),
    ]


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


# 방향어 ― '위' 는 뒤에 띄어쓰기 · '로' · '쪽' 이 올 때만 방향이다 ('위치' · '위험' · '위에' 는 아님)
_DIRECTION_WORD_RE = re.compile(r"오른쪽|왼쪽|위(?=\s|로|쪽|$)|아래|\b(?:up|down|left|right)\b", re.I)
_WORD_TO_DIRECTION = {"오른쪽": "right", "왼쪽": "left", "아래": "down"}
_STEPS_RE = re.compile(r"(\d+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*칸")
_KOREAN_NUMBER = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5,
                  "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
_QUESTION_RE = re.compile(r"\[사용자 질문\] (.*)")
# [개선 ④] '왼쪽 말고' 처럼 부정된 방향어 ― 방향어 검사 전에 지운다
_NEGATED_RE = re.compile(r"(오른쪽|왼쪽|위|아래)\s*(?:말고|아니고|대신)")
# [개선 ②] 제안(guess)에 대한 수락 답
_CONFIRM_RE = re.compile(r"^\s*(?:응|어|네|예|그래|좋아|맞아|ㅇㅇ|오케이|ok|yes)(?:요)?\s*[.!~]*\s*$", re.I)
# [개선 ⑤] 연속 명령의 연결어 ― ',' 는 넣지 않는다 ('왼쪽으로, 5칸 이동.' 이 쪼개진다)
_SPLIT_RE = re.compile(r"\s*(?:가고|하고|그리고|다음에)\s*")
# 연결어 없는 연속 명령은 각 동작에 방향과 칸 수가 명시된 경우에만 인식한다.
_COUNTED_MOVE = rf"(?:오른쪽|왼쪽|위(?:쪽)?|아래(?:쪽)?)(?:으로|로)?\s+{_STEPS_RE.pattern}"
_COUNTED_MOVE_RE = re.compile(_COUNTED_MOVE)
_COMPACT_SEQUENCE_RE = re.compile(rf"{_COUNTED_MOVE}(?:[\s,]+{_COUNTED_MOVE})+[.!]?")


def said_direction(text: str):
    """질문에 적힌 방향어 → up / down / left / right. 없으면 None."""
    text = _NEGATED_RE.sub("", text)                   # [개선 ④] '왼쪽 말고' 삭제
    match = _DIRECTION_WORD_RE.search(text)
    if not match:
        return None
    word = match.group(0).lower()
    return _WORD_TO_DIRECTION.get(word, "up" if word.startswith("위") else word)


def negated_directions(text: str) -> set:
    """[개선 ④] '왼쪽 말고' 처럼 부정된 방향 → {"left"}. 이 방향은 제안(guess)으로도 쓰지 않는다."""
    return {DIRECTION_ALIASES[m.group(1)]
            for m in _NEGATED_RE.finditer(text)}


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


def ask_for_direction(steps: int, guess=None) -> dict:
    """[R3] 방향만 모른다 → 되묻는다. 이미 아는 칸 수는 args 에 기억해 둔다.
    [개선 ②] LLM 이 추측한 방향은 버리지 않고 args.guess 에 담아 제안만 한다 (바로 움직이지 않는다)."""
    args = {"steps": steps}
    if guess in DIRECTIONS:
        args["guess"] = guess
        message = f"{DIRECTION_TO[guess]} {steps}칸 갈까요? 맞으면 '응', 아니면 방향을 말해 주세요."
    else:
        message = f"어느 쪽으로 {steps}칸 갈까요? 방향을 말하거나 손으로 가리켜 주세요."
    return {"tool": "ask", "args": args, "message": message}


def move_with_steps(direction: str, steps: int) -> dict:
    """코드가 확정한 이동 ― 안내 문장도 확정한 인자에 맞춰 다시 쓴다."""
    return {"tool": "move", "args": {"direction": direction, "steps": steps},
            "message": f"{DIRECTION_TO[direction]} {steps}칸 이동합니다."}


def _pending_ask_args(history: list) -> dict:
    """직전 답이 ask 였다면 그 args. 아니면 {}."""
    for turn in reversed(history):
        if turn["role"] == "assistant":
            data = extract_json(turn["content"]) or {}
            args = data.get("args") if isinstance(data.get("args"), dict) else {}
            return args if data.get("tool") == "ask" else {}
    return {}


def pending_steps(history: list):
    """[R5] 직전 답이 ask 였다면 그때 기억해 둔 칸 수. 아니면 None."""
    args = _pending_ask_args(history)
    return to_steps(args["steps"]) if "steps" in args else None


def pending_guess(history: list):
    """[개선 ②] 직전 ask 가 제안한 방향(args.guess). 없으면 None."""
    guess = _pending_ask_args(history).get("guess")
    return guess if guess in DIRECTIONS else None


def split_moves(prompt: str) -> list:
    """[개선 ⑤] 연결어가 있거나 방향과 칸 수를 연달아 쓴 명령을 순서대로 나눈다."""
    if _COMPACT_SEQUENCE_RE.fullmatch(prompt.strip()):
        return [{"direction": said_direction(move.group()), "steps": said_steps(move.group())}
                for move in _COUNTED_MOVE_RE.finditer(prompt)]
    parts = _SPLIT_RE.split(prompt)
    return [{"direction": said_direction(p), "steps": said_steps(p) or 1}
            for p in parts if said_direction(p)]


def apply_rules(call: dict, prompt: str, history: list, gesture_direction: str) -> dict:
    """[R3][R5] LLM 이 고른 도구를, 입력에 실제로 적힌 근거로 확정한다."""
    moves = split_moves(prompt)
    if len(moves) > 1:                                                     # [개선 ⑤] 연속 명령
        call = move_with_steps(**moves[0])
        call["then"] = moves[1:]                                           # 나머지 이동
        call["message"] = ", ".join(f"{DIRECTION_TO[m['direction']]} {m['steps']}칸"
                                    for m in moves) + " 이동합니다."
        return call
    direction = resolve_direction(prompt, history, gesture_direction)
    steps = said_steps(prompt)
    pending = pending_steps(history)
    guess = pending_guess(history)
    if direction is None and guess and _CONFIRM_RE.match(prompt):          # [개선 ②] 제안에 '응' → 그 방향으로
        return move_with_steps(guess, pending or 1)
    if call["tool"] == "move":
        if not has_direction_evidence(prompt, history, gesture_direction):
            llm_guess = call["args"]["direction"]                          # [개선 ②] LLM 추측은 제안으로
            if llm_guess in negated_directions(prompt):                    # [개선 ④] 부정된 방향은 제안하지 않는다
                llm_guess = None
            return ask_for_direction(steps or call["args"]["steps"], llm_guess)  # [R3] 근거 없는 이동
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


class DeviceError(Exception):
    """라즈베리파이에 연결할 수 없거나 약속과 다른 응답을 받았다."""


def device_url(ip: str, path: str) -> str:
    """기기 주소 → http://{ip}:8080{path}. IP · 호스트 이름 형식이 아니면 DeviceError."""
    if not _DEVICE_HOST_RE.match(ip):
        raise DeviceError(f"잘못된 주소 {ip!r}")
    return f"http://{ip}:{DEVICE_PORT}{path}"


async def device_get(ip: str, path: str, read_timeout: float, params=None) -> httpx.Response:
    """기기에 GET 한 번. 연결 실패 · 200 이 아니면 DeviceError."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(
                DEVICE_CONNECT_TIMEOUT, read=read_timeout)) as client:
            response = await client.get(device_url(ip, path), params=params)
    except httpx.HTTPError as exc:
        raise DeviceError(type(exc).__name__) from exc
    if response.status_code != 200:
        raise DeviceError(f"status {response.status_code}")
    return response


def scene_summary(yolo_summary: str, vlm_description: str) -> str:
    """LLM 답변을 그대로 쓸 수 없을 때 ― YOLO · VLM 결과를 그대로 이어 붙인다."""
    yolo = yolo_summary.strip()
    parts = [f"감지된 물체: {yolo}." if yolo else "", vlm_description.strip()]
    return " ".join(p for p in parts if p) or NO_SCENE_MESSAGE


def device_message(call: dict, yolo_summary: str, vlm_description: str) -> str:
    """[R10] 기기 탭(ip 있음)은 시뮬레이터가 아니라 실물 기기(OLED · LED)로 출력한다.
    '오른쪽으로 3칸 이동합니다.' 의 칸 수는 격자 시뮬레이터에서만 뜻이 있으므로, 답변은 방향만으로 쓴다.
    tool · args · then 은 apply_rules 가 정한 그대로 둔다 ― 형식은 로컬 PC 탭과 같고 문구만 다르다."""
    tool, args = call["tool"], call["args"]
    if tool == "move":
        moves = [args, *call.get("then", [])]
        if len(moves) > 1:                                   # [개선 ⑤] 연속 이동 → 순서대로 이동합니다
            return " → ".join(DIRECTION_KO[m["direction"]] for m in moves) + " 순서로 이동합니다."
        return f"{DIRECTION_TO[args['direction']]} 이동합니다."
    if tool == "ask":
        guess = args.get("guess")
        if guess in DIRECTIONS:                              # [개선 ②] 제안도 칸 수 없이
            return f"{DIRECTION_TO[guess]} 갈까요? 맞으면 '응', 아니면 방향을 말해 주세요."
        return ASK_MESSAGE
    message = call["message"]                                # describe ― 장면 설명은 그대로
    if message == FALLBACK_MESSAGE or _GRID_TALK_RE.search(message):
        return scene_summary(yolo_summary, vlm_description)
    return message


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

    inputs = (prompt,
              str(body.get("yolo_summary", "")),
              str(body.get("vlm_description", "")),
              _read_gesture(body.get("gesture_direction", "unknown")),
              _read_history(body.get("history")))
    ip = str(body.get("ip", "")).strip()
    to_device = bool(ip)          # [R10] 출력 대상 ― ip 가 있으면 기기 탭(OLED · LED), 없으면 시뮬레이터
    t0 = time.time()
    try:                          # 기기 탭 질문도 아직 PC LLM 이 도구를 고른다 (기기 LLM 은 PJT02)
        call, user_content = await run_in_threadpool(decide_tool, *inputs)
    except Exception as exc:
        _log("llm", t0, f"실패 ({type(exc).__name__})")
        return JSONResponse({"error": "llm_failed"}, status_code=500)
    if to_device:                 # [R10] 기기 탭 답변은 칸 수 없이 방향만
        call["message"] = device_message(call, inputs[1], inputs[2])
    where = f"[{ip}] " if to_device else ""   # 기기 탭 요청 ― [1.2.3.4]
    _log("tool", t0, f"{where}"
                     f"Q. {prompt} → {call['tool']} {call['args'] or ''} "
                     f"{call.get('then', '')}  {call['message']}")
    return {**call,
            "need_more_info": call["tool"] == "ask",     # [R4]
            "user_content": user_content}


# ---------------------------------------------------------------------------
# 라즈베리파이 중계 (3회차) ― PC 는 기기 요청을 중계만 하고 상태를 갖지 않는다 (R7)
# ---------------------------------------------------------------------------
@app.get("/api/camera-stream")
async def camera_stream(ip: str = ""):
    """[A6] 기기 MJPEG(D1)를 재인코딩 없이 그대로 중계한다."""
    ip = ip.strip()
    if not ip:
        return JSONResponse({"error": "invalid_request"}, status_code=400)
    client = httpx.AsyncClient(timeout=httpx.Timeout(
        DEVICE_CONNECT_TIMEOUT, read=STREAM_READ_TIMEOUT))
    try:
        upstream = await client.send(
            client.build_request("GET", device_url(ip, DEVICE_STREAM_PATH)), stream=True)
    except (httpx.HTTPError, DeviceError):
        await client.aclose()
        return JSONResponse({"error": "camera_unreachable", "ip": ip}, status_code=502)
    if upstream.status_code != 200:
        await upstream.aclose()
        await client.aclose()
        return JSONResponse({"error": "camera_unreachable", "ip": ip}, status_code=502)

    async def relay():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        except httpx.HTTPError:
            # [F105] 읽기 타임아웃 = 조용한 단절 → 스트림을 끝내면 화면이 다시 연결한다
            print(f"[cam ] 스트림 끊김 → 종료  {ip}", flush=True)
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(relay(), media_type=upstream.headers.get(
        "content-type", "multipart/x-mixed-replace; boundary=FRAME"))


async def _read_signal_request(request: Request, mapping: dict):
    """{ip, direction} → (ip, 매핑값, None). 틀리면 (None, None, 400 응답)."""
    try:
        body = await request.json()
    except Exception:
        return None, None, JSONResponse({"error": "invalid_json"}, status_code=400)
    if not isinstance(body, dict):
        return None, None, JSONResponse({"error": "invalid_json"}, status_code=400)
    ip = str(body.get("ip", "")).strip()
    value = mapping.get(str(body.get("direction", "")).strip().lower())
    if not ip or value is None:
        return None, None, JSONResponse({"error": "invalid_request"}, status_code=400)
    return ip, value, None


@app.post("/api/robot-signal")
async def robot_signal(request: Request):
    """[A7] {ip, direction} → 기기 LED 3회 점멸(D2). [R8] right → 17, left → 27, up · down 은 400."""
    ip, pin, error = await _read_signal_request(request, DIRECTION_GPIO_PIN)
    if error:
        return error
    t0 = time.time()
    try:
        await device_get(ip, DEVICE_GPIO_PATH, DEVICE_SIGNAL_TIMEOUT, {"pin": pin})
    except DeviceError as exc:
        _log("led", t0, f"실패 ({exc})  {ip}")
        return JSONResponse({"error": "device_unreachable", "ip": ip}, status_code=502)
    _log("led", t0, f"pin {pin}  {ip}")
    return {"ok": True}


@app.post("/api/oled-display")
async def oled_display(request: Request):
    """[A8 · R8] {ip, direction} → 기기 OLED 에 LEFT · RIGHT · UP · DOWN 표시(D3)."""
    ip, text, error = await _read_signal_request(request, DIRECTION_OLED_TEXT)
    if error:
        return error
    t0 = time.time()
    try:
        await device_get(ip, DEVICE_OLED_PATH, DEVICE_SIGNAL_TIMEOUT, {"text": text})
    except DeviceError as exc:
        _log("oled", t0, f"실패 ({exc})  {ip}")
        return JSONResponse({"error": "device_unreachable", "ip": ip}, status_code=502)
    _log("oled", t0, f"{text}  {ip}")
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
