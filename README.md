# 2회차 산출물 ― 멀티모달 AI Workflow 웹 대시보드

웹캠 화면을 보고 질문하면 **YOLO(객체 인식) · VLM(장면 설명) · MediaPipe(손 제스처)** 결과를 Text 로 모아
**LLM** 이 의도를 파악해 도구(**move · describe · ask**) 하나를 고르고, 코드가 규칙(R1 ~ R5)으로 확정한다.
move 면 **시뮬레이터** 의 로봇이 움직이고, describe 면 장면을 설명하고, ask 면 되묻는다.
프롬프트는 키보드로 입력하거나, **제스처만으로**(주먹 → 방향 → 손가락 개수 → 손 내리기) 입력할 수 있다.

라즈베리파이 연동(카메라 스트리밍 · 음성 · GPIO · 온디바이스 LLM)은 포함하지 않는다.
`연동` 탭은 화면(기기 등록 · 기기별 대시보드 탭)만 동작한다.

## 2026-10-22 명세서 1·2·3 수행 결과

### Furniture 최종 test 평가 완료

최신 18장 PPT와 PJT01·02·03 제출 ZIP v2는 `output/submission_v2/` 및 GitHub 릴리스 `backup-2026-10-22-submission-v2`에 보관한다. 생성 코드는 `scripts/update_submission_presentation.mjs`와 `scripts/package_submission_v2.py`다. 릴리스의 영문 다운로드 이름에 대응하는 원래 한글 파일명·복원 경로·SHA-256은 `results/backup_manifest_20261022_submission_v2.json`에 있다. 기존 시연 영상은 초기 촬영본이며 최신 변경은 ZIP의 화면·검증 기록에 반영했다.

최종 평가 코드·valid/test 비교·박스 위치 비교 이미지는 Git 태그 `backup-2026-10-22-final-test`에 보관한다. 파일별 크기·SHA-256과 고정 가중치·분할 해시는 `results/backup_manifest_20261022_final_test.json`을 참조한다. 백업 과정에서 추론이나 학습을 다시 실행하지 않았다.

이후 best.pt를 변경하지 않고 고정 test87장을 최종 평가했다. 기존 valid85장 결과를 같은 평가기로 재현했으며, test mAP50은99.50%, mAP50–95는89.50%, conf0.25·IoU0.5의 Precision/Recall은 각각100%다. valid mAP50–95 90.55%보다 약1.05%p 낮으며 Table의 test mAP50–95는82.91%다. 데이터·가중치 해시는 보존했고 test를 보고 튜닝하지 않았다. 상세 지표·한계·박스 사례는 `results/furniture_final_test_20261022/README.md`에 있다. **test87장은 이제 최종 평가에 사용한 데이터**이며 아래의 'test 미사용' 표현은 이전 실험 당시의 기록이다.

### 후속 F206 보강

이번 후속 코드·검증 기록은 Git 태그 `backup-2026-10-22-optimization`으로 보관한다. 파일별 SHA-256은 `results/backup_manifest_20261022_optimization.json`에 있다. Furniture 연결, F206 전후 비교, 캐시·단순 질문 최적화, VLM 크기·토큰 실험 및 최종 조건부 정책 검증을 포함한다. 학습 best.pt·last.pt와 당시 PPT·시연 영상·제출 ZIP은 기존 `backup-2026-10-22-specs` 릴리스에서 복원한다. 기존 제출물은 이번 후속 코드를 반영해 재생성한 버전이 아니라 당시 제출물 스냅샷이다.

후속 VLM 입력·토큰 실험은 `results/vlm_settings_20261022/README.md`에 있다. 실제 새 추론 비교 후 고확신 Chair/Sofa는 420px, 테이블·다른 클래스·불확실한 이미지는 448px를 유지하는 정책을 적용했다. 출력 상한은 60토큰이다. 6장 캐시 없는 전후 비교 평균은 6.223초→5.393초(13.34% 감소)였으며, 소규모 실험으로 일반화 품질을 보장하지 않는다. `CORE_VLM_MAX_SIDE`, `CORE_VLM_MAX_TOKENS`, `CORE_VLM_ADAPTIVE`, `CORE_VLM_DETAIL_SIDE`로 변경할 수 있다.

후속 시간 최적화: `results/optimization_20261022/README.md` 참조. 같은 테이블의 warm API 3회 중앙값은 9.705초에서 7.272초로 줄었다(캐시 제외). F206이 최종 답변을 구성하는 단순 장면 질문에서 사용하지 않는 LLM 생성을 생략하고, 동일 이미지 VLM 결과에 최대 8개·60초 메모리 캐시를 적용했다. 단계별 550ms 강제 대기도 제거했다. 이동/복합 의도는 기존 LLM 경로를 유지한다. 캐시 적중 시간은 새 프레임 성능과 구분한다.

`perception_consistency.py`와 대시보드에 출처·불일치 처리를 추가했다. 서로 다른 클래스 박스의 IoU가 0.8 이상이면 원시 검출은 보존하되 해당 후보를 확정 개수에서 제외하고 종류·개수 미확정을 표시한다. 높은 confidence만으로 종류를 정하지 않는다. 명시된 YOLO/VLM 개수가 다르면 불일치를 표시하며, VLM이 언급하지 않은 개수는 0이 아니라 미상으로 취급한다. 현재 명시 개수 파서는 Chair/Sofa/Table 및 한국어 별칭과 숫자·한/두/세/네 표현을 지원하며, 자유로운 모든 문장의 의미를 판정하는 기능은 아니다.

