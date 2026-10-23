# Local AI Interview Studio — 로컬 AI 면접 스튜디오

> **통합 면접 스튜디오 추가:** 다크·보라색 UI, 개인 지원자료, 시간제 면접, 로컬 모델과 웹캠·마이크 수집을 연결했습니다. [로컬 실행 안내](docs/studio-local.md)와 [단계별 구현·검증 현황](docs/studio-implementation.md)을 먼저 확인하세요. 신규 기능은 `/api/v2/studio`를 사용합니다. 아래 내용은 기존 기능의 안내를 포함합니다.

이력서·포트폴리오·기업 정보·채용 공고를 근거로 질문하고, 답변 내용과 전달 방식을 로컬에서 복기하는 Vue/FastAPI/PostgreSQL 프로그램입니다. [v0.3 요구사항 점검표](docs/v03-audit.md)에 구현·검증·후속 항목을 구분했습니다.

- 양안 눈동자·머리 자세와 6지점 개인 보정으로 카메라 방향·화면 영역을 추정합니다. 검증된 정밀 안구 추적기나 집중력 판정기는 아닙니다.
- ECAPA·SepFormer로 등록 화자의 음성을 추정하고 불확실한 구간을 제외합니다. 실제 환경별 정확도는 검증 중입니다.
- 한국어 CTC 강제 정렬을 **실험적 음향 진단**으로 제공합니다. 발음 점수·등급·음소 오류 판정을 만들지 않습니다.
- 모델 실행은 로컬 전용입니다. 공개 백업에는 개인 자료·음성·DB·인증정보·모델 가중치를 포함하지 않습니다. 모델 설치는 [음향 모델 안내](docs/local-audio-analysis.md)와 [영상 모델 안내](frontend/docs/local-media.md)를 따릅니다.

## 실행과 검증

[로컬 실행 안내](docs/studio-local.md)를 따라 PostgreSQL, API, 워커, 로컬 모델 서버와 프론트를 실행합니다. Docker Compose는 DB를 제공합니다. API 문서는 기본 개발 설정에서 http://127.0.0.1:8002/docs 입니다.

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q
cd ..\frontend
npm test
npm run build
```

기존 CareerFit 개인 문서·RAG 채팅 기능도 포함합니다. 실제 API 계약은 서버의 OpenAPI 문서를 확인하세요. 신규 면접 계약은 `/api/v2/studio` 아래에 있습니다.

## 공개 백업 범위

`PUBLIC_SNAPSHOT.json`은 배포 소스의 SHA-256 목록입니다. 실제 `.env`, 개인 문서, 녹음·영상, DB, 모델 가중치, 의존성과 빌드 산출물은 제외합니다. 설치 모델과 미완료 수락 기준은 위 문서에 명시합니다.
