"""Evaluate COCO and Furniture detectors on the same frozen Furniture valid split."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
import torch
from ultralytics import YOLO
from ultralytics.utils.metrics import ap_per_class, box_iou

ROOT = Path(__file__).resolve().parents[1]
NAMES = {0: "Chair", 1: "Sofa", 2: "Table"}


def match(pred_boxes, pred_cls, gt_boxes, gt_cls, thresholds):
    correct = np.zeros((len(pred_boxes), len(thresholds)), dtype=bool)
    if not len(pred_boxes) or not len(gt_boxes):
        return correct
    ious = box_iou(torch.tensor(gt_boxes, dtype=torch.float32),
                   torch.tensor(pred_boxes, dtype=torch.float32)).numpy()
    compatible = np.asarray(gt_cls)[:, None] == np.asarray(pred_cls)[None, :]
    for column, threshold in enumerate(thresholds):
        g, p = np.where((ious >= threshold) & compatible)
        candidates = sorted(zip(g, p), key=lambda pair: -ious[pair])
        used_g, used_p = set(), set()
        for gi, pi in candidates:
            if gi not in used_g and pi not in used_p:
                correct[pi, column] = True
                used_g.add(gi)
                used_p.add(pi)
    return correct


def evaluate(weights, dataset, label, output):
    model = YOLO(str(weights))
    coco = model.names.get(56) == "chair" and model.names.get(57) == "couch"
    mapping = {56: 0, 57: 1, 60: 2} if coco else {0: 0, 1: 1, 2: 2}
    if not coco and list(model.names.values()) != list(NAMES.values()):
        raise ValueError(f"Unexpected trained class mapping: {model.names}")
    manifest = json.loads((dataset / "split_manifest.json").read_text(encoding="utf-8"))
    samples = sorted((r for r in manifest if r["derived_split"] == "valid"), key=lambda r: r["id"])
    stats, predictions = [], []
    threshold_counts = {c: {"tp": 0, "fp": 0, "fn": 0} for c in NAMES}
    started = time.perf_counter()
    for number, row in enumerate(samples, 1):
        path = dataset / row["image"]
        with Image.open(path) as im:
            width, height = im.size
        labels = [list(map(float, line.split())) for line in (dataset / row["label"]).read_text().splitlines() if line.strip()]
        gt_cls = np.asarray([int(v[0]) for v in labels], dtype=int)
        gt = np.asarray([[(v[1]-v[3]/2)*width, (v[2]-v[4]/2)*height,
                          (v[1]+v[3]/2)*width, (v[2]+v[4]/2)*height] for v in labels])
        result = model.predict(path, imgsz=320, conf=0.001, iou=0.7,
                               classes=list(mapping), max_det=300, device="cpu", verbose=False)[0]
        boxes = result.boxes.xyxy.cpu().numpy()
        conf = result.boxes.conf.cpu().numpy()
        cls = np.asarray([mapping[int(c)] for c in result.boxes.cls.cpu().numpy()], dtype=int)
        correct = match(boxes, cls, gt, gt_cls, np.linspace(0.5, 0.95, 10))
        stats.append((correct, conf, cls, gt_cls))
        kept = conf >= 0.25
        correct25 = match(boxes[kept], cls[kept], gt, gt_cls, [0.5])[:, 0]
        for c in NAMES:
            tp = int(correct25[cls[kept] == c].sum())
            fp = int((cls[kept] == c).sum()) - tp
            threshold_counts[c]["tp"] += tp
            threshold_counts[c]["fp"] += fp
            threshold_counts[c]["fn"] += int((gt_cls == c).sum()) - tp
        predictions.append({"id": row["id"], "image": row["image"], "ground_truth": labels,
                            "boxes_xyxy": boxes.tolist(), "confidence": conf.tolist(),
                            "mapped_class_ids": cls.tolist(), "correct_iou50_95": correct.tolist()})
        if number % 20 == 0:
            print(f"{label}: {number}/{len(samples)}", flush=True)
    joined = [np.concatenate([s[i] for s in stats], axis=0) for i in range(4)]
    values = ap_per_class(*joined, names=NAMES, plot=False)
    per_class = []
    for c in NAMES:
        counts = threshold_counts[c]
        tp, fp, fn = (counts[k] for k in ("tp", "fp", "fn"))
        idx = list(values[6]).index(c)
        per_class.append({"class": NAMES[c], "map50": float(values[5][idx, 0]),
                          "precision_at_conf025": tp / max(tp+fp, 1),
                          "recall_at_conf025": tp / max(tp+fn, 1), **counts})
    report = {"model": label, "weights": str(weights), "images": len(samples),
              "split": "valid", "imgsz": 320, "ap_prediction_conf_floor": 0.001,
              "nms_iou": 0.7, "operating_conf": 0.25, "class_mapping": mapping,
              "map50": float(values[5][:, 0].mean()), "map50_95": float(values[5].mean()),
              "precision_at_conf025": float(np.mean([r["precision_at_conf025"] for r in per_class])),
              "recall_at_conf025": float(np.mean([r["recall_at_conf025"] for r in per_class])),
              "max_conf": float(joined[1].max()) if len(joined[1]) else 0.0,
              "per_class": per_class, "elapsed_seconds": time.perf_counter()-started,
              "split_manifest_sha256": hashlib.sha256((dataset / "split_manifest.json").read_bytes()).hexdigest(),
              "scope": "Three furniture classes with explicit COCO name/ID mapping; same frozen valid split and evaluator. Test is unused. COCO dining table and broad Furniture Table differ semantically; interpret baseline with this limitation."}
    (output / f"{label}_predictions.json").write_text(json.dumps(predictions, indent=2), encoding="utf-8")
    (output / f"{label}_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "datasets/roboflow/furniture/v2_curated_v2")
    parser.add_argument("--output", type=Path, default=ROOT / "results/spec_workflow_20261022/spec1")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    print(json.dumps(evaluate(args.weights.resolve(), args.data_dir.resolve(), args.label, args.output)), flush=True)
    reports = [json.loads(p.read_text()) for p in sorted(args.output.glob("*_metrics.json"))]
    fields = ["model", "images", "map50", "map50_95", "precision_at_conf025", "recall_at_conf025", "max_conf"]
    with (args.output / "finetune_compare.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(reports)


if __name__ == "__main__":
    main()
