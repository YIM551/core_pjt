"""Describe the Furniture sample with the Day 1 VLM and save a run record."""

import argparse
import hashlib
import importlib.util
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=ROOT / "samples/furniture_v2_sofa.jpg")
    parser.add_argument("--max-tokens", type=int, default=80)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.max_tokens < 1:
        parser.error("--max-tokens must be positive")
    started = datetime.now(timezone.utc)
    output_dir = args.output_dir or (
        ROOT / "results/furniture_day1" / started.strftime("vlm_%Y%m%dT%H%M%S%fZ")
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    record_path = output_dir / "vlm_inference.json"
    image_path = args.image.resolve()
    image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
    with Image.open(image_path) as source:
        image = source.convert("RGB")

    exercise_path = ROOT / "source/2회차_day1/page37_VLM_이미지설명/VLM_이미지설명.py"
    spec = importlib.util.spec_from_file_location("day1_vlm_first", exercise_path)
    exercise = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exercise)

    yolo_path = ROOT / "results/furniture_day1/inference.json"
    yolo_record = json.loads(yolo_path.read_text(encoding="utf-8")) if yolo_path.exists() else None
    record = {
        "status": "running",
        "started_at_utc": started.isoformat(),
        "image": image_path.as_posix(), "image_sha256": image_hash,
        "image_size": list(image.size),
        "model": exercise.VLM_GGUF_PATH.as_posix(),
        "vision_projector": exercise.VLM_MMPROJ_PATH.as_posix(),
        "device": "cpu", "n_threads": os.cpu_count(),
        "n_ctx": exercise.VLM_CONTEXT_SIZE,
        "prompt": exercise.VLM_DESCRIBE_PROMPT,
        "max_tokens": args.max_tokens, "temperature": 0.0,
        "yolo_record": yolo_path.as_posix() if yolo_record else None,
        "same_image_as_yolo": yolo_record["image_sha256"] == image_hash if yolo_record else None,
        "timing_note": "First VLM call includes image encoding and text generation; not a warmed benchmark.",
    }

    def save_record():
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    save_record()
    print(f"Run record: {record_path}", flush=True)
    print("Loading Qwen2.5-VL-3B and its vision projector on CPU...", flush=True)
    model = None
    try:
        start = time.perf_counter()
        model = exercise.load_vlm()
        record["model_load_seconds"] = time.perf_counter() - start
        print(f"Model loaded in {record['model_load_seconds']:.2f}s; describing image...", flush=True)
        start = time.perf_counter()
        # Same message structure and prompt as the exercise, retaining finish_reason and usage.
        response = model.create_chat_completion(
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": exercise.to_data_url(image)}},
                {"type": "text", "text": exercise.VLM_DESCRIBE_PROMPT},
            ]}],
            max_tokens=args.max_tokens, temperature=0.0,
        )
        record["inference_seconds"] = time.perf_counter() - start
        choice = response["choices"][0]
        record["description"] = (choice["message"].get("content") or "").strip()
        record["finish_reason"] = choice.get("finish_reason")
        record["usage"] = response.get("usage")
        record["status"] = "complete"
        record["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        save_record()
        (output_dir / "description.txt").write_text(record["description"] + "\n", encoding="utf-8")
        print(json.dumps({key: record[key] for key in (
            "status", "description", "finish_reason", "model_load_seconds", "inference_seconds", "same_image_as_yolo"
        )}, ensure_ascii=True), flush=True)
    except Exception as error:
        record.update(status="failed", error_type=type(error).__name__, error=str(error))
        save_record()
        raise
    finally:
        if model is not None:
            model.close()


if __name__ == "__main__":
    main()
