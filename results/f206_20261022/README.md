# F206 전후 비교

동일한 Furniture best.pt, 동일한 테이블 이미지 바이트, 동일한 YOLO 원시 검출 및 VLM 설명을 사용했다. 이전 기록은 before.json/before.png, 이후 실제 대시보드 실행은 after/validation.json 및 after/Table.png에 보관했다. 비교 검증의 상세 결과는 comparison.json이다.

| 항목 | 변경 전 | 변경 후 |
|---|---|---|
| 원시 YOLO | Sofa 0.676, Table 0.526 | 동일하게 보존 |
| YOLO→LLM 요약 | Sofa 1개, Table 1개 | 중복 후보: Sofa/Table (종류·개수 미확정) |
| VLM | 테이블 위에 체크무늬 천이 깔려 있다, 장애물 없음. | 동일 |
| 최종 답변 | 소파 1개, 테이블 1개가 보여요. | YOLO/VLM 출처와 중복 후보 표시, 종류·개수 미확정 및 재확인 안내 |

박스 IoU는 0.9369다. 서로 다른 클래스가 IoU 0.8 이상 겹치면 불확실성을 표시하며 후보 개수를 합산하지 않는다. 더 높은 confidence의 Sofa를 정답으로 선택하지 않는다. 이는 검출 모델 자체의 정확도 개선이 아니라 오류를 확정된 사실로 전달하지 않도록 하는 보강이다. 실제로 겹쳐 놓인 물체도 보수적으로 미확정 처리될 수 있다.

YOLO와 VLM이 명시한 Chair/Sofa/Table 개수가 다르면 count_mismatch를 표시한다. VLM이 개수를 말하지 않으면 미상이며 0으로 간주하지 않는다. 따라서 이 테이블 사례는 숫자 불일치가 아니라 겹치는 클래스 후보 문제다. VLM의 장애물 문구는 원문 인용이며 물리적 안전 판정이 아니다.

전후 비교 11/11, F206 규칙 검사 5/5, 기존 도구 규칙 17/17, 실제 서버 API 64/64 통과. 기존 제출 ZIP과 PPT·완료 기록은 수정하지 않았다.

재현: Furniture 서버를 실행하고 `CORE_RESULT_DIR=results/f206_20261022/after`, `CORE_TEST_CLASS=Table` 환경변수로 scripts/furniture_dashboard_validate.mjs를 실행한 뒤 scripts/compare_f206.py로 비교한다. 이전 비교 결과를 보존하려면 별도 결과 디렉터리를 사용한다.
