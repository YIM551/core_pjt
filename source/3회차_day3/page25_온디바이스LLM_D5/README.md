# page25 ― 온디바이스 LLM D5

> 강의자료 **9쪽** (설치 시작) · **21쪽** (실습 1-1 설치 확인) · **22 ~ 23쪽** (D5 코드) · **24쪽** (응답 시간) / **25쪽** (실습 1-2) · **26쪽** (서버 로그)  ·  `AI코어프로젝트_3회차_DAY3_r2.pptx`  ·  실행 위치: **라즈베리파이 (venv 파이썬) · 확인은 PC 에서도**

기기 서버에 [D5] /llm-infer 를 더해 Qwen3-1.7B 가 기기 안에서 move · describe · ask 를 고른다

## 무엇을 하는가

- ① JSON 스키마 강제(GBNF) ― tool 은 move|describe|ask, direction 은 네 방향. 1.7B 가 필드를 빠뜨리는 일이 구조적으로 없어진다
- ② 사고 모드 끄기 ― 마지막 user 메시지에만 `/no_think` (PC 의 ask_llm 과 같다)
- temperature 0 ― 같은 입력에 같은 도구
- 모델은 첫 요청 때 한 번 로드한다. 강의의 Pi 5 측정값은 첫 요청 44~54초, 이후 7.8~11.5초다. 프로젝트에서 측정한 기기 버전과 조건은 [모델별 추론 시간](../../../README_PJT03.md#모델별-추론-시간)에 기록했다.
- 제출용 D5는 도구와 인자를 선택하고 `message`를 빈 문자열로 제한한다. PC가 YOLO·VLM 인식 결과를 사용해 장면 설명을 작성한다.
- `D5_단독확인.py` ― 23쪽의 curl 다섯 줄을 한 번에 (표준 라이브러리만 써서 Pi 에서도 된다)

## 실행

```bash
# 라즈베리파이 ― 설치 (../명령어_모음_DAY3.md 9쪽 참고, 6 ~ 20분)
~/venv/bin/pip install "llama-cpp-python==0.3.35"
curl -fL -o ~/models/Qwen3-1.7B-Q4_K_M.gguf https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf
~/venv/bin/python3 ~/camera_server.py

# PC 또는 라즈베리파이
python D5_단독확인.py --device <PiIP>
```

## 확인 포인트

- ① describe · ② move(right, 2) · ④ 400 empty_user_content · ⑤ 400 invalid_json
- ③ '저쪽으로 가' 는 ask 또는 move ― 소형 모델은 틀릴 수 있다. 그래서 PC 가 규칙을 다시 적용한다 (R9, page30)
- 모델 파일 이름을 잠시 바꾸고 보내면 500 inference_failed, 서버는 계속 살아 있다
- 시스템 python3 로 띄우면 /llm-infer 가 매번 실패한다 (llama_cpp 는 venv 에만 있다)

## 이 폴더의 파일

- `camera_server.py`
- `D5_단독확인.py`
- `기대출력.txt` ― 라즈베리파이 실물에서 나와야 하는 출력 형식 (코드의 출력 문구 · 강의자료 기준, 실측 아님)

---
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
