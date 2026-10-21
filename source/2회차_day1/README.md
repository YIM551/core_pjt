# 2회차 1일차 ― 실습 코드

**폴더 하나 = 실습 하나.** 폴더 앞 숫자는 강의자료(`AI코어프로젝트_2회차_DAY1.pptx`)의 코드 쪽번호다.
동작 결과는 바로 다음 쪽에 있다.

VSCode 에서 폴더를 열고 → `README.md` 를 읽고 → 스크립트를 돌리고 →
`실행결과.txt` 와 대조한다. 이 순서면 혼자서도 끝까지 갈 수 있다.

---

## 공용 자료

| 폴더 | 내용 | 누가 만드나 |
|---|---|---|
| `samples/` | 입력 이미지 (`sample.jpg` 810×1080) | 사전 배포 |
| `dataset/` | 파인튜닝용 데이터셋 | `page56_데이터셋_준비` |
| `runs/` | 학습 결과 (`ft_v1/weights/best.pt`) | `page58_파인튜닝_학습` |

스크립트는 모두 `__file__` 기준 절대경로를 쓴다.
**어느 디렉터리에서 실행하든 동작하고**, 프로젝트를 통째로 옮겨도 그대로 된다.

---

## 실습 순서

| 쪽 | 폴더 | 하는 일 | 선행 |
|---:|---|---|---|
| 15 | `page15_환경체크` | 설치 확인 (패키지 · 디바이스 · 가중치) | ― |
| 23 | `page23_모델로딩_지연과락` | 지연 로딩 + 락으로 중복 로드 막기 | ― |
| 25 | `page25_YOLO_첫추론` | 첫 추론, conf 임계값 비교 | ― |
| 28 | `page28_YOLO_성능측정` | 시간·메모리 측정 → `measurement.csv` | ― |
| 37 | `page37_VLM_이미지설명` | VLM 로드 및 한국어 설명 (약 90초) | ― |
| 39 | `page39_VLM_프롬프트비교` | 프롬프트별 출력 차이 | ― |
| 42 | `page42_VLM_프롬프트비교` | 도전 2 ― 출력을 통제하는 프롬프트 (문제 · 정답, 약 3분) | ― |
| 47 | `page47_PoC_서버` | FastAPI 서버 (띄워 둔다) | ― |
| 49 | `page49_PoC_클라이언트` | 두 엔드포인트 호출·비교 | **47** |
| 56 | `page56_데이터셋_준비` | 데이터셋 생성·검증 → `dataset/` | ― |
| 58 | `page58_파인튜닝_학습` | 전이학습 → `runs/` | **56** |
| 61 | `page61_파인튜닝_평가` | 전/후 비교 → `finetune_compare.csv` | **56, 58** |

YOLO 결과를 한 문장으로 바꾸는 실습은 2일차로 옮겼다 (`source/2회차_day2/page14_YOLO_텍스트요약`).

**Part 4(47·49)는 터미널 2개**가 필요하다. 먼저 47에서 서버를 띄우고,
그 창은 그대로 둔 채 새 터미널에서 49를 실행한다.

---

## 설치

```bash
# 1) 가상환경 ― 배포 폴더(README.md · source)는 반드시 C:\work\core_pjt 에 둔다
cd C:\work\core_pjt
python -m venv .venv
.venv\Scripts\activate          # Windows
#   PowerShell 에서 '스크립트를 실행할 수 없으므로' 가 나오면 한 번만:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
source .venv/bin/activate       # macOS / Linux

# 2) 패키지
python -m pip install --upgrade pip
pip install fastapi==0.141.1 uvicorn==0.54.0 pillow==12.3.0 httpx==0.28.1 psutil==7.2.2
pip install ultralytics==8.4.164 torch==2.14.0 torchvision==0.29.0
pip install llama-cpp-python==0.3.34 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

### 가중치

| 위치 | 파일 | 크기 | 없으면 |
|---|---|---:|---|
| `C:\work\core_pjt\` | `yolo11n.pt` | 5.4 MB | 첫 실행 시 자동 다운로드 |
| `C:\work\core_pjt\models\` | `Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf` | 1.9 GB | VLM 실행 불가 |
| `C:\work\core_pjt\models\` | `mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf` | 1.3 GB | 이미지 입력이 동작 안 함 |

받는 방법 (VLM 두 파일, 약 3.1 GB) :

```bash
cd C:\work\core_pjt
pip install huggingface_hub==2.0.0
hf download ggml-org/Qwen2.5-VL-3B-Instruct-GGUF Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf --local-dir models
hf download ggml-org/Qwen2.5-VL-3B-Instruct-GGUF mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf --local-dir models

# 2일차 LLM (2.4 GB) ― 미리 받아 두면 2일차가 편하다
hf download Qwen/Qwen3-4B-GGUF Qwen3-4B-Q4_K_M.gguf --local-dir models
```

`mmproj` 를 빠뜨리는 것이 가장 흔한 실수다. 두 파일이 **모두** 있어야 한다.

---

## VSCode 세팅

1. `File → Open Folder` → `C:\work\core_pjt`
   (상위 폴더를 열어야 `models\`, `yolo11n.pt` 가 함께 보인다)
2. 확장 설치 : Python (Microsoft)
3. `Ctrl+Shift+P` → `Python: Select Interpreter` → `.venv` 선택
   — 이걸 빠뜨리면 터미널에서는 되는데 ▶ 실행은 `ModuleNotFoundError` 가 난다
   — 목록에 `.venv` 가 없으면 연 폴더가 `C:\work\core_pjt` 가 아닌 것이다 (1번부터 다시).
     그래도 없으면 `Enter interpreter path` → `C:\work\core_pjt\.venv\Scripts\python.exe`
4. 통합 터미널 `` Ctrl+` `` — Part 4는 `+` 로 터미널 2개를 띄운다

---

## 자주 겪는 문제

| 증상 | 원인 | 해결 |
|---|---|---|
| `ModuleNotFoundError: llama_cpp` | 인터프리터가 `.venv` 가 아님 | `Python: Select Interpreter` → `.venv` 후 터미널 재시작 |
| `VLM 본체 / mmproj 파일이 없습니다` | 가중치 미다운로드 | `models\` 에 GGUF 2개 모두 배치 |
| `image slice encoded in ...` 로그 | llama.cpp 진행 로그 | 오류 아님. 무시 |
| `[Errno 10048] bind on address` | 8000 포트 사용 중 | 기존 서버 종료 또는 `--port 8001` |
| `torch.cuda.is_available() False` | torch CPU 빌드 | CUDA 빌드로 재설치 (RTX 50 시리즈는 cu128+) |
| `CUDA out of memory` | batch/imgsz 과다 | `batch` 16 → 8 → 4 로 축소 |
| 첫 호출만 10초 이상 | 모델 지연 로딩 | 정상. 두 번째 호출부터 빨라진다 |

옵션은 모든 스크립트에서 `-h` 로 확인할 수 있다.
