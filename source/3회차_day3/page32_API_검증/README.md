# page32 ― API 검증 ― PJT02

> 강의자료 **32쪽** (실습 1-4) · **33쪽** (동작 결과)  ·  `AI코어프로젝트_3회차_DAY3_r2.pptx`  ·  실행 위치: **PC**

2일차 page29_기기연동_API_검증 스크립트에 PJT02 항목(A9 · D4 · D5 · R9, 음성 · 기기 탭 타이핑 경로)을 더한다

## 무엇을 하는가

- `--quick` : + A9 502, source=voice · device 인데 기기가 없으면 502 device_llm_unreachable (R6)
- 전체 : + R9 (source 없는 요청 = source text 요청)
- `--device <IP>` : + D4 · D5 직접, A9 중계, 음성 경로 TOOL_CASES 전부(R9 · R10), 기기 탭 타이핑(source=device)
- `--quick --device <IP>` : PC 인식 모델 없이 라즈베리파이 항목만 (기기 탭 질문은 모두 기기 LLM 을 쓰므로 가능)

## 실행

```bash
# 터미널 1
python ..\page30_음성경로_통합\대시보드_음성통합.py

# 터미널 2
python API_검증.py --quick
python API_검증.py
python API_검증.py --device <PiIP>      # 기기와 함께
```

## 확인 포인트

- `--quick` 22/22, 전체 98/98 (기기 없이)
- 기기와 함께 : PJT01 항목 + A9 · D4 · D5 · R9 · R10 전부 PASS
- 기기 LLM 첫 요청은 1분 가까이 ― 미리 한 번 호출해 두면(page25 D5_단독확인.py) 빨라진다

## 이 폴더의 파일

- `API_검증.py`
- `실행결과.txt` ― PC 에서 실제로 실행한 출력 (대조용)

---
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
