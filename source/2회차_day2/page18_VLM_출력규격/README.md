# page18 ― VLM 출력규격

> 강의자료 **18쪽** (코드) / **19쪽** (동작 결과)

VLM 설명을 '한국어 한 문장, 40자, 장애물 있음/없음' 규격으로 고정한다

## 무엇을 하는가

- 규격을 프롬프트 · max_tokens · 코드(normalize, check) 세 군데에 건다
- 같은 이미지로 두 번 돌려 재현성을 확인한다

## 실행

```bash
cd page18_VLM_출력규격
python VLM_출력규격.py
python VLM_출력규격.py --image C:\work\core_pjt\source\2회차_day2\samples\victory.jpg --repeat 1
```

## 확인 포인트

- sample.jpg : 25자, 검사 3개 모두 OK, 두 번 모두 같은 문장
- victory.jpg : 딱 40자 ― 경계. 넘으면 자르지 않고 NG 로 기록한다
- CPU 1회 약 8초 (긴 변 448px 입력)

## 이 폴더에 생기는 것

- 실행결과.txt ― 실제 실행 출력

---
실제 실행 출력은 `실행결과.txt` 에 그대로 담아 두었다.
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
