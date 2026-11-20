"""타이핑 명령으로 OLED 네 방향과 좌우 LED 3회 점멸을 확인한다.

PC 대시보드와 Pi 서버를 켠 뒤 실행한다.
    python OLED_LED_육안_검증.py --device 192.168.0.10
"""
import argparse
import sys
import time

import httpx

from API_검증 import OLED_TEXT, json_object


DIRECTIONS = ("left", "up", "right", "down")
PROMPT = "왼쪽으로 1칸 가고 위로 1칸 가고 오른쪽으로 1칸 가고 아래로 1칸 가"


def observe(client, ip):
    answer = client.post("/api/llm-answer", json={
        "source": "device", "ip": ip, "prompt": PROMPT,
        "history": [], "gesture_direction": "unknown",
    })
    answer.raise_for_status()
    data = json_object(answer)
    following = data.get("then")
    moves = [data.get("args"), *following] if isinstance(following, list) else []
    expected = [{"direction": direction, "steps": 1} for direction in DIRECTIONS]
    if data.get("tool") != "move" or moves != expected:
        raise ValueError(f"이동 명령이 예상과 다릅니다. tool={data.get('tool')!r}, moves={moves!r}")

    print("예상 OLED 순서: LEFT → UP → RIGHT → DOWN. 각 방향을 8초 이상 표시합니다.")
    input("OLED와 좌우 LED가 보이면 Enter를 누르세요. ")
    for move in moves:
        direction = move["direction"]
        signal = {"ip": ip, "direction": direction}
        paths = ["/api/oled-display"]
        if direction in ("left", "right"):
            paths.append("/api/robot-signal")
        led = {"left": "왼쪽 LED 3회", "right": "오른쪽 LED 3회"}.get(direction, "LED 점멸 없음")
        print(f"지금 확인할 출력 · OLED {OLED_TEXT[direction]} · {led}", flush=True)
        for path in paths:
            result = client.post(path, json=signal)
            result.raise_for_status()
            if json_object(result).get("ok") is not True:
                raise ValueError(f"{direction} {path} 응답에 ok=true가 없습니다.")
        time.sleep(8)
    print("OLED 요청 4건과 LED 요청 2건이 수락됐습니다. 실물에서 관찰한 결과를 별도로 기록하세요.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, metavar="IP", help="라즈베리파이 IP")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="PC 대시보드 주소")
    args = parser.parse_args()
    try:
        with httpx.Client(base_url=args.url, timeout=180, trust_env=False) as client:
            observe(client, args.device)
    except EOFError:
        sys.exit("Enter를 받을 수 있는 터미널에서 실행하세요.")
    except (httpx.HTTPError, ValueError) as exc:
        sys.exit(f"검증 중단 · {exc}")


if __name__ == "__main__":
    main()
