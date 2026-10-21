# 웹 대시보드 서버 API 설계 (2회차 3일차)

- 화면: `../2회차_web/index.html` (완성본 제공, 수정하지 않는다)
- 서버: `page39_대시보드_완성/대시보드_완성.py` (이 문서대로 만든 완성본)
- 확인: `page16_API_검증/API_검증.py` 가 이 문서의 번호별로 PASS / FAIL 을 찍는다 (43개 항목)
- 코드와의 대응: 서버 주석의 `[A1]` ~ `[A5]`, `[R1]` ~ `[R5]` 가 이 문서의 번호다

## 0. 전체 흐름

```
[전송] ─▶ 웹캠 스냅샷 1장
          ├─ POST /api/yolo-detect   (A3) ─▶ 객체 목록  ─┐
          ├─ POST /api/vlm-describe  (A4) ─▶ 장면 문장  ─┼─▶ POST /api/llm-answer (A5)
          └─ 브라우저 MediaPipe (A2)     ─▶ 손 방향    ─┘        │
                                                               ▼
                                        tool = move     → 시뮬레이터 로봇 이동
                                        tool = describe → 답변만 표시
                                        tool = ask      → 되묻고, 다음 전송에서 이어서 처리
```

**역할 분담** ― 인식은 모델이, 의도 판단(도구 선택)은 LLM 이, 규칙 보장은 코드가, 도구 실행은 화면이 한다.

## 1. 엔드포인트

| 번호 | 메서드 · 경로 | 요청 | 응답 (200) | 오류 |
|---|---|---|---|---|
| A1 | `GET /` | ― | `index.html` | ― |
| A2 | `GET /mediapipe/...` | ― | 브라우저 제스처 인식 파일 (`vision_bundle.mjs`, `wasm/*`, `gesture_recognizer.task`) | 404 |
| A3 | `POST /api/yolo-detect` | 본문 = JPEG 바이트 | `{"objects": [{"label", "confidence", "box"}]}` | 400 `empty_image` · `invalid_image`, 500 `yolo_failed` |
| A4 | `POST /api/vlm-describe` | 본문 = JPEG 바이트 | `{"description": str}` | 400 `empty_image` · `invalid_image`, 500 `vlm_failed` |
| A5 | `POST /api/llm-answer` | JSON (2절) | JSON (3절) | 400 `invalid_json` · `empty_prompt`, 500 `llm_failed` |

- 오류 응답은 모두 `{"error": "<코드>"}` 다. 화면은 코드만 보고 안내 문구를 띄운다.
- A3 `objects[i]` : `label` 문자열, `confidence` 0~1, `box` = 보낸 이미지의 픽셀 좌표 `[x1, y1, x2, y2]`. 객체가 없으면 빈 배열.
- A4 `description` : 2일차 실습 1-2 규격 (긴 변 448px, 40자 한 문장 + 장애물 있음/없음).
- A1 ~ A4 는 2일차 대시보드 서버와 같다. **오늘 바뀌는 것은 A5 하나다.**

## 2. A5 요청

```json
{
  "prompt": "오른쪽으로 3칸 가",
  "yolo_summary": "person 3개, bus 1개",
  "vlm_description": "버스 앞에 두 명의 사람이 서 있습니다, 장애물 없음.",
  "gesture_direction": "unknown",
  "history": []
}
```

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `prompt` | O | 사용자 질문. 공백뿐이면 400 `empty_prompt` |
| `yolo_summary` | | A3 결과를 화면이 2일차 Part 1 규격(`이름 N개`)으로 요약한 것 |
| `vlm_description` | | A4 결과 |
| `gesture_direction` | | 스냅샷의 손 방향 `up` · `down` · `left` · `right` · `unknown` (그 외 값은 `unknown`) |
| `history` | | 되묻기(ask) 뒤의 후속 턴일 때만 채워진다. `[{"role": "user"|"assistant", "content": str}]` |

`source`, `ip` 필드도 함께 오지만 3회차(라즈베리파이) 용이라 이번 서버는 쓰지 않는다.

## 3. A5 응답 ― 도구 호출

