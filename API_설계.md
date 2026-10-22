# 집사형 로봇 PoC API 설계

명세서 16-C-2-01, 02, 03을 순서대로 확장한 최종 서버는 `main.py`, 화면은 `index.html`이다. 개발 서버는 `http://127.0.0.1:8002`에서 실행했다. 기존 8000 포트의 서버와 구분한다.

## 입력과 처리

사용자는 예제 소파, 로컬 이미지 파일, 웹캠 중 하나를 입력으로 선택한다. 선택한 프레임 하나를 JPEG로 만들어 YOLO·VLM·브라우저 MediaPipe에 함께 전달한다. 객체 개수는 YOLO, 장면은 VLM, 손 방향은 MediaPipe에서 얻고, 출처별 텍스트와 질문을 Qwen3-4B에 보낸다. LLM은 도구를 선택하며, 서버의 규칙이 인자를 확정한다. 화면이 도구 결과에 따라 답변·되묻기·시뮬레이터 이동을 수행한다.

## 엔드포인트

| 번호 | 메서드와 경로 | 요청 | 성공 응답 | 오류 |
|---|---|---|---|---|
| A1 | GET `/` | 없음 | 대시보드 HTML | 없음 |
| A2 | GET `/mediapipe/...` | 없음 | JS·WASM·제스처 모델 | 404 |
| A3 | POST `/api/yolo-detect` | JPEG 본문 | `objects: [{label, confidence, box}]` | 400 `empty_image`, `invalid_image`; 500 `yolo_failed` |
| A4 | POST `/api/vlm-describe` | 같은 JPEG 본문 | `description` | 400 `empty_image`, `invalid_image`; 500 `vlm_failed` |
| A5 | POST `/api/llm-answer` | 질문과 인식 텍스트·손 방향·history | `tool, args, need_more_info, message, user_content` | 400 `invalid_json`, `empty_prompt`; 500 `llm_failed` |
| 확장 | GET `/api/sample-image?name=sofa` | `sofa`, `pointing`, `victory` 중 하나 | 지정된 샘플 JPEG | 404 `sample_not_found` |
| 확장 | GET `/api/health` | 없음 | 상태·YOLO 가중치 파일명·모델 로딩 여부 | 없음 |

오류 본문은 `{"error":"코드"}`로 통일한다. A3 박스는 입력 이미지의 픽셀 좌표다. A4는 긴 변 448px 이하의 이미지를 사용하며, 한국어 40자 이내 한 문장과 모델이 출력한 장애물 표기를 보존한다. 규격 재시도 후에도 한국어·장애물 표기가 없으면 실패로 응답한다. 길이를 줄일 때는 설명 부분에 생략 표시를 하고 장애물 표기를 유지한다.

1번 명세서의 PoC 응답 `summary, elapsed_ms`는 `scripts/spec1_poc_server.py`를 통해 기존 page47 서버에서 별도로 검증했다. 2·3번 최종 서버는 명세서의 확장된 `objects` 형식을 사용한다.

## LLM 요청 예시

```json
{
  "prompt": "이쪽으로 2칸 가",
  "yolo_summary": "chair 1개, couch 1개",
  "vlm_description": "거실에 소파와 의자가 있다, 장애물 있음.",
  "gesture_direction": "up",
  "history": []
}
```

이 예시는 필드 설명을 위한 예시이며 실제 모델 출력은 `results/spec_workflow_20261022/spec3/browser_validation.json`에 별도로 보관했다.

## 코드 규칙

| 번호 | 보장 내용 | 함수 |
|---|---|---|
| R1 | 깨진 JSON·알 수 없는 도구를 describe로 파싱 | `parse_tool_call` |
| R2 | 방향을 네 방향으로 정규화, 칸 수를 1~10 정수로 보정, 방향 없는 move는 ask | `to_direction`, `to_steps`, `parse_tool_call` |
| R3 | 방향 근거 우선순위는 이번 질문, 이전 질문, 손 방향. LLM이 만든 방향은 근거로 사용하지 않음 | `resolve_direction`, `apply_rules` |
| R4 | `need_more_info`는 tool이 ask인 경우에만 true | `llm_answer` |
| R5 | ask 뒤 방향만 답하면 이전 칸 수로 이동. LLM이 describe로 잘못 분류해도 코드가 이어받음 | `pending_steps`, `apply_rules` |

`위 2칸 가`는 방향으로 인식하며 `위치`, `위험`, `가위`는 방향으로 인식하지 않는다. 방향을 되묻던 중에도 `왼쪽에 무엇이 보여?`처럼 새 장면 질문이 들어오면 describe를 유지한다.

## 검증과 실행

```powershell
Set-Location C:\work\core_pjt
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8002
# 다른 터미널
.\.venv\Scripts\python.exe API_검증.py --url http://127.0.0.1:8002
.\.venv\Scripts\python.exe scripts\spec3_rules_validate.py
```

모델 변경은 서버 시작 전에 `CORE_YOLO_MODEL` 환경변수로 지정한다. 기본값은 COCO 사전학습 모델이며, Furniture 학습 결과는 `source/2회차_day1/runs/furniture_spec1_20261022/weights/best.pt`다. 두 모델은 지원 클래스가 다르다.

## 실물 연동 범위

현재 move는 브라우저의 8×8 격자를 이동하며 벽·경계에서 멈춘다. 실제 이동 결과는 브라우저 로그에 남는다. Ballie는 가정용 집사 로봇의 참고 콘셉트다. SmartThings의 디바이스 상태 조회·명령 API 연동은 후속 범위이며, 이번 서버에서 실물 기기 명령을 실행하지 않는다.
