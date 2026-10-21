# page61 ― LLM JSON파싱

> 강의자료 **61쪽** (코드) / **62쪽** (동작 결과)

LLM 답을 JSON 으로 받고, 깨진 출력도 안전하게 파싱한다

## 무엇을 하는가

- [A] LLM 실제 호출 → 방어 파싱
- [B] 실제로 겪은 깨진 출력 6종으로 파서를 점검한다

## 실행

```bash
cd page61_LLM_JSON파싱
python LLM_JSON파싱.py
python LLM_JSON파싱.py --skip-llm   # 파서 점검만
```

## 확인 포인트

- 6종 중 5종은 ok=True, 잘린 think 는 ok=False 와 기본값
- bool("false") 는 True ― 파서의 to_bool() 이 막는다

## 이 폴더에 생기는 것

- 실행결과.txt ― 실제 실행 출력

---
실제 실행 출력은 `실행결과.txt` 에 그대로 담아 두었다.
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
