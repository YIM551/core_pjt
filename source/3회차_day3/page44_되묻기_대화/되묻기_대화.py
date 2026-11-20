# -*- coding: utf-8 -*-
"""[page 44] F302 음성 되묻기 대화 ― ask 에 음성으로 답해 대화를 이어 간다.

강의자료 44쪽의 대화 세 갈래를 기기 탭과 똑같이 보낸다. history 는 화면(index.html)처럼 이 스크립트가 들고 있다가
매 요청에 실어 보낸다 (R7 ― 서버 · 기기는 대화 상태를 갖지 않는다).
  ① 음성 '저쪽으로 2칸 가' → ask → 음성 '왼쪽'         → move(left, 2)  · OLED LEFT
  ② 음성 '저쪽으로 2칸 가' → 제안 → 음성 '응'          → move(guess, 2) · OLED (제안 방향)
  ③ 음성 '저쪽으로 2칸 가' → ask → 기기 탭 타이핑 '위'  → move(up, 2)    · OLED UP   (음성 · 텍스트 섞기)

제안(args.guess)은 기기 LLM 이 방향을 추측했을 때만 나온다. 안 나오면 ② 는 건너뛴다 ―
'어느 쪽으로 갈까요?' 에 방향으로 답하는 경로(①)만 확인해도 된다. 규칙 함수 자체는 page56 최종 검증이 확인한다.

서버 두 개를 먼저 띄운다 (라즈베리파이 camera_server.py, PC ../page30_음성경로_통합).

실행:
    python 되묻기_대화.py --device 192.168.0.10            # 같은 문장을 source=voice 로 보낸다
    python 되묻기_대화.py --device 192.168.0.10 --ptt      # 음성 턴은 PTT 로 직접 말한다
"""
import argparse
import json
import time

import httpx

YOLO_SUMMARY = "person 3개, bus 1개"
VLM_DESCRIPTION = "버스 앞에 두 명의 사람이 서 있습니다, 장애물 없음."
OLED_TEXT = {"left": "LEFT", "right": "RIGHT", "up": "UP", "down": "DOWN"}

# (제목, 1턴 질문, 2턴 답 ― None 이면 제안 방향에 '응', 2턴 source, 기대 방향 ― None 이면 제안 방향)
DIALOGUES = [
    ("① ask → 방향으로 답", "저쪽으로 2칸 가", "왼쪽", "voice", "left"),
    ("② 제안 → '응'", "저쪽으로 2칸 가", "응", "voice", None),
    ("③ 음성 ask → 타이핑 '위'", "저쪽으로 2칸 가", "위", "device", "up"),
]


class DeviceTab:
    """기기 탭 하나 ― history 를 들고 있다가 매 요청에 싣는다. 최종 답(move · describe)이 나오면 비운다."""

    def __init__(self, client, ip, ptt):
        self.client, self.ip, self.ptt = client, ip, ptt
        self.history = []

    def send(self, prompt, source):
        if source == "voice" and self.ptt:
            prompt = wait_voice(self.client, self.ip, prompt) or prompt
        t0 = time.perf_counter()
        r = self.client.post("/api/llm-answer", json={
            "prompt": prompt, "yolo_summary": YOLO_SUMMARY, "vlm_description": VLM_DESCRIPTION,
            "gesture_direction": "none", "history": self.history, "source": source, "ip": self.ip})
        sec = time.perf_counter() - t0
        if r.status_code != 200:                 # [R6] 오류 때 화면은 history 를 지우지 않는다
            print(f"    [{source:6}] {prompt!r} → {r.status_code} {r.json().get('error')}  (history {len(self.history)}개 유지)")
            return {}
        data = r.json()
        if data["tool"] == "ask":                # 되묻기 ― 이번 턴을 history 에 남긴다
            self.history += [{"role": "user", "content": data["user_content"]},
                             {"role": "assistant", "content": json.dumps(
                                 {k: data[k] for k in ("tool", "args", "message")}, ensure_ascii=False)}]
        else:                                    # 최종 답 ― 다음 질문과 섞이지 않게 비운다
            self.history = []
        oled = self.output(data)
        print(f"    [{source:6}] {prompt!r} → {sec:4.1f}s  {data['tool']} {data['args']}"
              f"{'  OLED ' + ' → '.join(oled) if oled else ''}  ·  {data['message']!r}  (history {len(self.history)}개)")
        return data

    def output(self, data):
        """화면처럼 move 면 A8(OLED) · A7(LED, 좌우만)을 호출한다."""
        if data.get("tool") != "move":
            return []
        shown = []
        for move in [data["args"]] + data.get("then", []):
            self.client.post("/api/oled-display", json={"ip": self.ip, "direction": move["direction"]})
            if move["direction"] in ("left", "right"):
                self.client.post("/api/robot-signal", json={"ip": self.ip, "direction": move["direction"]})
            shown.append(OLED_TEXT[move["direction"]])
        return shown


def wait_voice(client, ip, prompt, timeout=30):
    """PTT 로 말한 새 발화를 A9 로 받는다 (화면의 1초 폴링과 같다). 시간 안에 없으면 None."""
    seq = client.get("/api/voice-poll", params={"ip": ip}).json().get("seq", 0)
    print(f"    🎤 PTT 를 누른 채 '{prompt}' 라고 말하고 떼세요…", flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(1)
        data = client.get("/api/voice-poll", params={"ip": ip}).json()
        if data.get("seq", 0) > seq and data.get("text"):
            return data["text"]
    print("    음성 없음 ― 같은 문장을 그대로 보낸다")
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", required=True, metavar="IP", help="라즈베리파이 IP")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="PC 대시보드 서버")
    parser.add_argument("--ptt", action="store_true", help="음성 턴은 PTT 로 직접 말한다")
    args = parser.parse_args()

    passed, total = 0, 0
    with httpx.Client(base_url=args.url, timeout=200) as client:
        for title, first, answer, source, expected in DIALOGUES:
            print(f"\n■ {title}")
            tab = DeviceTab(client, args.device, args.ptt)
            data = tab.send(first, "voice")
            if data.get("tool") != "ask":
                print("    1턴이 ask 가 아니다 ― R3 (방향 근거 없음 → ask) 확인")
                total += 1
                continue
            guess = data["args"].get("guess")
            if expected is None:                 # ② 제안이 있어야 '응' 이 뜻을 갖는다
                if guess is None:
                    print("    제안(guess) 없음 ― 이번엔 '어느 쪽으로 갈까요?' 로 끝났다. ①만 확인해도 된다 (건너뜀)")
                    continue
                expected = guess
            data = tab.send(answer, source)
            ok = data.get("tool") == "move" and data.get("args") == {"direction": expected, "steps": 2} \
                and tab.history == []
            passed, total = passed + ok, total + 1
            print(f"    {'O' if ok else 'X'}  기대 move({expected}, 2) · OLED {OLED_TEXT[expected]} · history 비움")

    print("\n" + "-" * 60)
    print(f"되묻기 대화 {passed}/{total}")


if __name__ == "__main__":
    main()
