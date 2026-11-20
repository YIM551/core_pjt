# page30 ― 음성 경로 통합 (A5 source 분기 · R9) ― 3회차 완성 서버

> 강의자료 **28쪽** (분기 표) · **29쪽** (R9 코드) / **30쪽** (실습 1-3) · **31쪽** (서버 로그)  ·  `AI코어프로젝트_3회차_DAY3_r2.pptx`  ·  실행 위치: **PC**

기기 탭 질문(음성 · 타이핑)은 기기 LLM 이 고르고, 규칙(R1 ~ R5)은 PC 가 텍스트 경로와 같은 함수로 보장한다

## 무엇을 하는가

- source "voice"(PTT) · "device"(기기 탭 타이핑) + ip → 기기 D5, source 없음 · "text" → 2회차와 같이 PC LLM
- [R9] user_content 는 항상 PC 가 만든다. 기기 답은 믿지 않고 `parse_tool_call → apply_rules` 를 그대로 지난다
- 예: '저쪽으로 가' ― 기기 LLM 이 move(right) 를 골라도 방향 근거가 없어 R3 가 ask 로 바꾸고 right 는 args.guess 로 남긴다
- 가라는 말이 없는데 ask 를 고르면 장면 질문으로 보고 describe
- [R10] 답변 문구는 '어디로 출력하나(ip 유무)' 로 정한다 ― 기기 탭이면 칸 수 없이
- [R6] 기기 꺼짐 · 시간 초과(120초) → 502 device_llm_unreachable, 화면은 history 를 유지한다
- 3일차(PJT03) 나머지 실습도 새 API 없이 이 서버를 그대로 쓴다

## 실행

```bash
# 라즈베리파이: page25 기기 서버 (또는 ../../3회차_day2/심화_F205_음성품질 완성본)
python 대시보드_음성통합.py        # 기기 탭에서 PTT 질문 · 타이핑 질문
```

## 확인 포인트

- PTT '앞에 뭐가 있어?' → describe, 장면 설명만
- PTT '오른쪽으로 두 칸 가' → OLED RIGHT + 오른쪽 LED, '오른쪽으로 이동합니다.'
- 기기 탭 타이핑 '왼쪽으로 1칸 가' → source: device ― 역시 기기 LLM, OLED LEFT
- 라즈베리파이 서버를 끄고 질문 → 502 안내 문구, history 유지, 로컬 PC 탭은 정상
- 서버 창 `[tool]` 줄 앞에 `[voice 192.168.x.x]` · `[device 192.168.x.x]` 가 찍힌다

## 이 폴더의 파일

- `대시보드_음성통합.py`

---
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
