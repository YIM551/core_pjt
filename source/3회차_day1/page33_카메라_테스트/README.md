# page26 ― 카메라 확인

> 강의자료 **32쪽** (카메라 연결) / **33쪽** (실습 2-1) · **34쪽** (동작 결과)  ·  `AI코어프로젝트_3회차_DAY1.pptx`  ·  실행 위치: **라즈베리파이**

서버 없이 카메라(CSI)와 picamera2 만 따로 확인하고, 기기 서버를 띄울 venv 를 만든다

## 무엇을 하는가

- `rpicam-hello --list-cameras` 로 인식 확인 → 이 스크립트로 640x480 스냅샷 저장 · 실제 FPS 측정
- venv 는 반드시 `--system-site-packages` ― picamera2 는 apt 로 설치되는 시스템 패키지라 이 옵션이 없으면 카메라를 못 쓴다
- 설치 명령 전체는 `../설치_명령어_기기.sh`

## 실행

```bash
rpicam-hello --list-cameras
python3 -m venv --system-site-packages ~/venv
~/venv/bin/python3 test_camera.py
~/venv/bin/python3 test_camera.py --fps 10    # [F105] FPS 를 낮췄을 때 비교
```

## 확인 포인트

- 카메라 목록이 비어 있지 않다 ― 비면 전원을 끄고 CSI 케이블(접점 방향 · 잠금 탭)을 다시 꽂는다
- `camera_test.jpg` 를 scp 로 PC 에 가져와 초점 · 밝기를 본다
- 측정 FPS 가 설정값(15) 근처

## 이 폴더의 파일

- `test_camera.py`
- `기대출력.txt` ― 라즈베리파이 실물에서 나와야 하는 출력 형식 (코드의 출력 문구 · 강의자료 기준, 실측 아님)

---
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
