# 로컬 음향 분석 구현·검증 기록

2026-10-23. 외부 음성 API를 호출하지 않습니다. 가중치 내려받기는 별도 설치 스크립트에서만 실행하며 요청 처리에서는 local_files_only/weights_only로 읽습니다.

## 제공하는 기능

- 명시적 동의를 받은 5~30초 등록 음성을 세션에 연결합니다. 등록 음성은 기본 24시간 후 워커가 삭제하며, 세션 삭제 시에도 삭제합니다. 경로는 API에 노출하지 않습니다.
- 실제 SpeechBrain ECAPA와 SepFormer WHAMR 가중치를 CPU로 실행합니다. 4초 구간마다 두 음원을 분리하고 등록 화자와의 유사도를 비교합니다. cosine>=0.65, 2위와 margin>=0.15일 때만 지원자 추정 음원을 유지합니다. 두 조건은 검증된 인식 임계값이 아닌 보수적 실험값입니다.
- 불확실 구간은 동일 시간 위치의 무음으로 바꾸므로 타임스탬프가 유지됩니다. STT와 속도 계산은 이 구간의 단어와 시간을 함께 제외합니다. 모델·등록이 없으면 원음 전사를 보존하지만 화자 미분리 상태를 명시합니다.
- 확정 전사를 참조하여 한국어 CTC 강제 정렬을 실행하고 글자별 음향 로그 사후확률과 시각을 제공합니다. 기술 용어와 전사 수정은 참조 문장에만 반영되며 원 ASR의 말하기 속도를 바꾸지 않습니다.
- **CTC 출력은 실험적 음향 일치 진단입니다. 발음 명료도·음소 오류·검증된 발음 등급이 아닙니다. score=null, calibrated=false를 유지합니다.** 자동 발음 평가 요구사항의 정확도 수락 기준은 미완료입니다.

## 설치

backend에서 requirements.txt와 requirements-local.txt를 설치한 뒤 `.venv/Scripts/python.exe scripts/download_audio_models.py`를 실행합니다. models/korean-ctc, models/ecapa, models/sepformer가 생성됩니다. 설정의 studio_*_model_path로 위치를 변경할 수 있습니다. 모델 및 업로드는 공개 저장소에 넣지 않습니다.

## 검증과 한계

- 단위·계약 테스트는 모델 누락, 반복 CTC 토큰, 잘못된 참조, 순번·소유권, 봉인 후 재생·만료, 등록 음성 경로 비노출·삭제, 과거 보고서 고정, 꼬리 질문 최대 1회, 품질 제외 분모·분자 일치를 검사합니다.
- STUDIO_REAL_AUDIO_TEST=1로 실제 CPU 모델 smoke를 별도 실행합니다. 합성 파형은 런타임 검사이며 발음·화자 구분 정확도 결과가 아닙니다.
- Windows Heami 한국어 TTS 참조 문장으로 실제 CTC 56개 음향 정렬 관찰값을 얻었습니다.
- Heami와 Zira TTS를 섞어 실제 SepFormer와 ECAPA를 실행했습니다. 두 구간 모두 등록 유사도가 낮아 제외되었습니다. 따라서 배경 화자 제거 품질이 검증되었다고 주장하지 않습니다. 사람 녹음의 깨끗한/소음/겹침/세 명 이상 조건 평가가 필요합니다.
- 실제 한국어 음소/GOP 전용 모델의 공개 가중치를 조사했으나 바로 사용할 수 있는 검증 모델은 확보하지 못했습니다. Barnbarm 모델 문서는 연구·비상업 한정이며 업로드 스크립트가 기본 비공개입니다. 이 부분은 추가 연구·모델 확보가 필요합니다.

## 근거

- [Kresnik 한국어 CTC 모델](https://huggingface.co/kresnik/wav2vec2-large-xlsr-korean): 한국어 ASR 모델이며 발음 채점 모델이 아닙니다.
- [SpeechBrain ECAPA](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb): 화자 임베딩 모델입니다.
- [SpeechBrain SepFormer WHAMR](https://huggingface.co/speechbrain/sepformer-whamr): 두 화자 분리용 8 kHz 모델이며 한국어 면접 정확도가 보장되는 것은 아닙니다.
- [Barnbarm 모델 문서](https://github.com/truffleplanet/barnbarm/blob/main/AI/docs/models/asr-model-card-v2.md), [가중치 업로드 스크립트](https://github.com/truffleplanet/barnbarm/blob/main/AI/scripts/upload_asr_checkpoint_to_hf.py)

## 공개 사람 음성 양성·음성 대조군 추가 (2026-10-23)

SpeechBrain 공식 테스트 자료 `tests/samples/ASR/spk1_snt1.wav`, `spk2_snt1.wav`로 확인했습니다. 초기에는 원본 16 kHz 등록 음성과 8 kHz SepFormer 출력의 대역폭 차이 때문에 지원자 음성이 보존되지 않았습니다. 등록 음성의 화자 임베딩 입력만 동일한 8 kHz→16 kHz 대역으로 맞춘 후, 기존 임계값을 유지하면서 깨끗한 지원자 음성 cosine .898/.904, 두 사람 혼합 .767/.802로 두 구간 모두 보존했습니다. 상대 출력 유사도는 각각 .338/.318 및 .166/.147이었습니다. 다른 화자만 있는 음성은 제외하는 회귀 검사도 추가했습니다.

이는 공개된 두 화자·짧은 예시의 동작 대조군입니다. 실제 한국어 면접·잔향·3인 이상 조건의 정확도 검증을 대체하지 않습니다. 대역폭 맞춤은 화자 식별용 등록 입력에만 적용하며 발음 진단의 전처리 보장으로 일반화하지 않습니다.

설치 스크립트는 ECAPA `0f99f2d0ebe89ac095bcc5903c4dd8f72b367286`, SepFormer `9950fd8055b38679d2af5bef2366b5dba600ec66`, 한국어 CTC `629c9a3501c10ba128bf3fa1eebb12af3be03f61` commit을 고정합니다.

보고서 `pipeline_versions.expected_model_revisions`는 설치 스크립트가 목표로 하는 기본 모델 commit입니다. 실제 읽은 파일의 해시를 검증한 값이 아니며, 별도 경로·TorchScript 모델을 사용할 수 있으므로 `loaded_model_identity_verified=false`로 명시합니다. 실제 가중치 식별 검증 완료로 해석하면 안 됩니다.