장면 설명 답변은 서버가 `[YOLO]`, `[VLM]` 원문 근거를 붙인 형식으로 구성해 출처 표시를 보장한다. 충돌 시 불확실성과 재확인 안내를 추가하며 move/ask 규칙은 유지한다. 겹치는 실제 물체도 모호 후보가 될 수 있으므로 이 기준은 중복 제거 정답 판정이 아닌 보수적인 불확실성 표시다.

같은 테이블 사진의 실제 대시보드 전후 비교는 `results/f206_20261022/comparison.json`, 변경 후 화면은 `results/f206_20261022/after/Table.png`에 있다. 원시 모델은 여전히 Sofa 0.676·Table 0.526을 검출하지만 최종 답변은 두 물체로 합산하지 않는다. 기존 제출물과 완료 기록은 당시 상태로 보존했다.

실행: `powershell -ExecutionPolicy Bypass -File scripts/start_furniture_dashboard.ps1` → `http://127.0.0.1:8003`.
규칙 검사: `.venv/Scripts/python.exe scripts/test_perception_consistency.py`.

광주 5반 임나경. Ballie와 SmartThings를 참고한 집사형 로봇 콘셉트로 명세서의 필수 기능을 순서대로 실행·검증했다. 웹캠을 공급하기 어렵다는 조건에 따라 Furniture와 제공된 손 이미지를 입력으로 사용했다. 물리 로봇 주행이나 실제 SmartThings 기기 제어는 후속 연동 범위다.

| 단계 | 수행 내용 | 검증 결과 |
|---|---|---|
| 명세서 1 | 모델 선정 근거, conf·시간·메모리 측정, VLM 프롬프트 비교, PoC 순차·병렬 측정, Furniture 10 epoch 파인튜닝 | 같은 valid 85장 mAP50 0.626 → 0.980, 클래스 평균 recall(conf 0.25) 0.487 → 0.988 |
| 명세서 2 | YOLO 요약·VLM 출력 규격, MediaPipe 손 방향·손가락 개수, 이미지 입력과 LLM 답변 연결 | 방향·반전 16/16, 손가락 개수 16/16, 실제 브라우저에서 손 이미지 기반 move(up, 2) 확인 |
| 명세서 3 | A1~A5·R1~R5 설계·검증, 도구 호출, 되묻기와 시뮬레이터 | 최종 API 64/64, 추가 규칙 검사 17/17, 브라우저의 ask·이동·벽/경계 정지 확인 |

전후 평가는 COCO의 chair/couch/dining table을 Furniture의 Chair/Sofa/Table로 명시적으로 대응시키고, 같은 평가 코드와 분할을 사용했다. Table의 범위와 dining table의 의미는 완전히 같지 않으므로, 이 비교를 세 클래스에 맞춘 참고 기준으로 해석한다. 선별된 단일 가구 사진의 검증 성능이며 복잡한 실내 장면 성능은 별도 검증해야 한다. test 87장은 학습·이번 평가에 사용하지 않았다.

- 실행 기록: `results/spec_workflow_20261022/`의 spec1·spec2·spec3 폴더
- API 설계: `API_설계.md`
- 학습 가중치: `source/2회차_day1/runs/furniture_spec1_20261022/weights/best.pt`
- 제출물: `output/submission/`의 최종 PPTX 및 PJT01·02·03 ZIP
- 회차별 필수·심화 상태: `results/spec_workflow_20261022/completion.json`

현재 대시보드는 `http://127.0.0.1:8002`에서 확인한다. **예제 소파** 또는 **이미지 선택**으로 입력하고 질문을 전송한다. **카메라 사용**을 누르면 웹캠 입력으로 전환한다. 실제 카메라의 조명·흔들림·실시간 제스처 시퀀스는 이번 정지 이미지 실험으로 검증하지 않았다.

```powershell
Set-Location C:\work\core_pjt
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8002
# 다른 터미널에서 검증
.\.venv\Scripts\python.exe API_검증.py --url http://127.0.0.1:8002
.\.venv\Scripts\python.exe scripts\spec3_rules_validate.py
```

Furniture 학습 가중치를 서버에 연결하려면 시작 전에 다음 환경변수를 지정한다. 기본 COCO 모델은 80개 클래스, Furniture 모델은 Chair/Sofa/Table 3개 클래스를 지원한다.

```powershell
$env:CORE_YOLO_MODEL = 'C:\work\core_pjt\source\2회차_day1\runs\furniture_spec1_20261022\weights\best.pt'
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8002
```

`가위`를 `위` 방향으로 오인하는 문제를 수정했고, ask 뒤 방향만 답하면 LLM이 describe로 잘못 분류해도 코드가 이전 칸 수로 이어받도록 보강했다. 새 장면 질문은 이동으로 바꾸지 않는다. VLM 규격은 모델이 만든 장애물 표기를 보존하며 길이 초과 시 설명 부분에만 생략 표시를 쓴다. 한국어·장애물 표기가 끝내 확보되지 않으면 오류로 처리한다.

아래 2026-10-21 기록은 이전 백업 시점의 이력이다. 10월 22일의 구현·학습 결과는 이번 수행 기록을 따른다.

