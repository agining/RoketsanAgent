"""Evaluate an RF-DETR checkpoint on the validation set with and without SAHI sliced inference.

Usage:
  python eval_sahi.py --weights snapshots/rfdetr960_ep17_best_ema.pth --mode full
  python eval_sahi.py --weights snapshots/rfdetr960_ep17_best_ema.pth --mode sahi --slice 640 --overlap 0.2
Writes COCO-format detections to --out-dir and prints COCO mAP50 / mAP50-95 (maxDets=100).
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
from faster_coco_eval import COCO, COCOeval_faster
from PIL import Image
from rfdetr import RFDETRLarge
from sahi import AutoDetectionModel
from sahi.predict import get_prediction, get_sliced_prediction

parser = argparse.ArgumentParser()
parser.add_argument("--weights", required=True)
parser.add_argument("--resolution", type=int, default=960)
parser.add_argument("--mode", choices=["full", "sahi"], default="sahi")
parser.add_argument("--slice", type=int, default=640)
parser.add_argument("--overlap", type=float, default=0.2)
parser.add_argument("--conf", type=float, default=0.05)
parser.add_argument("--postprocess", default="GREEDYNMM", choices=["GREEDYNMM", "NMM", "NMS", "LSNMS"])
parser.add_argument("--match-metric", default="IOS", choices=["IOS", "IOU"])
parser.add_argument("--match-thresh", type=float, default=0.5)
parser.add_argument("--agnostic", action="store_true", help="class-agnostic merging of slice predictions")
parser.add_argument("--no-full-pred", action="store_true", help="SAHI: skip the extra whole-image prediction")
parser.add_argument("--limit", type=int, default=0, help="evaluate only the first N images (0 = all)")
parser.add_argument("--ann", default="data/roketsan/valid/_annotations.coco.json")
parser.add_argument("--img-dir", default="data/roketsan/valid")
parser.add_argument("--out-dir", default="outputs/sahi_eval")
args = parser.parse_args()

CLASS_NAMES = ["bus", "car", "truck", "van"]  # ids 0..3, same as the COCO json

rfdetr_model = RFDETRLarge(pretrain_weights=args.weights, resolution=args.resolution, num_classes=len(CLASS_NAMES))
detection_model = AutoDetectionModel.from_pretrained(
    model_type="roboflow",
    model=rfdetr_model,
    confidence_threshold=args.conf,
    category_mapping={str(i): n for i, n in enumerate(CLASS_NAMES)},
)

coco_gt = COCO(args.ann)
img_ids = sorted(coco_gt.getImgIds())
if args.limit:
    img_ids = img_ids[: args.limit]

detections = []
start = time.time()
for n, img_id in enumerate(img_ids, 1):
    info = coco_gt.loadImgs(img_id)[0]
    image = np.asarray(Image.open(Path(args.img_dir) / info["file_name"]).convert("RGB"))
    if args.mode == "full":
        result = get_prediction(image, detection_model)
    else:
        result = get_sliced_prediction(
            image,
            detection_model,
            slice_height=args.slice,
            slice_width=args.slice,
            overlap_height_ratio=args.overlap,
            overlap_width_ratio=args.overlap,
            perform_standard_pred=not args.no_full_pred,
            postprocess_type=args.postprocess,
            postprocess_match_metric=args.match_metric,
            postprocess_match_threshold=args.match_thresh,
            postprocess_class_agnostic=args.agnostic,
            verbose=0,
        )
    for p in result.object_prediction_list:
        x1, y1, x2, y2 = p.bbox.to_xyxy()
        detections.append({
            "image_id": img_id, "category_id": int(p.category.id),
            "bbox": [float(x1), float(y1), float(x2 - x1), float(y2 - y1)], "score": float(p.score.value),
        })
    if n % 100 == 0:
        print(f"{n}/{len(img_ids)} images, {time.time() - start:.0f}s", flush=True)

tag = "full" if args.mode == "full" else (
    f"sahi_s{args.slice}_o{args.overlap}_{args.postprocess}_{args.match_metric}{args.match_thresh}"
    f"{'_agn' if args.agnostic else ''}{'_nofull' if args.no_full_pred else ''}"
)
out_dir = Path(args.out_dir)
out_dir.mkdir(parents=True, exist_ok=True)
json.dump(detections, open(out_dir / f"val_dets_{tag}.json", "w"))

coco_dt = coco_gt.loadRes(detections)
ev = COCOeval_faster(coco_gt, coco_dt, "bbox")
ev.params.imgIds = img_ids
ev.evaluate()
ev.accumulate()
ev.summarize()
print(f"RESULT {tag}: mAP50={ev.stats[1]:.4f} mAP50-95={ev.stats[0]:.4f} "
      f"images={len(img_ids)} dets={len(detections)} time={time.time() - start:.0f}s")
