# page61 ― 파인튜닝 평가

> 강의자료 **61쪽** (코드) / **62쪽** (동작 결과)

파인튜닝 전/후를 같은 기준으로 비교한다

## 무엇을 하는가

- before(yolo11n.pt) 와 after(best.pt) 를 같은 val 셋으로 평가한다
- mAP50 / mAP50-95 / precision / recall 을 CSV 로 남긴다

## 실행

```bash
cd page61_파인튜닝_평가
python YOLO_파인튜닝_평가비교.py
```

## 확인 포인트

- page56_데이터셋_준비 와 page58_파인튜닝_학습 을 먼저 실행해야 한다
- mAP50 만 보면 안 된다 ― max_conf 가 0.25 보다 낮은 이유를 생각해 본다 (도전 문제 4)

## 이 폴더에 생기는 것

- finetune_compare.csv
- 실행결과.txt ― 실제 실행 출력

---
실제 실행 출력은 `실행결과.txt` 에 그대로 담아 두었다.
막히면 `../README.md` 의 순서표를 먼저 확인할 것.
