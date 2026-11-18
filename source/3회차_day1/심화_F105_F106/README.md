# 심화 ― 스트림 안정화 · 부팅 자동 실행

> 강의자료 **73쪽** (심화 과제) · **69 ~ 70쪽** (도전 3 · FPS)  ·  `AI코어프로젝트_3회차_DAY1.pptx`  ·  실행 위치: **라즈베리파이**

F105 조용한 단절 · FPS 조정, F106 systemd 로 부팅 시 기기 서버 자동 실행

## 무엇을 하는가

- F105 ― 코드는 이미 들어 있다: PC 의 `STREAM_READ_TIMEOUT = 10.0`(page47 서버), 화면의 3초 뒤 재연결, 기기 서버의 `--fps` 옵션(page38). 해상도가 아니라 FPS 부터 낮춘다 ― 해상도를 낮추면 YOLO · VLM 정확도가 떨어진다
- F106 ― `camera-stream.service` 를 등록한다. `__USER__` 를 실제 사용자 이름으로 바꾸고, F105에서 검증한 640×480 / 10 FPS 설정으로 실행한다.
- 같은 서비스 파일을 2일차 이후(D4 · D5)에도 그대로 쓴다 ― ExecStart 는 `~/camera_server.py` 를 venv 파이썬으로 띄운다

## 실행

```bash
# F105
~/venv/bin/python3 ~/camera_server.py --fps 10

# F106: 서비스 파일을 Pi 홈에 복사하고, 수동 서버를 실행한 창에서 Ctrl+C로 종료한 뒤 실행
sed -i "s/__USER__/$USER/g" ~/camera-stream.service
sudo install -m 0644 ~/camera-stream.service /etc/systemd/system/camera-stream.service
sudo systemctl daemon-reload
sudo systemctl enable --now camera-stream.service
systemctl is-enabled camera-stream.service
systemctl is-active camera-stream.service
```

## 확인 포인트

- F105 ― 기기 탭 영상 아래 실제 FPS 가 바뀐다. Wi-Fi 를 잠깐 끊으면 약 10초 뒤 스트림 종료 → 3초 뒤 재연결
- F106 ― `enabled`와 `active`를 확인한 뒤 `sudo reboot`한다. SSH로 다시 접속해 수동으로 서버를 실행하기 전에 `systemctl is-active camera-stream.service`와 `journalctl -b -u camera-stream.service --no-pager -n 25`로 이번 부팅에서 기동한 상태를 확인한다. 대시보드 영상, OLED의 `start` 표시, LED를 확인한다.
- 비정상 종료 후 재시작을 확인하려면 `systemctl show -p MainPID -p NRestarts camera-stream.service`로 실행 상태를 기록하고, 해당 서비스의 메인 PID에 `sudo kill -KILL <PID>`를 보낸다. 잠시 뒤 서비스가 다시 `active`이고 PID와 재시작 횟수가 바뀌는지 확인한다.
- 서비스가 도는 동안 손으로 또 띄우면 8080 포트 · 카메라 충돌 ― 먼저 `sudo systemctl stop camera-stream`

## 이 폴더의 파일

- `camera-stream.service`

---
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
