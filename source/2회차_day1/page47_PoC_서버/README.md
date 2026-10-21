# page47 ― PoC 서버

> 강의자료 **47쪽** (코드)

YOLO 와 VLM 을 하나의 FastAPI 서버로 묶는다

## 무엇을 하는가

- POST /api/yolo-detect : 이미지 → 객체 요약 문장
- POST /api/vlm-describe : 이미지 → 장면 설명 문장
- 추론은 run_in_threadpool() 로 스레드풀에 위임한다

## 실행

```bash
cd page47_PoC_서버
python PoC_FastAPI서버.py
```

## 확인 포인트

- 이 창은 띄워 둔 채로 두고, page49_PoC_클라이언트 폴더에서 클라이언트를 실행한다
- http://127.0.0.1:8000/api/health 로 로딩 상태를 볼 수 있다

## 이 폴더에 생기는 것

- 실행결과.txt ― 실제 실행 출력

---
실제 실행 출력은 `실행결과.txt` 에 그대로 담아 두었다.
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
