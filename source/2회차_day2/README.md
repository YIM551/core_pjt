# 2회차 2일차 ― 실습 코드

**폴더 하나 = 실습 하나.** 폴더 앞 숫자는 강의자료(`AI코어프로젝트_2회차_DAY2.pptx`)의 코드 쪽번호다.
동작 결과는 바로 다음 쪽에 있다.

VSCode 에서 폴더를 열고 → `README.md` 를 읽고 → 스크립트를 돌리고 →
`실행결과.txt` 와 대조한다. 이 순서면 혼자서도 끝까지 갈 수 있다.

---

## 공용 자료

| 파일 / 폴더 | 내용 | 누가 만드나 |
|---|---|---|
| `samples/sample.jpg` | 1일차와 같은 장면 사진 (810×1080) | 사전 배포 |
| `samples/pointing_up.jpg` | 검지로 위를 가리키는 손 (419×419) | 사전 배포 (MediaPipe 공식 예제 이미지) |
| `samples/victory.jpg` | V 사인 (418×418) | 사전 배포 (MediaPipe 공식 예제 이미지) |
| `page56_LLM_통합답변/perception.json` | 예시 인식 Text (pointing_up.jpg, LLM 입력) ― 실습 4-1 · 4-2 가 읽는다 | 사전 배포 |
| `../2회차_web/` | 웹 대시보드 화면 (`index.html`, `mediapipe/`) ― 2 · 3일차 공용 | 사전 배포 (완성본) |

스크립트는 모두 `__file__` 기준 절대경로를 쓴다.
**어느 디렉터리에서 실행하든 동작하고**, 프로젝트를 통째로 옮겨도 그대로 된다.

---

## 실습 순서

| 쪽 | 폴더 | 하는 일 | 선행 |
|---:|---|---|---|
| 10 | `page10_환경체크` | 설치 확인 (2일차 신규 항목 포함) | ― |
| 14 | `page14_YOLO_텍스트요약` | 검출 결과 → LLM 용 한 문장 | ― |
| 18 | `page18_VLM_출력규격` | VLM 설명 규격화 (약 8초 × 2) | ― |
| 21 | `page21_YOLO_텍스트요약` | 도전 1 ― summarize() 규칙 고치기 (문제 · 정답) | ― |
| 27 | `page27_제스처_인식` | 제스처 · 랜드마크 21점 | ― |
| 31 | `page31_제스처_방향판별` | 랜드마크 벡터로 방향 판별 | ― |
| 36 | `page36_제스처_인식` | 도전 2 ― 펼친 손가락 개수 세기 (문제 · 정답) | ― |
| 45 | `page45_대시보드_서버` | 웹 대시보드 서버 ― 화면 + YOLO + VLM | ― |
| 49 | `page49_대시보드_서버` | 도전 3 ― 서버 상태 확인 API /api/health (문제 · 정답) | ― |
| 56 | `page56_LLM_통합답변` | 인식 Text + 질문 → LLM 답변 | ― |
| 61 | `page61_LLM_JSON파싱` | JSON 출력 + 방어 파싱 | ― |
| 64 | `page64_대시보드_LLM연결` | 웹 대시보드 서버 + LLM 답변 | **45** |
| 67 | `page67_LLM_통합답변` | 도전 4 ― 출처 충돌을 알리는 규칙 한 줄 (문제 · 정답) | ― |
| 과제 | `과제_VLM_단축측정` | 내 PC의 VLM 단축 효과 → `vlm_speed.csv` | ― |

**대시보드 서버(`page45`, `page64`)는 띄워 둔 채 브라우저로 접속한다** ― <http://127.0.0.1:8000>.
`index.html` 을 더블클릭해서 열면 API 호출 · 웹캠 · 제스처 인식이 모두 실패한다.
`page56`, `page61` 는 `perception.json` 이 없으면 내장 예시로 동작한다.

---

## 설치 (1일차 환경에 추가)

```bash
.venv\Scripts\activate
pip install mediapipe==1.0.1
```

### 가중치

| 위치 | 파일 | 크기 | 없으면 |
|---|---|---:|---|
| `C:\work\core_pjt\` | `yolo11n.pt` | 5.4 MB | 첫 실행 시 자동 다운로드 |
| `C:\work\core_pjt\models\` | `Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf` | 1.9 GB | VLM 실행 불가 |
| `C:\work\core_pjt\models\` | `mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf` | 1.3 GB | 이미지 입력이 동작 안 함 |
| `C:\work\core_pjt\models\` | `gesture_recognizer.task` **(신규)** | 8 MB | 제스처 실습 불가 |
| `C:\work\core_pjt\models\` | `Qwen3-4B-Q4_K_M.gguf` **(신규)** | 2.4 GB | LLM 실습 불가 |

받는 방법 (PowerShell · cmd 모두 그대로 붙여 넣는다) :

```bash
cd C:\work\core_pjt
curl.exe -L -o models\gesture_recognizer.task https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task
hf download Qwen/Qwen3-4B-GGUF Qwen3-4B-Q4_K_M.gguf --local-dir models      # 1일차에 받았으면 생략
```

PowerShell 에서는 `curl` 이 다른 명령(Invoke-WebRequest)이라 반드시 `curl.exe` 로 쓴다.

---

## 자주 겪는 문제

| 증상 | 원인 | 해결 |
|---|---|---|
| `FileNotFoundError: Can't find file` (mediapipe) | mediapipe 가 한글 경로를 못 읽음 | 실습 코드처럼 바이트/배열로 넘긴다 |
| `W0000` / `I0000` 로그가 잔뜩 나옴 | mediapipe 내부 로그 | 오류 아님. 무시 |
| `load_hparams: Qwen-VL models require ...` | llama.cpp 안내 로그 | 오류 아님. 무시 |
| 방향이 좌우 반대로 나옴 | 셀카 카메라의 거울 화면 | `--mirror` |
| `ggml-cuda ... CUDA error` 로 서버 종료 | torch(GPU) 와 llama.cpp(GPU) 가 한 프로세스에서 충돌 | `set CUDA_VISIBLE_DEVICES=-1` 로 CPU 고정 |
| 대시보드 화면이 안 뜸 / 웹캠이 안 켜짐 | html 파일을 직접 엶 / 카메라 권한 거부 | 서버 실행 후 <http://127.0.0.1:8000> 으로 접속, 권한 허용 |
| 대시보드의 YOLO · VLM 칸에 '오류' | 서버에서 추론 실패 | 서버 창의 `[yolo]` / `[vlm]` 로그 확인 |
| `[Errno 10048] bind on address` | 8000 포트 사용 중 (1일차 PoC 서버 등) | 기존 서버 종료 |
| PC 가 느려짐 (CPU 100%) | VLM · LLM 이 모든 코어를 사용 | 정상. 무거운 실습은 하나씩 |

옵션은 모든 스크립트에서 `-h` 로 확인할 수 있다.
