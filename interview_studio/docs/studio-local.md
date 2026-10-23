# 면접 스튜디오 로컬 실행

통합 앱은 `interview_pjt`에 구현하며 `core_pjt`의 다크·보라색 디자인과 로컬 Qwen3 모델을 재사용합니다. 기존 API와 페이지도 유지합니다. 개인 자료와 음성은 외부 모델 API로 보내지 않습니다.

## 실행

최초 환경 구성은 backend에서 `python -m venv .venv`, `.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-local.txt`, frontend에서 `npm ci`를 실행합니다. 모델 가중치는 별도 로컬 파일이며 Python 의존성 설치에 포함되지 않습니다.

공개 백업을 복원했다면 backend에서 `.\.venv\Scripts\python scripts/download_audio_models.py`, frontend에서 `npm run prepare:vision`을 실행해 모델·WASM을 준비합니다. Whisper는 backend에서 다음 명령으로 별도 준비합니다. 이 설치 단계만 인터넷을 사용합니다.

```powershell
.\.venv\Scripts\python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-small', local_dir='models/faster-whisper-small', allow_patterns=['*.json','*.bin','*.txt'])"
```

아래 `C:\work\interview_pjt`는 현재 작업 PC의 예시 경로입니다. 공개 백업에서는 `core_pjt/interview_studio`를 기준으로 자신의 복제 경로에 맞춥니다. LLM 가중치는 기존 core 프로젝트의 로컬 GGUF 파일을 지정하거나 별도로 준비합니다.

PowerShell 창을 각각 열어 실행합니다. 기존 core 서버의 8000번 포트와 충돌하지 않도록 API는 8002, 화면은 5174를 사용합니다.

```powershell
cd C:\work\interview_pjt
docker compose up -d db
cd backend
$env:DATABASE_URL='postgresql+psycopg://careerfit:careerfit@localhost:5432/careerfit'
$env:STUDIO_STT_MODEL_PATH='C:\work\interview_pjt\backend\models\faster-whisper-small'
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
```

```powershell
cd C:\work\interview_pjt\frontend
$env:CAREERFIT_API_TARGET='http://127.0.0.1:8002'
npm run dev -- --host 127.0.0.1 --port 5174
```

질문·내용 평가용 로컬 모델 서버:

```powershell
cd C:\work\interview_pjt\backend
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python -m llama_cpp.server --model C:\work\core_pjt\models\Qwen3-4B-Q4_K_M.gguf --model_alias qwen-model --host 127.0.0.1 --port 8080 --n_ctx 8192 --n_threads 8 --n_gpu_layers 0 --verbose false
```

화면: <http://127.0.0.1:5174/>. 장치 권한은 화면의 장치 확인 동작에서 요청합니다. 텍스트 모드에서는 웹캠·마이크가 필요하지 않습니다. 프로세스는 해당 창에서 Ctrl+C로 종료할 수 있습니다. DB 보존을 위해 Docker 볼륨 삭제 명령은 사용하지 않습니다.

요청이 없는 시간의 작업 복구와 미디어 보관 기한 정리를 위해 별도 창에서 워커도 실행합니다.

```powershell
cd C:\work\interview_pjt\backend
$env:DATABASE_URL='postgresql+psycopg://careerfit:careerfit@localhost:5432/careerfit'
.\.venv\Scripts\python -m app.studio.worker --watch
```

## 로컬 모델

- LLM: 기존 `core_pjt/models/Qwen3-4B-Q4_K_M.gguf`.
- STT: `backend/models/faster-whisper-small`의 로컬 가중치. [faster-whisper 공식 사용법](https://github.com/SYSTRAN/faster-whisper).
- 영상: `frontend/public/models/face_landmarker.task`, `pose_landmarker_lite.task`와 같은 서버에서 제공하는 WASM. [얼굴 분석 문서](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/web_js), [자세 분석 문서](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/web_js).
- 실험적 음향 진단·화자 분리: `backend/models/korean-ctc`, `ecapa`, `sepformer`. 설치 스크립트는 공개 모델 commit을 고정하며 런타임에는 내려받지 않습니다. [원리와 한계](local-audio-analysis.md).

모델 다운로드와 패키지 설치에는 인터넷을 사용하지만, 면접 자료·녹음·카메라 프레임의 추론은 로컬에서 수행합니다. 실제 한국어 발음 정확도, 시선 방향 추정 기준, 다양한 소음·가림 환경의 품질 검증은 별도 수락 항목입니다. 모델 실패·미검출·미구성은 미측정으로 표시합니다.

## 검증 명령

```powershell
cd C:\work\interview_pjt\backend
.\.venv\Scripts\python -m pytest -q
cd ..\frontend
npm test
npm run build
```

신규 계약은 `/api/v2/studio` 아래에 추가해 기존 `/api/v2` 자유 대화 면접 계약과 구분합니다. 실제 단계별 구현·검증 결과는 작업 완료 보고서에 기록합니다.
