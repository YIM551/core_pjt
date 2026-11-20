# -*- coding: utf-8 -*-
"""[심화 F205] 음성 인식 보정 전 · 후 정확도 비교 ― 같은 문장을 여러 번 녹음해 whisper 결과를 비교한다.

라즈베리파이에서 실행한다 (camera_server.py 와 같은 arecord 장치 · whisper.cpp 를 쓴다).
  보정 전 : whisper-cli 그대로
  보정 후 : --prompt 초기 프롬프트(WHISPER_PROMPT) + 보정 사전(VOICE_CORRECTIONS) ― camera_server.py 와 같은 값
녹음마다 두 결과에서 PC 규칙(방향어 · 칸 수)이 읽어 내는 값이 정답과 같은지 센다.
문장 전체가 아니라 '방향 · 칸 수' 를 맞혔는지 보는 이유 ― 도구 인자는 그 두 값으로만 정해진다 (R2 · R3).

실행:
    python3 보정_전후_비교.py --target "오른쪽으로 두 칸 가" --count 20     # Enter → 3초 녹음, 20회
    python3 보정_전후_비교.py --target "오른쪽으로 두 칸 가" --wav-dir rec  # 이미 녹음한 wav 로 다시 비교
주의: camera_server.py 가 돌고 있어도 된다 (PTT 를 누르지 않으면 마이크를 쓰지 않는다).
"""
import argparse
import re
import subprocess
from pathlib import Path

ALSA_DEVICE = "plughw:CARD=sndrpigooglevoi,DEV=0"          # camera_server.py:VOICE_ALSA_DEVICE
SAMPLE_RATE = 16000
WHISPER_DIR = Path.home() / "whisper.cpp"
WHISPER_BIN = WHISPER_DIR / "build" / "bin" / "whisper-cli"
WHISPER_MODEL = WHISPER_DIR / "models" / "ggml-base.bin"

# camera_server.py 의 [F205] 상수와 같은 값 ― 저쪽을 고치면 여기도 고친다
WHISPER_PROMPT = ("오른쪽, 왼쪽, 위, 아래, 한 칸, 두 칸, 세 칸, 네 칸, 다섯 칸, 여섯 칸, "
                  "일곱 칸, 여덟 칸, 아홉 칸, 열 칸, 가, 이동해, 응, 앞에 뭐가 있어?")
VOICE_CORRECTIONS = {"오는 쪽": "오른쪽", "오른 쪽": "오른쪽", "오른족": "오른쪽", "왼 쪽": "왼쪽",
                     "웬쪽": "왼쪽", "왼족": "왼쪽", "아레": "아래", "위쪽으로": "위로"}
_VOICE_STEPS_FIX_RE = re.compile(r"(\d+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*간(?![가-힣])")

# PC 서버(main.py)의 방향어 · 칸 수 규칙과 같다
_DIRECTION_WORD_RE = re.compile(r"오른쪽|왼쪽|위(?=\s|로|쪽|$)|아래")
_STEPS_RE = re.compile(r"(\d+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*칸")
_KOREAN_NUMBER = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}


def read_intent(text):
    """문장 → (방향어, 칸 수). PC 규칙이 도구 인자를 정할 때 보는 두 값."""
    direction = _DIRECTION_WORD_RE.search(text)
    steps = _STEPS_RE.search(text)
    return (direction.group(0) if direction else None,
            int(_KOREAN_NUMBER.get(steps.group(1), steps.group(1))) if steps else None)


def whisper(wav, prompt=None):
    command = [str(WHISPER_BIN), "-m", str(WHISPER_MODEL), "-l", "ko", "-nt", "-f", str(wav)]
    if prompt:
        command[-2:-2] = ["--prompt", prompt]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    lines = [ln.strip() for ln in result.stdout.splitlines()
             if ln.strip() and not (ln.strip()[0] in "[(" and ln.strip()[-1] in "])")]   # 비발화 태그 제거
    return " ".join(" ".join(lines).split())


def correct(text):
    for wrong, right in VOICE_CORRECTIONS.items():
        text = text.replace(wrong, right)
    return _VOICE_STEPS_FIX_RE.sub(r"\1 칸", text)


def record_all(folder, count, seconds, target):
    folder.mkdir(exist_ok=True)
    for i in range(1, count + 1):
        input(f"[{i}/{count}] Enter 를 누르고 '{target}' 라고 말하세요 ({seconds}초)…")
        subprocess.run(["arecord", "-q", "-D", ALSA_DEVICE, "-f", "S16_LE", "-r", str(SAMPLE_RATE),
                        "-c", "1", "-d", str(seconds), str(folder / f"{i:02d}.wav")], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", required=True, help="녹음할 문장 (정답)")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--seconds", type=int, default=3)
    parser.add_argument("--wav-dir", default="f205_rec", help="녹음 파일 폴더 (있으면 녹음을 건너뛴다)")
    args = parser.parse_args()
    if not WHISPER_BIN.exists() or not WHISPER_MODEL.exists():
        raise SystemExit(f"whisper 바이너리/모델이 없다: {WHISPER_BIN}, {WHISPER_MODEL} (2일차 page58 whisper_빌드.sh)")

    folder = Path(args.wav_dir)
    if not sorted(folder.glob("*.wav")):
        record_all(folder, args.count, args.seconds, args.target)
    answer = read_intent(args.target)
    print(f"\n정답 {args.target!r} → 방향 · 칸 수 {answer}\n")

    before_ok = after_ok = 0
    wavs = sorted(folder.glob("*.wav"))
    for wav in wavs:
        before = whisper(wav)
        after = correct(whisper(wav, WHISPER_PROMPT))
        b, a = read_intent(before) == answer, read_intent(after) == answer
        before_ok, after_ok = before_ok + b, after_ok + a
        print(f"{wav.name}  전 {'O' if b else 'X'} {before!r:32}  후 {'O' if a else 'X'} {after!r}")

    print("\n" + "-" * 60)
    print(f"방향 · 칸 수 정확도  보정 전 {before_ok}/{len(wavs)}  →  보정 후 {after_ok}/{len(wavs)}")
    print("틀린 표현이 반복되면 VOICE_CORRECTIONS 에 더하고(camera_server.py 도 함께) 다시 돌린다")


if __name__ == "__main__":
    main()
