"""Audit the immutable Furniture v2 export and find conservative similarity links."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import zipfile

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import yaml


ROOT = Path(__file__).resolve().parents[1]
CLASS_NAMES = {0: "chair", 1: "sofa", 2: "table"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def source_fingerprint(source):
    files = {p.relative_to(source).as_posix(): digest(p)
             for p in sorted(source.rglob("*")) if p.is_file()}
    combined = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"tree_sha256": combined, "files": files}


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def visual_hashes(image):
    gray = np.asarray(image.convert("L").resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float32)
    low = cv2.dct(gray)[:8, :8].flatten()[1:]
    phash = sum(int(bit) << i for i, bit in enumerate(low > np.median(low)))
    dh = np.asarray(image.convert("L").resize((9, 8), Image.Resampling.LANCZOS))
    dhash = sum(int(bit) << i for i, bit in enumerate((dh[:, 1:] > dh[:, :-1]).flatten()))
    rgb = np.asarray(image.resize((32, 32)), dtype=np.float32)
    return phash, dhash, rgb.mean(axis=(0, 1)).tolist()


def contact_sheets(source, out, items):
    sheets = out / "contact_sheets"
    sheets.mkdir(exist_ok=True)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 15)
        small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 12)
    except OSError:
        font = small = ImageFont.load_default()
    for class_id, name in CLASS_NAMES.items():
        subset = sorted((row for row in items if row["class_id"] == class_id), key=lambda row: row["id"])
        save_json(out / f"{name}_index.json", subset)
        for page in range(0, len(subset), 30):
            canvas = Image.new("RGB", (1440, 1325), "#f1f5f9")
            draw = ImageDraw.Draw(canvas)
            draw.text((12, 5), f"{name.upper()} | green = original label box | page {page//30+1}", font=font, fill="black")
            for cell, row in enumerate(subset[page:page+30]):
                with Image.open(source / row["image"]) as source_image:
                    thumb = ImageOps.contain(source_image.convert("RGB"), (230, 220))
                ox, oy = cell % 6 * 240 + (240-thumb.width)//2, 30 + cell//6 * 259
                canvas.paste(thumb, (ox, oy))
                cx, cy, width, height = row["bbox"]
                draw.rectangle((ox+(cx-width/2)*thumb.width, oy+(cy-height/2)*thumb.height,
                                ox+(cx+width/2)*thumb.width, oy+(cy+height/2)*thumb.height),
                               outline="#00b828", width=2)
                tx = cell % 6 * 240 + 5
                draw.text((tx, oy+221), f"{row['id']} / {row['original_split']}", font=font, fill="black")
                draw.text((tx, oy+240), Path(row["image"]).name.split(".rf.")[0][:29], font=small, fill="#334155")
            canvas.save(sheets / f"{name}_{page//30+1:02}.jpg", quality=92)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "datasets/roboflow/furniture/v2")
    parser.add_argument("--output", type=Path, default=ROOT / "results/furniture_day1/data_audit")
    parser.add_argument("--contact-sheets", action="store_true")
    args = parser.parse_args()
    source, out = args.source.resolve(), args.output.resolve()
    require(out != source and not out.is_relative_to(source) and not source.is_relative_to(out),
            "Audit output and raw source must be separate directories")
    out.mkdir(parents=True, exist_ok=True)
    (out / "reviews").mkdir(exist_ok=True)
    snapshot = source_fingerprint(source)
    snapshot_path = out / "raw_fingerprint_before.json"
    if snapshot_path.exists():
        require(json.loads(snapshot_path.read_text(encoding="utf-8")) == snapshot, "Source changed since initial audit")
    else:
        save_json(snapshot_path, snapshot)
    provenance = json.loads((source / "provenance.json").read_text(encoding="utf-8"))
    archive = source.parent / provenance["archive_name"]
    require(digest(archive) == provenance["archive_sha256"], "Export ZIP checksum mismatch")
    with zipfile.ZipFile(archive) as original:
        for member in original.infolist():
            if not member.is_dir():
                require(digest(source / member.filename) == hashlib.sha256(original.read(member)).hexdigest(), member.filename)
    config = yaml.safe_load((source / "data.yaml").read_text(encoding="utf-8"))
    require(config["names"] == ["Chair", "Sofa", "Table"], "Unexpected class mapping")
    items, per_split, structural_issues = [], {}, []
    for split in ("train", "valid", "test"):
        per_split[split] = Counter()
        for label in sorted((source / split / "labels").glob("*.txt")):
            fields = [line.split() for line in label.read_text().splitlines() if line.strip()]
            require(len(fields) == 1 and len(fields[0]) == 5, f"Unexpected annotation format: {label}")
            class_id = int(fields[0][0])
            require(class_id in CLASS_NAMES, f"Unexpected class ID in {label}")
            box = list(map(float, fields[0][1:]))
            matches = list((source / split / "images").glob(label.stem + ".*"))
            require(len(matches) == 1, f"Expected exactly one image for {label}")
            image_path = matches[0]
            with Image.open(image_path) as opened:
                image = opened.convert("RGB")
                image.load()
            phash, dhash, mean = visual_hashes(image)
            row = {"original_split": split, "class_id": class_id,
                   "image": image_path.relative_to(source).as_posix(),
                   "label": label.relative_to(source).as_posix(), "bbox": box,
                   "image_sha256": digest(image_path), "label_sha256": digest(label),
                   "width": image.width, "height": image.height,
                   "pixel_sha256": hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest(),
                   "phash": phash, "dhash": dhash, "mean_rgb": mean}
            cx, cy, width, height = box
            valid = all(math.isfinite(v) and 0 <= v <= 1 for v in box) and width > 0 and height > 0
            valid = valid and min(cx-width/2, cy-height/2) >= -1e-6 and max(cx+width/2, cy+height/2) <= 1+1e-6
            row["structural_valid"] = valid
            items.append(row)
            per_split[split][class_id] += 1
        require(len(list((source / split / "images").glob("*"))) == sum(per_split[split].values()),
                f"Unpaired images in {split}")
    for class_id, name in CLASS_NAMES.items():
        subset = sorted((row for row in items if row["class_id"] == class_id), key=lambda row: Path(row["image"]).name.casefold())
        for index, row in enumerate(subset):
            row["id"] = f"{name[0].upper()}{index:03}"
            if not row["structural_valid"]:
                structural_issues.append(row["id"])
    links = []
    for index, first in enumerate(items):
        for second in items[index+1:]:
            exact = first["pixel_sha256"] == second["pixel_sha256"]
            pd = (first["phash"] ^ second["phash"]).bit_count()
            dd = (first["dhash"] ^ second["dhash"]).bit_count()
            ar1, ar2 = first["width"]/first["height"], second["width"]/second["height"]
            color_gap = max(abs(a-b) for a, b in zip(first["mean_rgb"], second["mean_rgb"]))
            near = pd <= 4 and dd <= 8 and abs(ar1/ar2-1) <= 0.05 and color_gap <= 25
            if exact or near:
                links.append({"a": first["id"], "b": second["id"], "kind": "identical_pixels" if exact else "perceptual_candidate",
                              "phash_distance": pd, "dhash_distance": dd,
                              "cross_original_split": first["original_split"] != second["original_split"]})
    save_json(out / "image_index.json", items)
    save_json(out / "similarity_links.json", links)
    report = {"images": len(items), "classes": config["names"], "boxes_by_original_split": per_split,
              "all_images_have_one_annotation": True, "structural_issue_ids": structural_issues,
              "source_matches_export_archive": True, "raw_tree_sha256": snapshot["tree_sha256"],
              "similarity_link_count": len(links), "cross_original_split_links": sum(row["cross_original_split"] for row in links),
              "method": "RGB decoded pixel hashes plus pHash<=4, dHash<=8, aspect ratio difference<=5%, mean RGB gap<=25. Candidate links are conservatively grouped, not proof of duplicate identity. Visual object/scene groups supplement this check."}
    save_json(out / "structural_audit.json", report)
    if args.contact_sheets:
        contact_sheets(source, out, items)
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
