# -*- coding: utf-8 -*-
"""[page 25] D5 단독 확인 ― 기기 LLM(/llm-infer)에 PC 서버를 거치지 않고 직접 묻는다.

강의자료 25쪽의 curl 을 한 번에 돌린다. 표준 라이브러리만 써서 PC 에서도, 라즈베리파이에서도 된다.
  ① '앞에 뭐가 있어?'     → describe
  ② '오른쪽으로 2칸 가'   → move(right, 2)
  ③ '저쪽으로 가'         → ask (또는 move ― 소형 모델은 틀릴 수 있다. PC 의 R3 가 ask 로 바꾼다)
  ④ user_content 없음     → 400 empty_user_content
  ⑤ JSON 아님             → 400 invalid_json

첫 요청은 모델 로딩 때문에 1분 가까이 걸린다 (Pi 5 실측 44 ~ 54초, 이후 7.8 ~ 11.5초).
500 inference_failed 는 모델 파일 이름을 잠시 바꾸고 이 스크립트를 다시 돌려 직접 확인한다 ―
서버는 죽지 않고 다음 요청에 계속 응답해야 한다.

실행:
    python D5_단독확인.py --device 192.168.0.10       # PC 에서
    python3 D5_단독확인.py --device localhost          # 라즈베리파이에서
"""
import argparse
import json
import time
import urllib.error
import urllib.request

DEVICE_PORT = 8080

# PC 서버(build_user_content)가 만드는 것과 같은 형식 ― D5 는 user_content 를 직접 만들지 않는다 (R9)
YOLO_SUMMARY = "person 3개, bus 1개"
VLM_DESCRIPTION = "버스 앞에 두 명의 사람이 서 있습니다, 장애물 없음."

# (번호, 질문, 기대 도구들)
CASES = [
    ("①", "앞에 뭐가 있어?", ("describe",)),
    ("②", "오른쪽으로 2칸 가", ("move",)),
    ("③", "저쪽으로 가", ("ask", "move")),       # move 면 PC 의 R3 가 ask 로 바꾼다
]


def user_content(prompt):
    return (f"[YOLO 객체 인식] {YOLO_SUMMARY}\n"
            f"[VLM 장면 설명] {VLM_DESCRIPTION}\n"
            f"[손 제스처] 가리키는 방향: 손 없음\n\n"
            f"[사용자 질문] {prompt}")


def post(url, body: bytes, timeout):
    """POST 한 번 → (status, dict). 연결 실패면 (None, {})."""
    request = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:          # 400 · 500 도 본문(JSON)을 읽는다
        try:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        except ValueError:
            return exc.code, {}
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"  연결 실패: {exc} ― 기기 서버가 떠 있는지, IP · 8080 포트를 확인한다")
        return None, {}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", required=True, metavar="IP", help="라즈베리파이 IP (Pi 에서는 localhost)")
    parser.add_argument("--timeout", type=float, default=180, help="첫 요청은 모델 로딩까지 1분 가까이")
    args = parser.parse_args()
    url = f"http://{args.device}:{DEVICE_PORT}/llm-infer"
    print(f"D5 {url}\n")

    passed = 0
    for no, prompt, expected in CASES:
        t0 = time.perf_counter()
        status, data = post(url, json.dumps({"user_content": user_content(prompt), "history": []},
                                            ensure_ascii=False).encode("utf-8"), args.timeout)
        ok = status == 200 and data.get("tool") in expected and isinstance(data.get("args"), dict)
        passed += ok
        print(f"{'O' if ok else 'X'}  {no} {time.perf_counter() - t0:5.1f}s  {prompt}")
        print(f"       → {status} {data.get('tool')} {data.get('args', '')}  {data.get('message', data)!r}")
        if no == "③" and data.get("tool") == "move":
            print("       (소형 모델이 방향을 추측했다 ― 방향 근거가 없으므로 PC 의 R3 가 ask 로 바꾸고 guess 로 남긴다)")

    for no, title, body, code in (("④", "user_content 없음", b'{"history": []}', "empty_user_content"),
                                  ("⑤", "JSON 아님", b"{broken", "invalid_json")):
        status, data = post(url, body, 10)
        ok = status == 400 and data.get("error") == code
        passed += ok
        print(f"{'O' if ok else 'X'}  {no}         {title}\n       → {status} {data.get('error')}")

    total = len(CASES) + 2
    print(f"\n{passed}/{total}" + ("" if passed == total else "  ― X 항목을 기기 서버 로그(LLM: raw=...)와 대조한다"))


if __name__ == "__main__":
    main()
