# 심화 ― 스트림 안정화 · 부팅 자동 실행

> 강의자료 **27 ~ 28쪽** (도전 문제 · FPS 와 해상도) · F106 은 강의자료 없이 이 README 로 진행 (선택)  ·  `AI코어프로젝트_3회차_DAY2_r2.pptx` (1일차 이어서)  ·  실행 위치: **라즈베리파이**

F105 조용한 단절 · FPS 조정, F106 systemd 로 부팅 시 기기 서버 자동 실행

## 무엇을 하는가

- F105 ― 코드는 이미 들어 있다: PC 의 `STREAM_READ_TIMEOUT = 10.0`(page15 서버), 화면의 3초 뒤 재연결, 기기 서버의 `--fps` 옵션(1일차 page38). 해상도가 아니라 FPS 부터 낮춘다 ― 해상도를 낮추면 YOLO · VLM 정확도가 떨어진다
- F106 ― `camera-stream.service` 를 등록한다. `__USER__` 를 실제 사용자 이름으로 바꾼다
- 같은 서비스 파일을 2일차 이후(D4 · D5)에도 그대로 쓴다 ― ExecStart 는 `~/camera_server.py` 를 venv 파이썬으로 띄운다

## 실행

```bash
# F105
~/venv/bin/python3 ~/camera_server.py --fps 10

# F106 (PC 에서 scp camera-stream.service pi@<PiIP>:~/ 후)
sed -i "s/__USER__/$USER/g" ~/camera-stream.service
sudo cp ~/camera-stream.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now camera-stream
journalctl -u camera-stream -f            # 로그
```

## 확인 포인트

- F105 ― 기기 탭 영상 아래 실제 FPS 가 바뀐다. Wi-Fi 를 잠깐 끊으면 약 10초 뒤 스트림 종료 → 3초 뒤 재연결
- F106 ― 전원을 껐다 켠 뒤 아무 조작 없이 영상 · OLED('start') · LED 가 동작한다
- 서비스가 도는 동안 손으로 또 띄우면 8080 포트 · 카메라 충돌 ― 먼저 `sudo systemctl stop camera-stream`

## 이 폴더의 파일

- `camera-stream.service`

---
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
