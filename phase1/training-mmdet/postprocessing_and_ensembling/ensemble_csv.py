"""Ensemble prediction CSVs with Weighted Boxes Fusion and/or score them.

Inputs are CSVs in the submission format (``label score x y w h`` groups).
With several inputs, boxes are fused per image with Weighted Boxes Fusion
(https://arxiv.org/abs/1910.13302, ``ensemble-boxes`` package). With
``--ann-file`` the (fused or single) predictions are scored with
pycocotools, standard COCO settings.

Examples:
    # score one CSV
    python yolo/ensemble_csv.py --csv a.csv --ann-file val.json
    # fuse two CSVs with weights 2:1, score and save
    python yolo/ensemble_csv.py --csv a.csv b.csv --weights 2 1 \
        --ann-file val.json --out-csv fused.csv
    # fuse test predictions (image sizes read from the image folder)
    python yolo/ensemble_csv.py --csv a.csv b.csv --img-dir <test images> \
        --out-csv fused.csv
"""
import argparse
import contextlib
import csv
import io
import json
import os
import os.path as osp

import numpy as np
from ensemble_boxes import nms, soft_nms, weighted_boxes_fusion
from PIL import Image
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval

CLASSES = ['bus', 'car', 'truck', 'van']


def read_csv(path):
    preds = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            t = row['PredictionString'].split()
            boxes = []
            if t != ['none']:
                for k in range(0, len(t), 6):
                    label, s, x, y, w, h = t[k:k + 6]
                    boxes.append((CLASSES.index(label), float(s), float(x),
                                  float(y), float(w), float(h)))
            preds[row['image_id']] = boxes
    return preds


def fuse(pred_list, sizes, weights, iou_thr, skip_box_thr, conf_type,
         method='wbf'):
    fused = {}
    for image_id, (w, h) in sizes.items():
        boxes_list, scores_list, labels_list = [], [], []
        for preds in pred_list:
            b = np.array(preds.get(image_id, []), dtype=np.float64)
            if len(b) == 0:
                b = np.zeros((0, 6))
            xyxy = np.stack([
                b[:, 2] / w, b[:, 3] / h, (b[:, 2] + b[:, 4]) / w,
                (b[:, 3] + b[:, 5]) / h
            ], 1) if len(b) else np.zeros((0, 4))
            boxes_list.append(np.clip(xyxy, 0, 1).tolist())
            scores_list.append(b[:, 1].tolist())
            labels_list.append(b[:, 0].tolist())
        if method == 'wbf':
            boxes, scores, labels = weighted_boxes_fusion(
                boxes_list, scores_list, labels_list, weights=weights,
                iou_thr=iou_thr, skip_box_thr=skip_box_thr,
                conf_type=conf_type)
        elif method == 'nms':
            # per-class NMS over the pooled boxes (scores scaled by weights)
            boxes, scores, labels = nms(
                boxes_list, scores_list, labels_list, weights=weights,
                iou_thr=iou_thr)
        else:  # soft-NMS: overlapping boxes are down-weighted, not removed
            boxes, scores, labels = soft_nms(
                boxes_list, scores_list, labels_list, weights=weights,
                iou_thr=iou_thr, sigma=0.5, thresh=skip_box_thr or 0.001)
        order = np.argsort(-scores)[:300]
        fused[image_id] = [(int(labels[i]), float(scores[i]),
                            boxes[i][0] * w, boxes[i][1] * h,
                            (boxes[i][2] - boxes[i][0]) * w,
                            (boxes[i][3] - boxes[i][1]) * h) for i in order]
    return fused


def evaluate(preds, coco):
    name2id = {
        osp.splitext(i['file_name'])[0]: i['id']
        for i in coco.dataset['images']
    }
    cat_ids = {c['name']: c['id'] for c in coco.dataset['categories']}
    dets = [
        dict(image_id=name2id[img], category_id=cat_ids[CLASSES[lab]],
             score=s, bbox=[x, y, w, h])
        for img, boxes in preds.items() if img in name2id
        for lab, s, x, y, w, h in boxes
    ]
    with contextlib.redirect_stdout(io.StringIO()):
        e = COCOeval(coco, coco.loadRes(dets), 'bbox')
        e.evaluate()
        e.accumulate()
        e.summarize()
    s = e.stats
    metrics = dict(mAP=s[0], mAP_50=s[1], mAP_75=s[2], mAP_s=s[3],
                   mAP_m=s[4], mAP_l=s[5])
    prec = e.eval['precision']
    for k, name in enumerate(CLASSES):
        p = prec[0, :, k, 0, -1]
        metrics[f'{name}_AP50'] = float(p[p > -1].mean())
    return metrics


def write_csv(preds, path):
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['image_id', 'PredictionString'])
        for img in sorted(preds):
            parts = [
                f'{CLASSES[lab]} {s:.2f} {round(x)} {round(y)} {round(w)} '
                f'{round(h)}' for lab, s, x, y, w, h in preds[img]
            ]
            writer.writerow([img, ' '.join(parts) if parts else 'none'])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--csv', nargs='+', required=True)
    parser.add_argument('--weights', type=float, nargs='+')
    parser.add_argument('--ann-file', help='COCO file to score against')
    parser.add_argument('--img-dir', help='to read image sizes (no ann file)')
    parser.add_argument('--iou-thr', type=float, default=0.55)
    parser.add_argument('--skip-box-thr', type=float, default=0.0)
    parser.add_argument('--conf-type', default='avg')
    parser.add_argument(
        '--method', choices=['wbf', 'nms', 'soft_nms'], default='wbf',
        help='wbf: Weighted Boxes Fusion; nms: per-class NMS of the pooled '
        'boxes; soft_nms: per-class soft-NMS')
    parser.add_argument('--out-csv')
    parser.add_argument('--out-json', help='write the metrics as JSON')
    args = parser.parse_args()

    pred_list = [read_csv(p) for p in args.csv]
    coco = None
    if args.ann_file:
        with contextlib.redirect_stdout(io.StringIO()):
            coco = COCO(args.ann_file)
        sizes = {
            osp.splitext(i['file_name'])[0]: (i['width'], i['height'])
            for i in coco.dataset['images']
        }
    else:
        sizes = {}
        for n in os.listdir(args.img_dir):
            stem = osp.splitext(n)[0]
            if stem in pred_list[0]:
                with Image.open(osp.join(args.img_dir, n)) as im:
                    sizes[stem] = im.size

    if len(pred_list) == 1:
        preds = pred_list[0]
    else:
        preds = fuse(pred_list, sizes, args.weights, args.iou_thr,
                     args.skip_box_thr, args.conf_type, args.method)
    if args.out_csv:
        write_csv(preds, args.out_csv)
        print(f'Saved {len(preds)} images to {args.out_csv}')
    if coco is not None:
        metrics = evaluate(preds, coco)
        print('RESULT ' + ' '.join(f'{k}={v:.4f}' for k, v in metrics.items()))
        if args.out_json:
            with open(args.out_json, 'w') as f:
                json.dump(dict(args=vars(args), metrics=metrics), f, indent=1)


if __name__ == '__main__':
    main()
