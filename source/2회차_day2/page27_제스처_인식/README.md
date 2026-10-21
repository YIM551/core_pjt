# page27 ― 제스처 인식

> 강의자료 **27쪽** (코드) / **28쪽** (동작 결과)

MediaPipe GestureRecognizer 로 손 제스처와 랜드마크 21점을 얻는다

## 무엇을 하는가

- pointing_up.jpg / victory.jpg 두 장을 인식한다
- --save 로 랜드마크 21점을 그린 PNG 를 이 폴더에 저장한다

## 실행

```bash
cd page27_제스처_인식
python 제스처_인식.py --save
```

## 확인 포인트

- Pointing_Up (0.82) / Victory (0.91) 이 나오면 성공
- mediapipe 는 한글 경로를 못 읽는다 ― 스크립트는 파일을 바이트/배열로 넘긴다
- W0000 / I0000 로 시작하는 로그는 오류가 아니다

## 이 폴더에 생기는 것

- landmarks_pointing_up.png
- landmarks_victory.png
- 실행결과.txt ― 실제 실행 출력

## 도전 문제 2

> 강의자료 **36쪽** ― `../page36_제스처_인식` 폴더에서 한다

---
실제 실행 출력은 `실행결과.txt` 에 그대로 담아 두었다.
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
