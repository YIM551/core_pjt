"""Build a reviewed, group-disjoint Furniture subset without editing the export."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import random
import shutil
import sys

from PIL import Image
import yaml

from audit_furniture_structure import ROOT, digest, require, save_json, source_fingerprint


SPLITS = ("train", "valid", "test")
RATIOS = (0.70, 0.15, 0.15)


class Groups:
    def __init__(self, ids):
        self.parents = {key: key for key in ids}

    def find(self, key):
        while self.parents[key] != key:
            self.parents[key] = self.parents[self.parents[key]]
            key = self.parents[key]
        return key

    def join(self, first, second):
        a, b = sorted((self.find(first), self.find(second)))
        self.parents[b] = a


def assign_splits(group_rows, seed):
    """Deterministic repeated greedy group allocation, minimizing class-ratio error."""
    keys = sorted(group_rows)
    vectors = {key: [sum(row["class_id"] == cls for row in group_rows[key]) for cls in range(3)] for key in keys}
    totals = [sum(vector[cls] for vector in vectors.values()) for cls in range(3)]
    targets = [[total * ratio for total in totals] for ratio in RATIOS]
    for cls in range(3):
        if sum(vector[cls] > 0 for vector in vectors.values()) < 3:
            raise ValueError(f"Class {cls} has fewer than three independent accepted groups")

    def objective(counts, require_coverage=False):
        score = sum((counts[s][c]-targets[s][c])**2 / max(targets[s][c], 1)**2
                    for s in range(3) for c in range(3))
        if require_coverage:
            score += sum(100000 for row in counts for count in row if count == 0)
        return score

    rng = random.Random(seed)
    best = None
    for attempt in range(256):
        order = sorted(keys, key=lambda key: -(sum(vectors[key]) * rng.uniform(0.65, 1.35)))
        counts = [[0, 0, 0] for _ in SPLITS]
        assignment = {}
        for key in order:
            choices = list(range(3))
            rng.shuffle(choices)
            candidates = []
            for split in choices:
                trial = [row[:] for row in counts]
                trial[split] = [a+b for a, b in zip(trial[split], vectors[key])]
                candidates.append((objective(trial), split, trial))
            _, split, counts = min(candidates, key=lambda value: value[0])
            assignment[key] = split
        for _ in range(12):
            changed = False
            rng.shuffle(order)
            for key in order:
                old = assignment[key]
                baseline = objective(counts, True)
                for new in range(3):
                    if new == old:
                        continue
                    trial = [row[:] for row in counts]
                    trial[old] = [a-b for a, b in zip(trial[old], vectors[key])]
                    trial[new] = [a+b for a, b in zip(trial[new], vectors[key])]
                    if objective(trial, True) + 1e-12 < baseline:
                        counts, assignment[key] = trial, new
                        changed = True
                        break
            if not changed:
                break
        score = objective(counts, True)
        if best is None or score < best[0]:
            best = score, assignment.copy(), counts
    if any(count == 0 for row in best[2] for count in row):
        raise ValueError("Unable to cover every class in every split without breaking groups")
    return {key: SPLITS[value] for key, value in best[1].items()}, best[2], targets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "datasets/roboflow/furniture/v2")
    parser.add_argument("--audit-dir", type=Path, default=ROOT / "results/furniture_day1/data_audit")
    parser.add_argument("--output", type=Path, default=ROOT / "datasets/roboflow/furniture/v2_curated_v2")
    parser.add_argument("--seed", type=int, default=20261021)
    args = parser.parse_args()
    source, audit, output = args.source.resolve(), args.audit_dir.resolve(), args.output.resolve()
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise SystemExit("Source and derived output must be separate sibling directories")
    if output.exists():
        raise SystemExit(f"Output already exists; use a new version directory: {output}")
    before = json.loads((audit / "raw_fingerprint_before.json").read_text(encoding="utf-8"))
    require(source_fingerprint(source) == before, "Raw source changed before build")
    items = json.loads((audit / "image_index.json").read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in items}
    require(len(by_id) == len(items) == 689, "Expected 689 unique indexed source images")
    reviews, review_hashes = {}, {}
    for path in sorted((audit / "reviews").glob("*_review.json")):
        review_hashes[path.name] = digest(path)
        content = json.loads(path.read_text(encoding="utf-8"))
        for decision in content["decisions"]:
            require(decision["id"] in by_id and decision["id"] not in reviews, decision["id"])
            require(decision["status"] in ("accept", "quarantine") and decision.get("reason"), "Invalid review decision")
            require(decision.get("group_id"), f"Missing visual group: {decision['id']}")
            reviews[decision["id"]] = decision
    require(set(reviews) == set(by_id), "Every source image must have one visual review")
    overrides_path = audit / "review_overrides.json"
    overrides = json.loads(overrides_path.read_text(encoding="utf-8")) if overrides_path.exists() else []
    for override in overrides:
        require(override["id"] in reviews and override["status"] in ("accept", "quarantine"), "Invalid review override")
        reviews[override["id"]] = {**reviews[override["id"]], **override}
    scene_path = audit / "scene_groups.json"
    scene_groups = json.loads(scene_path.read_text(encoding="utf-8")) if scene_path.exists() else []
    links = json.loads((audit / "similarity_links.json").read_text(encoding="utf-8"))
    union = Groups(by_id)
    visual_groups = defaultdict(list)
    for key, review in reviews.items():
        visual_groups[review["group_id"]].append(key)
    for ids in visual_groups.values():
        for key in ids[1:]:
            union.join(ids[0], key)
    for scene in scene_groups:
        require(all(key in by_id for key in scene["ids"]), "Unknown scene-group ID")
        for key in scene["ids"][1:]:
            union.join(scene["ids"][0], key)
    for link in links:
        union.join(link["a"], link["b"])
    accepted, quarantined = [], []
    for row in items:
        decision = reviews[row["id"]]
        record = {**row, "review": decision, "group_id": "group_" + union.find(row["id"])}
        if decision["status"] == "accept" and row["structural_valid"]:
            accepted.append(record)
        else:
            if not row["structural_valid"]:
                record["structural_exclusion"] = "Box outside normalized image extent"
            quarantined.append(record)
    groups = defaultdict(list)
    for row in accepted:
        groups[row["group_id"]].append(row)
    assignment, counts, targets = assign_splits(groups, args.seed)

    output.mkdir(parents=True)
    for split in SPLITS:
        (output / split / "images").mkdir(parents=True)
        (output / split / "labels").mkdir()
    manifest = []
    for row in sorted(accepted, key=lambda row: row["id"]):
        split = assignment[row["group_id"]]
        image = output / split / "images" / Path(row["image"]).name
        label = output / split / "labels" / Path(row["label"]).name
        require(not image.exists() and not label.exists(), "Filename collision")
        shutil.copy2(source / row["image"], image)
        shutil.copy2(source / row["label"], label)
        require(digest(image) == row["image_sha256"] and digest(label) == row["label_sha256"], "Copy hash mismatch")
        manifest.append({
            "id": row["id"], "class_id": row["class_id"], "group_id": row["group_id"],
            "original_split": row["original_split"], "derived_split": split,
            "original_image": row["image"], "original_label": row["label"],
            "image": image.relative_to(output).as_posix(), "label": label.relative_to(output).as_posix(),
            "image_sha256": row["image_sha256"], "label_sha256": row["label_sha256"],
            "review_reason": row["review"]["reason"], "label_action": "unchanged_copy",
        })
    original_config = yaml.safe_load((source / "data.yaml").read_text(encoding="utf-8"))
    config = {"train": "train/images", "val": "valid/images", "test": "test/images",
              "nc": 3, "names": original_config["names"]}
    (output / "data.yaml").write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")
    for name in ("README.dataset.txt", "README.roboflow.txt"):
        shutil.copy2(source / name, output / ("SOURCE_" + name))
    save_json(output / "split_manifest.json", manifest)
    save_json(output / "quarantine.json", [{"id": row["id"], "image": row["image"], "label": row["label"],
        "class_id": row["class_id"], "original_split": row["original_split"], "group_id": row["group_id"],
        "reason": row.get("structural_exclusion") or row["review"]["reason"],
        "source": source.as_posix()} for row in sorted(quarantined, key=lambda row: row["id"])])
    group_split_sets = defaultdict(set)
    for row in manifest:
        group_split_sets[row["group_id"]].add(row["derived_split"])
    leaked_groups = [key for key, values in group_split_sets.items() if len(values) > 1]
    require(not leaked_groups, "Visual groups overlap between splits")
    actual_split_by_id, actual_hash_splits, actual_pixel_splits = {}, defaultdict(set), defaultdict(set)
    image_name_to_id = {Path(row["image"]).name: row["id"] for row in manifest}
    for split in SPLITS:
        for image in (output / split / "images").iterdir():
            key = image_name_to_id[image.name]
            require(key not in actual_split_by_id, f"Image repeated on disk: {key}")
            actual_split_by_id[key] = split
            actual_hash_splits[digest(image)].add(split)
            with Image.open(image) as opened:
                pixels = opened.convert("RGB")
                pixel_hash = hashlib.sha256(str(pixels.size).encode() + pixels.tobytes()).hexdigest()
            actual_pixel_splits[pixel_hash].add(split)
    require(actual_split_by_id == {row["id"]: row["derived_split"] for row in manifest}, "On-disk splits differ from manifest")
    linked_leaks = [link for link in links if link["a"] in actual_split_by_id and link["b"] in actual_split_by_id
                    and actual_split_by_id[link["a"]] != actual_split_by_id[link["b"]]]
    hash_leaks = [key for key, values in actual_hash_splits.items() if len(values) > 1]
    pixel_leaks = [key for key, values in actual_pixel_splits.items() if len(values) > 1]
    require(not linked_leaks and not hash_leaks and not pixel_leaks, "Image similarity leakage across actual output splits")
    original_group_splits = defaultdict(set)
    for row in items:
        original_group_splits[union.find(row["id"])].add(row["original_split"])
    after = source_fingerprint(source)
    require(before == after, "Raw source changed during build")
    checks = {
        "original_tree_unchanged": before == after, "accepted_plus_quarantined_equals_689": len(manifest)+len(quarantined) == 689,
        "all_source_images_reviewed": len(reviews) == 689,
        "all_derived_images_and_labels_match_source_hashes": True,
        "every_class_present_in_every_split": all(value > 0 for row in counts for value in row),
        "group_overlap_between_splits": leaked_groups,
        "known_exact_or_perceptual_links_cross_split": linked_leaks,
        "actual_file_hash_overlap_between_splits": hash_leaks,
        "actual_decoded_pixel_hash_overlap_between_splits": pixel_leaks,
    }
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "source": source.as_posix(),
        "output": output.as_posix(), "source_version": "Furniture v2", "derived_version": output.name,
        "seed": args.seed, "target_ratios": dict(zip(SPLITS, RATIOS)),
        "class_names": original_config["names"], "accepted_images": len(manifest), "quarantined_images": len(quarantined),
        "classes_by_split": {split: dict(zip(original_config["names"], values)) for split, values in zip(SPLITS, counts)},
        "images_by_split": {split: sum(values) for split, values in zip(SPLITS, counts)},
        "independent_groups_by_split": dict(Counter(assignment.values())),
        "source_known_groups_spanning_original_splits": sum(len(value) > 1 for value in original_group_splits.values()),
        "raw_tree_sha256": before["tree_sha256"], "review_sha256": review_hashes,
        "image_index_sha256": digest(audit / "image_index.json"),
        "script_sha256": {name: digest(ROOT / "scripts" / name) for name in
                          ("audit_furniture_structure.py", "build_furniture_curated.py")},
        "runtime": {"python": sys.version.split()[0], **{name: version(name) for name in
                    ("ultralytics", "numpy", "pillow", "PyYAML", "opencv-python")}},
        "scene_groups_sha256": digest(scene_path) if scene_path.exists() else None,
        "review_overrides_sha256": digest(overrides_path) if overrides_path.exists() else None,
        "similarity_links_sha256": digest(audit / "similarity_links.json"),
        "split_manifest_sha256": digest(output / "split_manifest.json"),
        "label_policy": "Conservative assistant visual screening. Accepted boxes are copied unchanged; images with missing/ambiguous targets or problematic boxes are quarantined. No model-generated annotations are treated as ground truth.",
        "evaluation_scope": "Local exploratory evaluation on a curated mainly-single-target subset, not the original RF100 benchmark and not a complete-room object-counting benchmark. Visual review and perceptual grouping can miss issues; new production claims need independent annotation review and scene data.",
        "test_policy": "New holdout frozen by split_manifest.json. Source data was visually inspected for QA; do not use derived test predictions or scores for tuning.",
        "checks": checks,
    }
    save_json(output / "derivation.json", report)
    save_json(audit / "curation_summary.json", report)
    save_json(audit / "raw_fingerprint_after.json", after)
    print(json.dumps({key: report[key] for key in ("accepted_images", "quarantined_images", "classes_by_split", "independent_groups_by_split", "checks")}, ensure_ascii=True))


if __name__ == "__main__":
    main()
