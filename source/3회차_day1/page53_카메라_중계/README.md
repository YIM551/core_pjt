# page47 ― 카메라 중계 (A6)

> 강의자료 **53쪽** (실습 4-1 A6) · **54쪽** (device_url · device_get)  ·  `AI코어프로젝트_3회차_DAY1.pptx`  ·  실행 위치: **PC**

page16 기준선 서버에 A6 /api/camera-stream 하나만 더해, 라즈베리파이 영상을 기기 탭에 띄운다

## 무엇을 하는가

- 브라우저 → PC(8000) `/api/camera-stream?ip=` → 기기(8080) `/stream.mjpg` ― 재인코딩 없이 바이트 그대로
- PC 가 중계하는 이유 ― 같은 출처라 CORS · canvas 스냅샷 보안 제한이 없고, 주소 검증 · 오류 격리를 한 곳에서 한다
- 기기 연결 실패 → 이 요청만 502 camera_unreachable (R6). 로컬 PC 탭은 영향 없음
- `device_url()` 이 IP · 호스트 이름 형식만 허용한다 ― 경로 끼워넣기 방지
- [F105] 읽기 10초 동안 데이터가 없으면 스트림을 끝낸다 → 화면이 3초 뒤 다시 연결

## 실행

```bash
python 대시보드_카메라중계.py      # http://127.0.0.1:8000
# 연동 탭 → 기기 이름 · IP 등록 → 기기 탭에 영상

# 기기 없이 확인 (다른 터미널)
curl -i "http://127.0.0.1:8000/api/camera-stream"
curl -i "http://127.0.0.1:8000/api/camera-stream?ip=192.0.2.1"
```

## 확인 포인트

- 기기 탭 영상 아래에 '스트리밍 중 · 약 15fps'
- ip 없음 → 400 invalid_request, 연결할 수 없는 IP → 502 camera_unreachable
- 아직 A7 · A8 이 없으므로 기기 탭에서 move 를 해도 OLED · LED 는 그대로다 (다음 단계)

## 이 폴더의 파일

- `대시보드_카메라중계.py`
- `실행결과.txt` ― PC 에서 실제로 실행한 출력 (대조용)

---
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