```json
{
  "tool": "move",
  "args": {"direction": "right", "steps": 3},
  "need_more_info": false,
  "message": "오른쪽으로 3칸 이동합니다.",
  "user_content": "[YOLO 객체 인식] ...\n[VLM 장면 설명] ...\n[손 제스처] 가리키는 방향: 인식 불가\n\n[사용자 질문] 오른쪽으로 3칸 가"
}
```

| tool | 의도 | args | 화면 동작 |
|---|---|---|---|
| `move` | 이동 (`오른쪽으로 3칸 가`) | `{"direction": up|down|left|right, "steps": 1~10}` | 시뮬레이터 로봇을 `direction` 으로 `steps` 칸. 벽 · 경계에서 멈춘다 |
| `describe` | 장면 질문 (`앞에 뭐 있어?`) | `{}` | 답변만 표시. 이동 단계는 건너뜀 |
| `ask` | 이동하라는데 방향을 모름 (`저쪽으로 가`) | `{}` 또는 `{"steps": 이미 아는 칸 수}` | `[추가 정보 요청]` 표시, 대화 기록을 보관했다가 다음 전송에 함께 보낸다 |

- `user_content` : 이번 턴에 LLM 에 실제로 넣은 입력. 화면이 대화 기록(history)에 그대로 붙인다.
- 화면은 assistant 턴을 `{"tool", "args", "message"}` JSON 으로 기록한다 ― 그래서 ask 의 `args` 가 다음 턴까지 전달된다.

## 4. 규칙 ― LLM 이 틀려도 코드가 보장한다

| 번호 | 규칙 | 보장하는 곳 |
|---|---|---|
| R1 | `tool` 은 항상 `move` · `describe` · `ask` 중 하나. JSON 이 깨지면 `describe`, 없는 도구도 `describe` | `parse_tool_call` |
| R2 | 도구별 인자 형식. `move` 의 `direction` 은 네 방향 중 하나, `steps` 는 1~10 정수(범위 밖은 잘라냄). 방향 없는 `move` 는 `ask` | `parse_tool_call`, `to_steps` |
| R3 | 방향의 근거(질문의 방향어 ― 이전 턴 포함 ― 또는 손 제스처)가 없으면 `move` 를 `ask` 로 바꾼다. LLM 이 스스로 고른 `ask` 도 같은 형식으로 맞춘다. 이미 아는 칸 수는 `args.steps` 에 담는다 | `apply_rules`, `has_direction_evidence` |
| R4 | `need_more_info` 는 `tool == "ask"` 와 같다 | `llm_answer` |
| R5 | `ask` 뒤에 사용자가 방향만 답하면(`왼쪽`), LLM 이 무엇을 고르든 `move` 로 바꾸고 칸 수는 `ask` 가 기억한 값을 쓴다. 방향은 질문의 방향어가 LLM 보다 우선한다 | `apply_rules`, `pending_steps` |

**R3 · R5 가 코드에 있는 이유 (실측, Qwen3-4B CPU)**

- 프롬프트만으로는 8문항 중 6문항. `저쪽으로 가`, `버스 있는 쪽으로 가` 를 모두 `move(right, 1)` 로 추측했다.
- 규칙을 프롬프트에 두 가지 방식으로 더해도 그대로 6/8 (도전 1).
- 되물은 뒤 `왼쪽` 이라고만 답하면 LLM 은 칸 수를 1 로 되돌렸다. 기억은 LLM 이 아니라 코드가 한다.

→ **조건 분기는 LLM 에 맡기지 않고 코드로 보장한다** (2일차 "형식은 파서가 보장한다" 의 연장).

## 5. 3회차로 넘기는 것

2일차 이전 대시보드에 있던 `/api/camera-stream`, `/api/robot-signal`, `/api/voice-poll`, `/api/oled-display` 는 라즈베리파이 연동용이라 이번 서버에 없다. 이번에는 **"로컬 PC" 탭과 시뮬레이터만** 쓴다.

- 이동 결과(벽에 막혀 몇 칸만 갔는지 등)는 화면만 알고 서버로 돌려보내지 않는다. 결과를 LLM 에 되돌려 주는 것(move_result)은 3회차에서 다룬다.
- 화면의 "연동" 탭은 3회차용이다. 이번에는 쓰지 않는다.