## 2026-10-21 진행 기록 ― Furniture v2와 1일차 첫 추론

웹캠 대신 [Roboflow Furniture v2](https://universe.roboflow.com/roboflow-100/furniture-ngpea/dataset/2)의 YOLOv11 ZIP을 받아 로컬 이미지로 실습했다.

- **완료:** 이미지 689장(train 454 / valid 161 / test 74) 다운로드, 이미지 디코딩·라벨 형식·대응 관계 검증, 로컬 YAML 연결, 기존 1일차 코드로 YOLO 첫 추론.
- 클래스 번호는 `0: Chair`, `1: Sofa`, `2: Table`이다. SHA-256 기준 동일 이미지 파일 중복은 0개다. 이후 수행한 유사 이미지·촬영 그룹 검수 결과는 아래 파생 데이터 기록을 따른다.
- 기본 `yolo11n.pt`가 샘플에서 confidence 0.10 / 0.25 / 0.60 기준 각각 5 / 3 / 2개를 예측했다. 같은 소파 이미지로 VLM 추론과 PoC 서버의 두 API 응답까지 확인했다. **Furniture 파인튜닝은 아직 실행하지 않았다.** 기존 데모 학습 가중치는 Furniture 학습 결과가 아니다.
- 출처·버전·라이선스·ZIP 해시는 `datasets/roboflow/furniture/v2/provenance.json`, 데이터 검사와 첫 추론 기록은 `results/furniture_day1/validation.json` · `image_manifest.csv` · `inference.json` · `first_inference.jpg`에 있다.

### GitHub 백업과 복구

백업 저장소는 **[YIM551/core_pjt](https://github.com/YIM551/core_pjt) (현재 공개, 사용자 요청으로 공개 유지)**다. 원본 데이터·모델·영상은 **[최초 백업 릴리스](https://github.com/YIM551/core_pjt/releases/tag/backup-2026-10-21)**, 최종 학습용 데이터는 **[데이터 정비 완료 백업 릴리스](https://github.com/YIM551/core_pjt/releases/tag/backup-2026-10-21-curated)**에서 관리한다. 후자의 태그는 VLM·PoC 실행 결과와 데이터 검수까지 포함한 코드 시점이다.

| 위치 | 보관 내용 |
|---|---|
| Git 저장소 | 코드·문서·브라우저 JS/WASM 자산·샘플·실습 결과·데이터셋 출처 및 설정 |
| 릴리스 `furniture.v2-release.yolov11.zip` | 공식 Furniture v2 원본 이미지·라벨·설정 |
| 릴리스 `local-models.zip` | `yolo11n.pt`, 제스처 `.task`, 기존 데모 학습 `.pt` 등 로컬 모델. 프로젝트 상대경로를 유지한 압축 파일 |
| 릴리스 `project-overview.mp4` | 원래 `설명 영상/코어프로젝트2회차설명영상.mp4` |
| 새 릴리스 `furniture.v2-curated-v2.zip` | 최종 학습용 이미지·라벨 565쌍, data.yaml, 고정 분할·검수 대기 목록·출처. 프로젝트 상대경로 보존 |

가상환경·캐시·모델 가중치·원본 데이터 이미지/라벨·ZIP·영상·다운로드 과정의 브라우저 화면은 Git에 넣지 않는다. GB 단위 GGUF 모델은 릴리스에도 넣지 않으며, 아래 **2. 모델 다운로드**의 공식 명령으로 다시 받는다. `data.local.yaml`은 PC 경로에 맞춰 다시 생성한다.

새 환경에서는 저장소를 `C:\work\core_pjt`에 복제하고, 아래 **1. 가상환경과 패키지**에 따라 설치한다. 최초 릴리스의 세 파일과 새 릴리스의 최종 데이터 ZIP을 다운로드한 뒤 다음 위치에 복구한다.

```powershell
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\furniture.v2-release.yolov11.zip" -DestinationPath "C:\work\core_pjt\datasets\roboflow\furniture\v2" -Force
Copy-Item -LiteralPath "$env:USERPROFILE\Downloads\furniture.v2-release.yolov11.zip" -Destination "C:\work\core_pjt\datasets\roboflow\furniture\furniture.v2-release.yolov11.zip"
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\local-models.zip" -DestinationPath "C:\work\core_pjt" -Force
Copy-Item -LiteralPath "$env:USERPROFILE\Downloads\project-overview.mp4" -Destination "C:\work\core_pjt\설명 영상\코어프로젝트2회차설명영상.mp4"
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\furniture.v2-curated-v2.zip" -DestinationPath "C:\work\core_pjt" -Force

& "C:\work\core_pjt\.venv\Scripts\python.exe" "C:\work\core_pjt\scripts\prepare_furniture.py"
& "C:\work\core_pjt\.venv\Scripts\python.exe" "C:\work\core_pjt\scripts\furniture_first_inference.py"
```

첫 명령의 ZIP은 `provenance.json`에 기록된 SHA-256으로 확인할 수 있다. `prepare_furniture.py`는 원본을 보존하며 경로 설정과 검증 보고서를 생성한다. `furniture_first_inference.py`는 기존 1일차 추론 함수를 사용해 샘플 결과 이미지와 JSON을 다시 저장한다.

새 ZIP의 크기·SHA-256·이전 릴리스 의존 파일은 `results/backup_manifest_20261021_curated.json`에 기록했다. 압축 파일 1,136개 항목을 로컬 파일과 해시 비교했다. `v2_curated_v1`은 대체된 중간본이므로 이미지 사본 대신 원본 경로와 해시를 담은 매니페스트를 보관한다. PoC의 `server.json`에 있는 PID와 로그는 과거 실행 기록이며, 복구 후에는 서버를 다시 실행해야 한다.

### Furniture 학습용 파생 데이터 준비 완료

공식 원본은 `datasets/roboflow/furniture/v2`에 그대로 보존했다. 원본 ZIP 내부 파일과의 일치, 작업 전후 전체 원본 파일 SHA-256 일치를 확인했다. 689장 모두 박스가 하나씩 있고 파일 누락·깨진 이미지·좌표 범위 오류는 없지만, 추가 가구가 라벨링되지 않은 사진이 있었다. 기존 valid에는 Chair가, test에는 Table이 없으며 동일 가구의 다른 각도가 train/valid에 함께 들어간 사례도 확인했다.

24개의 이미지 모음 화면에서 689장 전체를 시각 검토하고, 애매한 사례를 포함한 125장을 원본 크기로 추가 확인했다. **565장은 채택, 124장은 추가 검수 대기**로 분리했다. 검수 대기에는 확인된 누락 라벨뿐 아니라 잘린 가구·의자/소파 구분의 불확실성도 포함된다. 기존 추론 샘플 `S217`(Sofa--383)도 왼쪽 의자의 라벨이 없어 학습 세트에서 제외했다. 정답 박스를 임의 생성하지 않았으며, 채택한 라벨은 원본 그대로 복사했다.

최종 학습 설정은 **`datasets/roboflow/furniture/v2_curated_v2/data.yaml`** 이다. `v2_curated_v1`은 검수 중간본이며 `SUPERSEDED.json`으로 대체 상태를 기록했다.

| 새 분할 | Chair | Sofa | Table | 이미지 수 |
|---|---:|---:|---:|---:|
| train | 156 | 113 | 124 | 393 |
| valid | 34 | 24 | 27 | 85 |
| test | 34 | 24 | 29 | 87 |

seed `20261021`, 목표 비율 70/15/15를 사용했다. 반복 가구·제품군, 같은 촬영 공간, 보수적인 유사 이미지 후보를 묶은 뒤 그룹을 쪼개지 않고 클래스별 비율을 맞췄다. 확인한 그룹의 분할 간 겹침과 실제 파일/디코딩 픽셀의 분할 간 동일 해시 중복은 0개다. 모든 클래스가 세 분할에 존재하며 Ultralytics 8.4.164로 565장 전체를 읽고 320×320 입력 텐서로 변환하는 검사도 통과했다.

- `datasets/roboflow/furniture/v2_curated_v2/split_manifest.json`: 원본↔파생 경로, 클래스·촬영 그룹·분할·이미지/라벨 해시. 이후 실험에서 고정할 분할이다.
- 같은 폴더의 `quarantine.json`: 추가 검수할 원본 이미지와 개별 사유. 원본 파일을 이동하거나 삭제하지 않았다.
- 같은 폴더의 `derivation.json`: 검수·스크립트 해시, 라이브러리 버전, seed, 분할 정책과 검증 결과. `SOURCE_README.*.txt`에 원본 출처·라이선스 문구도 보존했다.
- `results/furniture_day1/data_audit`: 원본 해시 목록, 검수용 이미지 모음, 이미지별 검수 결정, 촬영 공간 묶음, 구조 검사 및 로더 검사 기록.

재현 시 기존 파생 디렉터리를 덮어쓰지 않고 새 출력 경로를 지정한다. 검수 JSON과 원본이 현재 기록과 일치해야 한다.

```powershell
Set-Location C:\work\core_pjt
.\.venv\Scripts\python.exe scripts\audit_furniture_structure.py
.\.venv\Scripts\python.exe scripts\build_furniture_curated.py --output datasets\roboflow\furniture\v2_curated_rebuild --seed 20261021
```

이 데이터는 주로 하나의 가구가 선명한 사진을 남긴 첫 파인튜닝 실습용 부분집합이다. 자동화된 시각 검수만으로 모든 누락을 보장할 수는 없다. 방 전체의 여러 가구를 검출하는 성능을 평가하려면 제외된 사진을 추가 라벨링하고 별도 장면 평가 세트를 만들어야 한다. 새 분할 성적을 원래 RF100 벤치마크와 동일하게 해석하지 않는다.

### 다음 작업

1. 아래 명령으로 CPU 1 epoch 학습 연결을 확인한다. 재실행할 때는 기존 학습 결과를 덮어쓰지 않도록 `--name`을 바꾼다.
2. 연결이 확인되면 같은 train/valid로 학습 설정을 비교한다. test는 최종 설정을 정한 뒤 한 번 평가하며, 테스트 점수로 설정을 고르지 않는다.
3. `quarantine.json`의 사진을 라벨링 도구에서 열어 보이는 모든 Chair/Sofa/Table에 박스를 추가하고, 재검수한 새 데이터 버전을 만든다. 기본 COCO 모델과 Furniture 모델은 클래스 체계가 달라 mAP를 그대로 전후 비교하지 않는다.

```powershell
Set-Location C:\work\core_pjt
.\.venv\Scripts\python.exe "source\2회차_day1\page58_파인튜닝_학습\YOLO_파인튜닝_학습.py" `
  --data "C:\work\core_pjt\datasets\roboflow\furniture\v2_curated_v2\data.yaml" `
  --epochs 1 --imgsz 320 --batch 4 --device cpu --name furniture_curated_smoke_20261021
```

## 받은 뒤 폴더 놓기

받은 `2회차_산출물` 폴더는 강의 실습과 같은 **`C:\work\core_pjt`** 에서 실행한다.

- **`C:\work\core_pjt` 가 없으면** : 받은 `2회차_산출물` 폴더 이름을 `core_pjt` 로 바꿔 `C:\work\` 에 둔다.
- **`C:\work\core_pjt` 가 이미 있으면 (강의 수강 시)** : 받은 폴더 안의 파일을 모두 `C:\work\core_pjt` 에 복사한다.
  폴더 이름을 바꾸거나 기존 `core_pjt` 를 지우지 않는다 ― 강의 때 받은 `models\` 와 `.venv` 를 그대로 쓴다.
  `yolo11n.pt` · `models\gesture_recognizer.task` 는 같은 파일이라 덮어써도 된다.
  단, **이 안내(`README.md`)는 `README_산출물.md` 로 이름을 바꿔 복사한다** ― 강의 `README.md` 를 덮어쓰지 않는다.

## 폴더 구성

이 폴더는 강의 실습 폴더 **`C:\work\core_pjt`** 그대로다. 강의 수강 시에는 강의 실습 파일(`README.md` · `source\` · `lecture\`)과 함께 두며,
가상환경(`.venv`)과 모델(`models\`)도 강의 실습과 같은 것을 쓴다.

```
C:\work\core_pjt\
├─ main.py              웹 대시보드 서버 (FastAPI) ― 화면 · YOLO · VLM · LLM API (A1 ~ A5, 규칙 R1 ~ R5)
├─ index.html           대시보드 화면 (연동 · 대시보드 · 시뮬레이터 탭)
├─ mediapipe\           브라우저 제스처 인식 파일 (vision_bundle.mjs · wasm)
├─ yolo11n.pt           YOLO 가중치 (포함)
├─ models\              VLM · LLM · 제스처 모델 가중치 ― 강의와 공용 (아래 2단계)
├─ .venv\               가상환경 ― 강의와 공용 (아래 1단계)
├─ samples\             샘플 이미지 ― sample.jpg (거리 · 버스, API_검증.py 입력) · pointing_up.jpg · victory.jpg (손 제스처)
├─ API_검증.py          서버가 API 설계대로 동작하는지 번호별 PASS / FAIL (아래 5단계)
├─ requirements.txt     파이썬 패키지 (버전 고정)
├─ 명세서\              16-C-2-01 ~ 03 (docx · pdf)
├─ 데이터 포맷\         16-C-2-01 ~ 03 (xlsx)
├─ 설명 영상\           코어프로젝트2회차설명영상.mp4
├─ README.md            (이 파일) ― 강의 core_pjt 에 복사했다면 README_산출물.md
└─ source\ · lecture\   강의 실습 파일 ― 강의 수강 시에만 있다 (그대로 둔다)
```

## 준비물

- Windows 10/11, **Python 3.12** (3.13 이상은 일부 패키지 휠이 없을 수 있다)
- 메모리 16GB 이상 권장, 디스크 여유 약 8GB (가상환경 약 1.2GB + 모델 약 5.8GB)
- 웹캠, Chrome 또는 Edge
- 인터넷 (패키지 · 모델 설치)
- GPU 없이 CPU 로 동작한다

---

## 1. 가상환경과 패키지 (터미널 1)

PowerShell 을 열고 `C:\work\core_pjt` 로 이동한다. 아래 명령은 **한 줄씩** 그대로 입력한다.
강의 때 만든 `.venv` 가 이미 있으면 `python -m venv .venv` 는 건너뛰고 activate 부터 한다.

```powershell
cd C:\work\core_pjt

python --version
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

- 프롬프트 앞에 `(.venv)` 가 보이면 활성화된 것이다.
- `activate` 에서 "스크립트를 실행할 수 없으므로" 오류가 나면 한 번만 실행 후 다시 activate :
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
- 설치는 약 3분 걸린다 (torch 가 가장 크다).

## 2. 모델 다운로드 (터미널 1 계속)

모델은 강의 실습과 같은 **`C:\work\core_pjt\models`** 에서 읽는다 (강의 `설치_명령어.sh` 와 같은 위치).
강의 때 받아 둔 네 파일이 이미 있으면 이 단계는 건너뛴다.
없는 파일만 1단계의 가상환경이 켜진 터미널(`C:\work\core_pjt`)에서 받는다. `hf` 명령은 1단계에서 함께 설치된다.

```powershell
hf download ggml-org/Qwen2.5-VL-3B-Instruct-GGUF Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf --local-dir models
hf download ggml-org/Qwen2.5-VL-3B-Instruct-GGUF mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf --local-dir models
hf download Qwen/Qwen3-4B-GGUF Qwen3-4B-Q4_K_M.gguf --local-dir models
curl.exe -L -o models\gesture_recognizer.task https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task
```

받은 뒤 `C:\work\core_pjt\models\` 에 아래 네 파일이 있어야 한다.

| 파일 | 크기 | 용도 |
|---|---|---|
| Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf | 1.9 GB | VLM 본체 (장면 설명) |
| mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf | 1.3 GB | VLM 비전 프로젝터 ― 본체와 둘 다 있어야 이미지를 본다 |
| Qwen3-4B-Q4_K_M.gguf | 2.5 GB | LLM (의도 파악 · 도구 선택) |
| gesture_recognizer.task | 8 MB | 손 제스처 모델 (서버가 브라우저에 내준다) |

- `models\.cache` 폴더는 다운로드 도구가 만든 것이다. 그대로 둬도 된다.
- PowerShell 에서는 `curl` 이 아니라 반드시 `curl.exe` 로 쓴다.
- YOLO 가중치(`yolo11n.pt`)는 폴더에 들어 있다.

## 3. 서버 실행 (터미널 2)

**새 PowerShell 창**을 하나 더 열고, 가상환경을 켠 뒤 uvicorn 으로 서버를 띄운다.

```powershell
cd C:\work\core_pjt
.venv\Scripts\activate
uvicorn main:app --host 127.0.0.1 --port 8000
```

`Uvicorn running on http://127.0.0.1:8000` 이 보이면 준비된 것이다. 이 창은 띄운 채로 둔다 (끄려면 `Ctrl+C`).
모델은 첫 요청 때 올라오므로 서버 자체는 바로 뜬다.

- 요청이 오면 서버 창에 `[yolo]` · `[vlm ]` · `[tool]` 로 한 줄씩 찍힌다. `[tool]` 줄에서 질문 → 고른 도구 → 인자 → 답변을 볼 수 있다.
  ```
  [tool] 시작 18:06:10    3364 ms  Q. 오른쪽으로 3칸 가 → move {'direction': 'right', 'steps': 3}  오른쪽으로 3칸 이동합니다.
  ```
- `python main.py` 로 띄워도 같은 서버가 뜬다 (이때는 `Uvicorn running ...` 문구가 나오지 않는다).

## 4. 브라우저로 접속

Chrome / Edge 에서 **http://127.0.0.1:8000** 을 연다. (html 파일을 더블클릭해서 열면 API 와 제스처 인식이 동작하지 않는다)

1. 왼쪽 `대시보드` 탭 → `로컬 PC`
2. 카메라 권한을 **허용** 하면 `카메라 스트리밍` 칸에 웹캠 영상이 뜬다

## 5. 사용 방법

### 키보드로 질문

프롬프트 입력창에 질문을 쓰고 `[전송]`.

| 예 | 동작 |
|---|---|
| `앞에 뭐가 있어?` | describe ― 스냅샷 → YOLO · VLM · 제스처 인식 → LLM 이 장면을 설명 (로봇은 움직이지 않는다) |
| `오른쪽으로 3칸 가` | move(right, 3) ― 시뮬레이터 로봇이 오른쪽으로 3칸 이동 |
| `이쪽으로 2칸 가` + 손으로 방향 가리키기 | 질문에 방향어가 없으면 스냅샷의 손 방향으로 이동 |
| `왼쪽으로 2칸 가` + 손은 위 | 질문의 방향어가 손보다 우선 ― move(left, 2) |
| `저쪽으로 2칸 가` (손 없음) | ask ― `[추가 정보 요청] 어느 쪽으로 2칸 갈까요?` 로 되묻는다 |
| (되묻기 뒤) `아래` | 방향만 답해도 앞서 말한 칸 수로 이동 ― move(down, 2) |

진행바 `1.프롬프트+캡처 → 2.분석중 → 3.추가정보 요청중 → 4.답변생성 → 5.이동중` 으로 단계가 보인다.
describe 면 `5.이동중` 을 건너뛰고, ask 면 `3.추가정보 요청중` 에서 다음 전송을 기다린다.

LLM 에는 출처별 Text 가 들어간다 ― `[YOLO 객체 인식] person 3개, bus 1개` · `[VLM 장면 설명] 한국어 한 문장, 장애물 있음/없음.` ·
`[손 제스처] 가리키는 방향: 위` (손이 없으면 `손 없음`, 방향을 판단할 수 없으면 `인식 불가`).
개수는 YOLO, 상황은 VLM, 방향은 프롬프트 방향어 → 이전 턴 질문 → 손 제스처 순서로 따른다 (LLM 이 고른 방향은 쓰지 않는다).

### 제스처만으로 입력 (로컬 PC)

카메라 앞에서 아래 순서로 한다. 주먹을 쥔 뒤 **5초 안에** 끝내야 한다.

1. **주먹** 을 잠깐 유지 → 입력창이 강조되고 "제스처 기반 프롬프트 입력중" 표시
2. **검지로 방향** (위 · 아래 · 왼쪽 · 오른쪽) 을 가리킨다 → 입력창에 `오른쪽으로,` 처럼 써진다
3. **펼친 손가락 개수**(1 ~ 5) 로 칸 수를 보인다 → `오른쪽으로, 3칸 이동.`
4. **손을 화면 밖으로** 빼면 자동 전송된다

화면은 셀카처럼 좌우가 뒤집혀 보인다 ― 화면에 보이는 방향 그대로 가리키면 된다.

### 시뮬레이터

왼쪽 `시뮬레이터` 탭. 8x8 격자, 로봇은 (1, 1) 에서 출발한다.
벽 19칸은 페이지를 열 때마다 무작위로 생기고(모든 빈칸에 갈 수 있는 배치만), 벽 · 격자 끝에 막히면 그 자리에서 멈춘다.
이동 기록은 `이동 경로 로그` 에 남는다.

### API 검증 (터미널 1)

서버가 뜬 상태에서 1단계 터미널로 돌아와 실행한다.

```powershell
python API_검증.py --quick    # 모델 추론 없이 화면 · 파일 · 오류 응답만 (몇 초)
python API_검증.py            # 전체 ― 인식 · 도구 선택 · 되묻기까지 (약 2분)
```

마지막 두 줄이 아래와 같으면 설계대로 동작하는 것이다 (`--quick` 은 `전체 9/9 PASS`).

```
A1 1/1  A2 2/2  A3 3/3  A4 3/3  A5 18/18  R1 10/10  R2 10/10  R3 5/5  R4 10/10  R5 2/2
전체 64/64 PASS
```

FAIL 이 있으면 번호(A1 ~ A5, R1 ~ R5)를 맨 아래 표에서 찾는다.

---

## 처리 시간 (CPU 참고값)

실측 : Intel i5-11400 (6코어), 메모리 32GB, 웹캠 640x480

| 단계 | 시간 |
|---|---|
| 1단계 패키지 설치 | 약 3분 |
| 2단계 모델 다운로드 (5.8GB) | 약 2분 (회선 속도에 따라 다름) |
| 첫 [전송] (모델 로딩 포함) | 약 30초 |
| 두 번째부터 [전송] 한 번 | 약 20초 (VLM 설명이 가장 오래 걸린다) |
| `python API_검증.py` 전체 | 약 2분 |

PC 성능에 따라 다르다. 처리 중에는 입력창이 잠기고 `⏳ 처리 중` 이 표시된다.

## 자주 겪는 문제

| 증상 | 원인 · 해결 |
|---|---|
| `pip install` 중 llama-cpp-python 빌드 오류 | `--extra-index-url ...` 를 빼먹었다. 1단계 명령을 그대로 다시 실행 |
| `hf` 를 찾을 수 없음 | 가상환경이 꺼진 터미널이다. `.venv\Scripts\activate` 후 다시 실행 |
| `[Errno 10048]` (8000 포트 사용 중) | 이미 다른 서버가 떠 있다. 그 창에서 `Ctrl+C`, 또는 `--port 8001` 로 띄우고 8001 로 접속 (`API_검증.py --url http://127.0.0.1:8001`) |
| `API_검증.py` 가 "서버에 연결할 수 없습니다" | 터미널 2 에서 서버를 먼저 띄운다 |
| 카메라 칸이 "카메라 접근 권한이 거부됨" | 주소창 왼쪽 자물쇠 → 카메라 허용 후 새로고침. 다른 프로그램이 웹캠을 쓰고 있으면 끈다 |
| VLM 답변이 "VLM 분석 오류" | `C:\work\core_pjt\models\` 에 VLM 본체와 mmproj 두 파일이 모두 있는지 확인 |
| LLM 답변이 "LLM 답변 생성 중 오류" | `C:\work\core_pjt\models\Qwen3-4B-Q4_K_M.gguf` 확인 |
| 서버 창에 `[vlm ] 규격 벗어남 (...)` | VLM 출력이 한국어 · 40자 · '장애물 있음/없음' 규격을 벗어났다는 기록이다. 글자를 자르지 않고 그대로 쓴다 (가끔 한자가 섞인다) |
| 서버 창에 `add_text:` · `image slice encoded` 같은 줄 | VLM 라이브러리가 찍는 진행 기록이다. 무시해도 된다 |
| 제스처 입력이 시작되지 않음 | 처리 중에는 새 제스처를 받지 않는다. 손 전체가 화면에 들어오게 하고 주먹을 0.5초 정도 유지 |
| `오른쪽에 있는 게 뭐야?` 에 되묻기(`[추가 정보 요청]`)가 나온다 | 질문에 방향어(오른쪽)가 있어 LLM 이 이동 요청으로 볼 때가 있다. 로봇은 움직이지 않는다. `오른쪽에 뭐가 보여?` 처럼 묻거나 그냥 다시 질문한다 |
| `오른쪽으로 3칸 가` 인데 로봇이 덜 간다 | 벽 · 격자 끝에 막히면 그 자리에서 멈춘다 (이동 경로 로그 확인). 막힌 사실은 서버로 전달되지 않아 답변은 '3칸 이동' 으로 나온다 |
| PC 가 느려짐 | 정상 ― VLM · LLM 이 CPU 코어를 모두 쓴다 |

## 강의 실습 코드와 다른 점

- **서버 파일** : `main.py` 는 3일차 실습 4-1(`C:\work\core_pjt\source\2회차_day3\page39_대시보드_완성\대시보드_완성.py`)과 같은 코드에서 출발했다. 경로는 이 폴더(`C:\work\core_pjt`) 기준이고, 방향 결정은 명세 16-C-2-03 개선안대로 바꿨다 (`resolve_direction` ― 프롬프트 방향어 → 이전 턴 질문 → 손 제스처, LLM 이 고른 방향은 쓰지 않음).
- **VLM 출력 검사** : 2일차 실습 1-2 의 `normalize` · `check` 를 서버에 넣었다. 규격을 벗어난 출력은 서버 창에 기록만 하고 자르지 않는다.
- **화면** : `index.html` 은 `C:\work\core_pjt\source\2회차_web\index.html` 과 같은 파일이다.

## 참고 ― API · 규칙 번호

| 번호 | 메서드 | 경로 | 요청 → 응답(200) / 오류 |
|---|---|---|---|
| A1 | GET | `/` | 대시보드 화면(index.html) |
| A2 | GET | `/mediapipe/...` | 브라우저 제스처 인식 파일(vision_bundle.mjs, wasm, gesture_recognizer.task) / 404 |
| A3 | POST | `/api/yolo-detect` | JPEG 바이트 → `{"objects": [{label, confidence, box}]}` / 400 `empty_image` · `invalid_image`, 500 `yolo_failed` |
| A4 | POST | `/api/vlm-describe` | JPEG 바이트 → `{"description": 한 문장 + 장애물 있음/없음}` / 400 `empty_image` · `invalid_image`, 500 `vlm_failed` |
| A5 | POST | `/api/llm-answer` | `{prompt, yolo_summary, vlm_description, gesture_direction, history}` → `{tool, args, need_more_info, message, user_content}` / 400 `invalid_json` · `empty_prompt`, 500 `llm_failed` |

| 번호 | 규칙 | 내용 (보장하는 함수) |
|---|---|---|
| R1 | 도구 이름 보장 | tool 은 항상 move · describe · ask 중 하나. JSON 이 깨지거나 없는 도구면 describe (`parse_tool_call`) |
| R2 | 도구 인자 보장 | move 의 direction 은 네 방향 중 하나, steps 는 1 ~ 10 정수(범위 밖은 잘라냄). 방향 없는 move 는 ask (`parse_tool_call`, `to_steps`) |
| R3 | 방향 근거 확인 | 방향은 프롬프트 방향어 → 이전 턴 질문 → 손 제스처 순서로 정하고, LLM 이 고른 방향은 쓰지 않는다. 셋 다 없으면 move 를 ask 로 바꾸고, 이미 아는 칸 수는 args.steps 에 담는다 (`apply_rules`, `resolve_direction`, `previous_direction`) |
| R4 | 추가 정보 표시 | need_more_info 는 tool 이 ask 일 때만 true (`llm_answer`) |
| R5 | 되묻기 이어가기 | ask 라도 방향 근거(R3)가 있으면 move 로 바꾼다. 칸 수는 질문 → ask 가 기억한 값 → LLM 순서 (`apply_rules`, `pending_steps`) |

API_검증.py 의 A5 세부 항목 : A5-1 장면 질문 → describe · A5-2 방향 · 칸 수 → move · A5-3 손 방향으로 move ·
A5-4 제스처 시퀀스 문구 → move · A5-5 프롬프트 방향어가 손 제스처보다 우선 · A5-6 이전 턴 질문이 손 제스처보다 우선.

A5-6 은 방어용 항목이다. 화면에서는 방향어가 있는 질문이 R3 로 항상 move 가 되고 history 에는 ask 로 끝난 턴만 남으므로,
'방향어가 든 이전 턴' 은 실제로 전달되지 않는다. 우선순위(프롬프트 방향어 → 이전 턴 질문 → 손 제스처) 구현만 확인하려고 그런 history 를 직접 만들어 보낸다.

- `gesture_direction` 은 `up` · `down` · `left` · `right`, 손이 없으면 `none`, 방향을 판단할 수 없으면 `unknown`.
- 대화 기록(`history`)은 브라우저가 보관해 요청에 담아 보낸다 ― 서버는 저장하지 않는다.

## 2026-10-22 GitHub 백업 및 복구

명세서 1·2·3 코드와 검증 기록, 학습 CSV·설정, 최종 PPT와 시연 영상 3개는 이 커밋에 보관한다.
[제출·학습 결과 릴리스](https://github.com/YIM551/core_pjt/releases/tag/backup-2026-10-22-specs)에는 학습 가중치와 제출물을 다음 8개 파일로 보관한다.

- `furniture-spec1-20261022-training.zip`: 프로젝트 루트에 압축 해제하면 학습 결과와 `weights/best.pt`, `weights/last.pt` 복원
- `home-butler-presentation-20261022.pptx`: 최종 PPT 원본
- `pjt01-demo-20261022.webm` ~ `pjt03-demo-20261022.webm`: 실제 브라우저 시연 영상
- `PJT01_Gwangju_5_ImNagyeong.zip` ~ `PJT03_Gwangju_5_ImNagyeong.zip`: 제출 ZIP 원본, 내용과 바이트 변경 없음

릴리스 파일명은 다운로드 호환성을 위해 영문으로 표시한다. 원래 한글 파일명·복원 경로·크기·SHA-256은 `results/backup_manifest_20261022_specs.json`의 `restore_to`를 따른다.
저장소를 clone한 뒤 학습 ZIP을 루트에 풀고 README의 환경 설치 명령을 실행한다. 원본 데이터·기본 모델은 `backup-2026-10-21`, 학습 데이터 565쌍은 `backup-2026-10-21-curated` 릴리스를 함께 사용한다. GGUF 모델과 가상환경은 기존 공식 다운로드·설치 절차로 준비한다.
