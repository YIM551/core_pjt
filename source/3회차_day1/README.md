# 3회차 1일차 (PJT01) ― 라즈베리파이 기기 연동 · 실습 코드

**폴더 하나 = 실습 하나.** 폴더 앞 숫자는 강의자료(`AI코어프로젝트_3회차_DAY1.pptx`)의 처음 쪽번호다 (지금 쪽은 아래 표).

VSCode 에서 폴더를 열고 → `README.md` 를 읽고 → 스크립트를 돌리고 →
`실행결과.txt`(PC 실측) 또는 `기대출력.txt`(라즈베리파이 ― 출력 형식) 와 대조한다.

---

## 오늘 만드는 것

2회차 도구 호출(move · describe · ask)을 **시뮬레이터 대신 라즈베리파이 5 의 OLED · LED** 로 출력한다.
2회차 API(A1 ~ A5)와 규칙(R1 ~ R5)은 **하나도 바꾸지 않고**, 새 엔드포인트만 더한다 (F101).

```
카메라(Picamera2) → 기기 /stream.mjpg (D1) → PC /api/camera-stream (A6) → 기기 탭 영상
기기 탭 [전송] → 스냅샷 → YOLO(A3) · VLM(A4) · MediaPipe → /api/llm-answer (A5, 2회차와 같다)
move → PC /api/oled-display (A8) → 기기 /oled-display (D3) : LEFT · RIGHT (좌우만)
     → PC /api/robot-signal (A7) → 기기 /gpio-blink   (D2) : right → GPIO 17, left → GPIO 27 (좌우만)
```

| 파일 / 폴더 | 내용 | 누가 만드나 |
|---|---|---|
| `../3회차_web/` | 대시보드 화면 (연동 탭 · 기기 탭 포함) ― 3회차 내내 같은 파일 | 사전 배포 (완성본) |
| `samples/` | 검증에 쓰는 사진 (`sample.jpg`, 2회차와 같은 파일) | 사전 배포 |
| `설치_명령어_기기.sh` | 라즈베리파이 준비 명령 (SPI · 카메라 · venv · luma.oled · scp) | 사전 배포 |
| `명령어_모음_DAY1.md` | 강의자료 명령어 화면을 복사용으로 옮긴 것 (쪽별 · 명령만) ― gist 로 배포 | 사전 배포 |

---

## 실습 순서

| 쪽 | 폴더 | 하는 일 | 어디서 |
|---:|---|---|---|
| 23 ~ 24 | `page23_기준선_검증` | 실습 1-1 ― 2회차 서버(+ 개선안)로 검증 → 기준선 80/80 PASS 기록 | PC |
| 32 ~ 34 | `page33_카메라_테스트` | 실습 2-1 ― 카메라 인식 · 스냅샷 · 실제 FPS | Pi |
| 35 ~ 37 | `page36_LED_테스트` | 실습 2-2 ― LED 2개 배선만 따로 확인 | Pi |
| 38 ~ 40 | `page39_OLED_테스트` | 실습 2-3 ― SPI 켜기 · OLED 배선만 따로 확인 | Pi |
| 45 ~ 49 | `page45_기기서버_D1_D3` | 실습 3-1 · 3-2 ― 기기 서버 D1 영상 · D2 LED · D3 OLED | Pi |
| 53 ~ 54 | `page53_카메라_중계` | 실습 4-1 ― 기준선 서버 + A6, 기기 탭에 라즈베리파이 영상 | PC |
| 55 ~ 63 | `page61_기기연동` | 실습 4-2 ― + A7 · A8 · R10, move 를 OLED · LED 로 (**PJT01 완성 서버**) | PC |
| 71 ~ 72 | `page71_API_검증` | 실습 5-1 ― 기준선 항목 + A6 ~ A8 · R6 · R8 · R10 (`--quick` · `--device`) | PC |
| 73 | `심화_F105_F106` | 스트림 안정화(FPS) · systemd 부팅 자동 실행 | Pi |

PC 서버는 단계마다 **앞 단계 서버 + 새 기능** 이다. 앞 폴더 서버를 끄고 다음 폴더 서버를 띄운다.

```bash
# 터미널 1 ― PC 서버 (단계별로 바꿔 가며)
cd page61_기기연동
python 대시보드_기기연동.py            # 브라우저 http://127.0.0.1:8000

# 터미널 2 ― 설계대로 동작하는지
cd page71_API_검증
python API_검증.py --quick             # 기기 없이 (몇 초)
python API_검증.py --device <PiIP>     # 제출용
```

라즈베리파이 쪽은 PC 에서 `scp` 로 홈 폴더에 복사해 SSH 로 실행한다 (`설치_명령어_기기.sh`).

---

## 설치

- **PC** ― 새로 설치할 것이 없다. 2회차 환경(`.venv`, `models\` 가중치) 그대로.
- **라즈베리파이** ― `설치_명령어_기기.sh` (SPI 켜기, `python3 -m venv --system-site-packages ~/venv`, `~/venv/bin/pip install luma.oled`).

### 배선 (강의자료 31쪽 · 전원을 끄고)

| 장치 | 신호 | BCM GPIO | 물리 핀 |
|---|---|---|---|
| LED 오른쪽 · 왼쪽 | + (긴 다리, 저항 220 ~ 330Ω 거쳐) | 17 · 27 | 11 · 13 |
| LED 공통 | − (짧은 다리) | GND | 6 |
| OLED | VCC · GND | 3.3V · GND | 17 · 20 |
| OLED | DIN · CLK | 10 · 11 | 19 · 23 |
| OLED | CS · DC · RST | 8 · 25 · 22 | 24 · 22 · 15 |
| 카메라 | CSI | ― | CSI 커넥터 (Pi 5 는 22핀) |

---

## 자주 겪는 문제

| 증상 | 원인 | 해결 |
|---|---|---|
| 기준선에 FAIL 이 있다 | 2회차 서버 · 모델 문제 | 3회차 작업 전에 먼저 고친다 (번호 → 명세서 표) |
| `GPIO busy` | 기기 서버가 핀을 잡고 있음 / OLED RST 를 17 · 27 에 꽂음 | `pkill -f "[c]amera_server.py"`, RST 는 GPIO 22 |
| 'OLED 표시 완료' 로그인데 화면이 없다 | SPI 는 단방향 ― 코드는 실패를 모른다 | DC · RST 핀, 3.3V, SPI 켜짐 확인 |
| OLED 가 안 나오고 `oled: unavailable` | 시스템 `python3` 로 실행 (luma.oled 는 venv 에만) | `~/venv/bin/python3 ~/camera_server.py` |
| 카메라를 못 연다 | venv 에 `--system-site-packages` 없음 / 다른 프로그램이 카메라 사용 | venv 다시 만들기 / 서버 · 서비스 끄기 |
| 기기 탭 영상이 안 나온다 | 연동 탭 IP 오타 · 다른 네트워크 · page16 서버를 띄움 | `http://<PiIP>:8080/stream.mjpg` 를 PC 브라우저로 먼저 |
| up · down 일 때 LED 가 안 켜진다 | LED 는 좌우 2개뿐 (A7 400) | 정상 (R8) |
| 기기 탭 '음성 ● 끊김' | 1일차 서버에는 A9 가 없다 | 정상 ― 2일차 page41 에서 생긴다 |
| SSH 로 `pkill -f camera_server.py` 를 보냈더니 세션이 끊김 | 명령 문자열이 패턴에 걸림 | `pkill -f "[c]amera_server.py"` |

옵션은 모든 스크립트에서 `-h` 로 확인할 수 있다.
