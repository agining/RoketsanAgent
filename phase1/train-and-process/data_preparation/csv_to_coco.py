"""Convert train/val annotation CSVs (x, y, w, h = top-left + size in pixels) to COCO json for DEIMv2.

Usage: python helper_codes/csv_to_coco.py <image_dir> <out_dir>
Images listed in train.txt / val.txt without any boxes are kept as negative samples.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IMAGE_DIR = Path(sys.argv[1])
OUT_DIR = Path(sys.argv[2])
OUT_DIR.mkdir(parents=True, exist_ok=True)

SPLITS = {
    "train": (ROOT / "train_annotations.csv", ROOT / "train.txt"),
    "val": (ROOT / "val_annotations.csv", ROOT / "val.txt"),
}

# Same deterministic (sorted) mapping as label_generator.py
class_names = set()
for csv_file, _ in SPLITS.values():
    with open(csv_file, newline="") as f:
        class_names.update(row["label"] for row in csv.DictReader(f))
class_names = sorted(class_names)
class_to_id = {name: i for i, name in enumerate(class_names)}
print("Classes:", class_to_id)

for split, (csv_file, list_file) in SPLITS.items():
    rows_by_image = defaultdict(list)
    with open(csv_file, newline="") as f:
        for row in csv.DictReader(f):
            rows_by_image[row["image_id"]].append(row)

    image_ids = [l.strip() for l in open(list_file) if l.strip()]
    image_ids = sorted(set(image_ids) | set(rows_by_image))

    images, annotations = [], []
    ann_id, skipped = 1, 0
    for img_idx, image_id in enumerate(image_ids, start=1):
        path = IMAGE_DIR / f"{image_id}.jpg"
        if not path.exists():
            print(f"WARNING: missing image {path}")
            continue
        with Image.open(path) as im:
            width, height = im.size
        images.append({"id": img_idx, "file_name": path.name, "width": width, "height": height})

        for row in rows_by_image.get(image_id, []):
            x, y, w, h = (float(row[k]) for k in ("x", "y", "w", "h"))
            # clip to image bounds
            x1, y1 = max(0.0, x), max(0.0, y)
            x2, y2 = min(float(width), x + w), min(float(height), y + h)
            if x2 - x1 < 1 or y2 - y1 < 1:
                skipped += 1
                continue
            bw, bh = x2 - x1, y2 - y1
            annotations.append({
                "id": ann_id, "image_id": img_idx, "category_id": class_to_id[row["label"]],
                "bbox": [x1, y1, bw, bh], "area": bw * bh, "iscrowd": 0,
            })
            ann_id += 1

    coco = {
        "images": images,
        "annotations": annotations,
        "categories": [{"id": i, "name": n} for n, i in class_to_id.items()],
    }
    out = OUT_DIR / f"instances_{split}.json"
    json.dump(coco, open(out, "w"))
    print(f"{split}: {len(images)} images, {len(annotations)} boxes, {skipped} degenerate boxes skipped -> {out}")
