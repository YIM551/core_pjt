"""Run the Day 1 YOLO detector on a Furniture v2 sample and save the results."""

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "furniture_v2_sofa.jpg"
ORIGINAL = (
    ROOT / "datasets" / "roboflow" / "furniture" / "v2" / "valid" / "images"
    / "Sofa--383-_jpg.rf.02ef655cee76cbd77bbab340a6231ce2.jpg"
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=SAMPLE)
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "results" / "furniture_day1"
    )
    args = parser.parse_args()
    image_path = args.image.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Reuse the existing exercise's model loading and inference functions.
    exercise_path = (
        ROOT / "source" / "2회차_day1" / "page25_YOLO_첫추론" / "YOLO_첫추론.py"
    )
    spec = importlib.util.spec_from_file_location("day1_yolo_first", exercise_path)
    exercise = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exercise)
    model = exercise.load_model()
    model.to("cpu")
    with Image.open(image_path) as source:
        image = source.convert("RGB")

    image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
    original_matches = (
        ORIGINAL.is_file()
        and hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == image_hash
    )
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "image": image_path.as_posix(),
        "image_sha256": image_hash,
        "image_size": list(image.size),
        "dataset_image": ORIGINAL.as_posix() if original_matches else None,
        "dataset_split": "valid" if original_matches else None,
        "model": exercise.YOLO_MODEL_PATH.as_posix(),
        "model_sha256": hashlib.sha256(exercise.YOLO_MODEL_PATH.read_bytes()).hexdigest(),
        "model_type": "pretrained COCO YOLO11n; not fine-tuned on Furniture",
        "device": "cpu",
        "inferences": [],
        "timing_note": "First call includes warm-up. These single calls are not a benchmark.",
    }
    for index, conf in enumerate((0.1, 0.25, 0.6)):
        results, elapsed = exercise.detect(model, image, conf)
        detections = [
            {
                "class_id": int(box.cls.item()),
                "label": model.names[int(box.cls.item())],
                "confidence": float(box.conf.item()),
                "xyxy": box.xyxy[0].tolist(),
            }
            for box in results[0].boxes
        ]
        report["inferences"].append({
            "confidence_threshold": conf,
            "elapsed_ms": elapsed,
            "includes_initial_warmup": index == 0,
            "detections": detections,
        })
        print(f"conf={conf:.2f}: {len(detections)} objects; "
              + ", ".join(item["label"] for item in detections))
        if conf == 0.25:
            annotated = output_dir / "first_inference.jpg"
            results[0].save(filename=str(annotated))
            report["annotated_image"] = annotated.as_posix()

    result_path = output_dir / "inference.json"
    result_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Results: {result_path}")
    print(f"Image: {report['annotated_image']}")


if __name__ == "__main__":
    main()
