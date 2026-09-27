"""Predict the Kaggle test images with RF-DETR + SAHI and write a submission CSV.

PredictionString per image: "label confidence x y w h" repeated (x, y = top-left, pixels, same convention as the
annotation CSVs), or "none" when nothing passes the threshold. Rows follow sample_submission.csv.

Usage: python predict_test_sahi.py --weights <ckpt> --out submissions/submission.csv
"""
import argparse
import csv
import time
from pathlib import Path

import numpy as np
from PIL import Image
from rfdetr import RFDETRLarge
from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction

COMP = Path("/home/ubuntu/.cache/kagglehub/competitions/level-up-ai-roketsan-yapay-zeka-hackathonu")
CLASS_NAMES = ["bus", "car", "truck", "van"]

parser = argparse.ArgumentParser()
parser.add_argument("--weights", required=True)
parser.add_argument("--resolution", type=int, default=960)
parser.add_argument("--slice", type=int, default=960)
parser.add_argument("--overlap", type=float, default=0.2)
parser.add_argument("--conf", type=float, default=0.5)
parser.add_argument("--nms-iou", type=float, default=0.5, help="IoU threshold of the class-agnostic NMS merge")
parser.add_argument("--img-dir", default=str(COMP / "test/images"))
parser.add_argument("--sample", default=str(COMP / "sample_submission.csv"))
parser.add_argument("--out", default="submissions/submission.csv")
parser.add_argument("--shard", type=int, default=0, help="process only images with index %% num_shards == shard")
parser.add_argument("--num-shards", type=int, default=1)
args = parser.parse_args()

rfdetr_model = RFDETRLarge(pretrain_weights=args.weights, resolution=args.resolution, num_classes=len(CLASS_NAMES))
detection_model = AutoDetectionModel.from_pretrained(
    model_type="roboflow",
    model=rfdetr_model,
    confidence_threshold=args.conf,
    category_mapping={i: n for i, n in enumerate(CLASS_NAMES)},  # SAHI looks names up by int id
)

image_ids = [row["image_id"] for row in csv.DictReader(open(args.sample))]
image_ids = image_ids[args.shard::args.num_shards]
out = Path(args.out)
out.parent.mkdir(parents=True, exist_ok=True)
start, n_boxes, n_empty = time.time(), 0, 0
with open(out, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["image_id", "PredictionString"])
    for n, image_id in enumerate(image_ids, 1):
        image = np.asarray(Image.open(Path(args.img_dir) / f"{image_id}.jpg").convert("RGB"))
        result = get_sliced_prediction(
            image,
            detection_model,
            slice_height=args.slice,
            slice_width=args.slice,
            overlap_height_ratio=args.overlap,
            overlap_width_ratio=args.overlap,
            perform_standard_pred=True,
            postprocess_type="NMS",
            postprocess_match_metric="IOU",
            postprocess_match_threshold=args.nms_iou,
            postprocess_class_agnostic=True,
            verbose=0,
        )
        parts = []
        for p in sorted(result.object_prediction_list, key=lambda p: -p.score.value):
            if p.score.value < args.conf:
                continue
            x1, y1, x2, y2 = p.bbox.to_xyxy()
            parts.append(f"{p.category.name} {p.score.value:.4f} {round(x1)} {round(y1)} {round(x2 - x1)} {round(y2 - y1)}")
        n_boxes += len(parts)
        n_empty += not parts
        writer.writerow([image_id, " ".join(parts) if parts else "none"])
        if n % 200 == 0:
            print(f"{n}/{len(image_ids)} images, {time.time() - start:.0f}s", flush=True)

print(f"wrote {out}: {len(image_ids)} images, {n_boxes} boxes, {n_empty} with 'none', {time.time() - start:.0f}s")
