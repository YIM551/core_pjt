# 심화 ― 음성 인식 품질 개선

> 강의자료 **85쪽** (실습 6-2 · 심화 F205 안내)  ·  `AI코어프로젝트_3회차_DAY2_r2.pptx`  ·  실행 위치: **라즈베리파이**

whisper 초기 프롬프트 · 보정 사전 · 짧은 발화 필터로 방향어 · 칸 수 인식률을 높이고, 보정 전 · 후를 숫자로 비교한다

## 무엇을 하는가

- `camera_server.py` = 3일차 page17 기기 서버 + F205 (3회차 기기 서버 완성본)
- `WHISPER_PROMPT` ― whisper `--prompt` 로 방향어 · 칸 수 어휘(오른쪽 … 열 칸, 응)를 미리 보여 준다
- `VOICE_CORRECTIONS` ― '오는 쪽' → '오른쪽', '웬쪽' → '왼쪽', '세 간' → '세 칸'
- `보정_전후_비교.py` ― 같은 문장을 20회 녹음해, PC 규칙이 읽는 방향 · 칸 수가 맞았는지 보정 전 · 후로 센다
- small 모델(약 4배 느림)로 바꾸기 전에 이것부터 시도한다

## 실행

```bash
scp camera_server.py 보정_전후_비교.py pi@<PiIP>:~/
python3 보정_전후_비교.py --target "오른쪽으로 두 칸 가" --count 20
python3 보정_전후_비교.py --target "오른쪽으로 두 칸 가" --wav-dir f205_rec   # 녹음 재사용
~/venv/bin/python3 ~/camera_server.py
```

## 확인 포인트

- 보정 후 정확도가 보정 전보다 같거나 높다
- 자주 틀리는 표현이 보이면 `VOICE_CORRECTIONS` 에 더한다 (camera_server.py · 보정_전후_비교.py 양쪽)
- 인식이 바뀌어도 '응'(한 글자)은 그대로 통과한다

## 이 폴더의 파일

- `camera_server.py`
- `보정_전후_비교.py`

---
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
