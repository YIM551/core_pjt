"""Validate the Furniture v2 export and create its local YOLO configuration.

Run with the project's .venv Python. Original images, labels and data.yaml
are read only; generated configuration and reports may be regenerated.
"""

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COUNTS = {"train": 454, "valid": 161, "test": 74}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
SOURCE_URL = "https://universe.roboflow.com/roboflow-100/furniture-ngpea/dataset/2"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path,
        default=PROJECT_ROOT / "datasets" / "roboflow" / "furniture" / "v2",
    )
    parser.add_argument(
        "--report-dir", type=Path,
        default=PROJECT_ROOT / "results" / "furniture_day1",
    )
    args = parser.parse_args()
    root = args.data_dir.resolve()
    report_dir = args.report_dir.resolve()
    source_yaml = root / "data.yaml"
    if not source_yaml.is_file():
        raise SystemExit(f"Missing exported config: {source_yaml}")
    with source_yaml.open(encoding="utf-8-sig") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise SystemExit("data.yaml must contain a mapping.")
    names = config.get("names")
    if isinstance(names, list):
        class_names = dict(enumerate(names))
    elif isinstance(names, dict):
        class_names = {int(key): value for key, value in names.items()}
    else:
        raise SystemExit("data.yaml must provide its original names list or mapping.")
    if set(class_names) != set(range(len(class_names))):
        raise SystemExit("Class IDs in names must be contiguous from zero.")
    if len(class_names) != 3 or config.get("nc", len(class_names)) != len(class_names):
        raise SystemExit("Furniture v2 must have 3 classes and a consistent nc value.")

    errors, rows = [], []
    duplicate_candidates = defaultdict(list)
    counts, label_counts, box_counts = {}, {}, {}
    class_counts = Counter()
    split_class_counts = {}
    split_box_count_histograms = {}
    for split, expected in EXPECTED_COUNTS.items():
        image_dir = root / split / "images"
        label_dir = root / split / "labels"
        if not image_dir.is_dir() or not label_dir.is_dir():
            errors.append(f"{split}: missing images or labels directory")
        images = sorted(
            path for path in image_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
        labels = set(label_dir.rglob("*.txt"))
        counts[split] = len(images)
        label_counts[split] = len(labels)
        box_counts[split] = 0
        split_class_counts[split] = Counter({class_id: 0 for class_id in class_names})
        split_box_count_histograms[split] = Counter()
        if len(images) != expected:
            errors.append(f"{split}: expected {expected} images, found {len(images)}")
        used_labels = set()
        for image_path in images:
            relative_image = image_path.relative_to(root).as_posix()
            label_path = label_dir / image_path.relative_to(image_dir).with_suffix(".txt")
            relative_label = label_path.relative_to(root).as_posix()
            width, height, image_hash, boxes = None, None, None, 0
            try:
                image_hash = sha256(image_path)
                duplicate_candidates[image_hash].append(
                    {"split": split, "path": relative_image}
                )
                with Image.open(image_path) as image:
                    image.load()
                    width, height = image.size
            except (OSError, ValueError, Image.DecompressionBombError) as exc:
                errors.append(f"{relative_image}: image decode failed: {exc}")
            if not label_path.is_file():
                errors.append(f"{relative_image}: missing label {relative_label}")
            else:
                used_labels.add(label_path)
                try:
                    lines = label_path.read_text(encoding="utf-8-sig").splitlines()
                except (OSError, UnicodeError) as exc:
                    errors.append(f"{relative_label}: cannot read label: {exc}")
                    lines = []
                for line_number, line in enumerate(lines, 1):
                    if not line.strip():
                        continue
                    try:
                        fields = line.split()
                        if len(fields) != 5:
                            raise ValueError("expected class_id cx cy width height")
                        class_id = int(fields[0])
                        if class_id not in class_names:
                            raise ValueError(f"unknown class ID {class_id}")
                        cx, cy, box_width, box_height = map(float, fields[1:])
                        coords = (cx, cy, box_width, box_height)
                        if not all(math.isfinite(value) and 0 <= value <= 1 for value in coords):
                            raise ValueError("coordinates must be finite and normalized to [0, 1]")
                        if box_width <= 0 or box_height <= 0:
                            raise ValueError("box width and height must be positive")
                        boxes += 1
                        class_counts[class_id] += 1
                        split_class_counts[split][class_id] += 1
                    except ValueError as exc:
                        errors.append(f"{relative_label}:{line_number}: {exc}")
            box_counts[split] += boxes
            split_box_count_histograms[split][boxes] += 1
            rows.append({
                "path": relative_image, "split": split, "sha256": image_hash,
                "width": width, "height": height,
                "label_path": relative_label, "box_count": boxes,
            })
        for orphan in sorted(labels - used_labels):
            errors.append(f"{orphan.relative_to(root).as_posix()}: label has no matching image")

    duplicate_groups = [
        {"sha256": digest, "cross_split": len({item["split"] for item in items}) > 1,
         "images": items}
        for digest, items in duplicate_candidates.items() if len(items) > 1
    ]
    cross_split_groups = sum(group["cross_split"] for group in duplicate_groups)
    local_yaml = root / "data.local.yaml"
    if not errors:
        local_config = dict(config)
        local_config.update(
            path=root.as_posix(), train="train/images", val="valid/images", test="test/images"
        )
        with local_yaml.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(local_config, handle, allow_unicode=True, sort_keys=False)

    report = {
        "status": "pass" if not errors else "fail",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": SOURCE_URL, "version": 2,
        "data_dir": root.as_posix(), "original_yaml_sha256": sha256(source_yaml),
        "class_names": class_names, "expected_image_counts": EXPECTED_COUNTS,
        "image_counts": counts, "label_counts": label_counts,
        "box_counts": box_counts, "boxes_by_class_id": dict(sorted(class_counts.items())),
        "boxes_by_split_and_class_id": {
            split: dict(sorted(counts.items())) for split, counts in split_class_counts.items()
        },
        "box_count_histogram_by_split": {
            split: dict(sorted(counts.items())) for split, counts in split_box_count_histograms.items()
        },
        "total_images": len(rows), "local_config_written": not errors,
        "local_config": local_yaml.as_posix(),
        "duplicate_check": "Exact image file bytes (SHA-256), not visual similarity",
        "duplicate_groups": duplicate_groups,
        "cross_split_duplicate_group_count": cross_split_groups,
        "errors": errors,
    }
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (report_dir / "image_manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["path", "split", "sha256", "width", "height", "label_path", "box_count"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Furniture v2 validation: {report['status'].upper()}")
    print(f"Images: {counts}; total={len(rows)}")
    print(f"Class mapping: {class_names}")
    for split, split_counts in split_class_counts.items():
        print(f"{split} class instances: {dict(split_counts)}")
        missing = [class_names[class_id] for class_id, count in split_counts.items() if not count]
        if missing:
            print(f"WARNING: {split} has no instances of: {', '.join(missing)}")
    print(f"Exact duplicate groups: {len(duplicate_groups)}; cross-split={cross_split_groups}")
    if duplicate_groups:
        print("WARNING: duplicates are reported only; no source images or labels were changed.")
    print(f"Reports: {report_dir}")
    if errors:
        for error in errors[:10]:
            print(f"ERROR: {error}")
        raise SystemExit(f"Validation failed with {len(errors)} errors; local config was not written.")
    print(f"Local config: {local_yaml}")


if __name__ == "__main__":
    main()
