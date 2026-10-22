# Furniture best.pt 최종 test 평가

고정 test 87장을 최종 평가에 사용했다. 이후 이 test는 미사용 데이터가 아니며 모델·설정·임계값 선택에 사용하지 않는다. 가중치·분할·라벨을 변경하거나 추가 학습하지 않았다.

학습 데이터 565장의 이미지·라벨 해시를 검증했고 train/valid/test 사이 동일 이미지 SHA-256 및 알려진 group_id 중복이 없음을 확인했다. 육안으로 발견하지 못한 유사 장면까지 없음을 보장하는 검사는 아니다. 기존 valid 결과 네 지표를 오차 1e-8 이내로 재현한 후 test를 실행했다. 모델과 분할 매니페스트의 전후 해시도 동일했다.

평가 설정은 기존 valid와 동일하다: imgsz320, CPU, AP 수집 confidence0.001, NMS IoU0.7, max_det300. Precision/Recall은 confidence0.25 및 매칭 IoU0.5에서 계산한 클래스 평균이다. mAP50–95는 IoU0.50부터0.95까지 평가한다. API의 기본 추론 해상도와 이번 고정 평가 해상도를 혼동하지 않는다. F206 후처리 없이 원시 YOLO 검출을 평가했다.

| 지표 | valid 85장 | test 87장 | test−valid |
|---|---:|---:|---:|
| mAP50 | 97.96% | 99.50% | +1.54%p |
| mAP50–95 | 90.55% | 89.50% | −1.05%p |
| Precision(conf0.25, IoU0.5) | 95.34% | 100.00% | +4.66%p |
| Recall(conf0.25, IoU0.5) | 98.77% | 100.00% | +1.23%p |

| 클래스 | test 정답 객체 | valid mAP50–95 | test mAP50–95 |
|---|---:|---:|---:|
| Chair | 34 | 96.14% | 94.06% |
| Sofa | 24 | 83.37% | 91.53% |
| Table | 29 | 92.14% | 82.91% |

운영 지점에서 test TP87·FP0·FN0이며 이미지마다 정답 객체가 하나씩 있다. 이는 이 데이터의 주석과 IoU0.5 기준의 결과로, 모델이 모든 장면에서 완벽하다는 뜻은 아니다. AP와 고정 confidence의 P/R은 다른 계산이며 P/R100%여도 mAP50이99.5%일 수 있다.

더 엄격한 위치 기준에서 conf0.25의 매칭 TP는 IoU0.75에서87개,0.90에서73개,0.95에서38개였다. test의 mAP50은 높아졌지만 mAP50–95는 약1.05%p 낮아졌다. 클래스별로는 Table의 박스 범위가 주석과 어긋나는 영향이 크며, 클래스 인식 성공과 정밀한 경계 일치는 구분해야 한다. 표본이 작고 분포가 달라 이 차이만으로 과적합 유무나 통계적 우열을 단정하지 않는다.

localization_examples.jpg는 클래스별 최저 IoU 사례이며 초록은 주석, 빨강은 예측이다. 소파 예측이 아래쪽을 더 포함하고 테이블 예측은 주석보다 좁게 잡힌다. 이 차이는 주석의 경계 정의에도 영향을 받으므로 모두 잘못된 종류 검출로 해석하지 않는다.

원본이 단일 가구 중심으로 선별된 Furniture 데이터이므로 다중 가구·가림·조명 변화·실제 방·주행 장애물 환경의 성능을 대신하지 않는다. 데이터 정비에서 제외한124장도 이번 평가에 포함하지 않았다. 실제 배포 성능은 앞으로 별도 수집한 외부 이미지로 확인하고, 이번 test 점수에 맞춰 best.pt를 재조정하지 않는다.

파일: evaluation_lock.json(고정 조건·해시), comparison.json(전후 지표), valid_vs_test.csv, test_final_metrics.json, test_final_predictions.json, test_errors.json(운영 지점 오류0건), localization_analysis.json 및 localization_examples.jpg. 원래 valid 기록과 기존 제출물은 보존했다. 스크립트 scripts/final_furniture_evaluate.py는 결과 디렉터리가 존재하면 중단해 최종 평가 기록을 덮어쓰지 않는다.
