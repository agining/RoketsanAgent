"""Grid-search ensemble settings on a labelled set (parallel, CPU only).

Loads the member CSVs once, then scores every combination of member set x
fusion method (WBF / NMS) x IoU threshold x WBF confidence rule x weights x
pre-filter score threshold with pycocotools, in a process pool. Prints the
results sorted by mAP_50 and writes them to a JSON file.

Example:
    yolo/.venv/bin/python yolo/ensemble_search.py \
        --ann-file dataset/val_annotations_extended.json --out results.json
"""
import argparse
import contextlib
import io
import itertools
import json
import os
import os.path as osp
from multiprocessing import Pool

import numpy as np
from ensemble_boxes import nms, weighted_boxes_fusion
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval

from ensemble_csv import CLASSES, read_csv

P = osp.join(osp.dirname(osp.abspath(__file__)), '..', 'predictions')
MEMBERS = {
    'rtm_sahi640': 'val_predictions_sahi640.csv',
    'p2_sahi640': 'val_predictions_p2_sahi640.csv',
    'rtdetr_sahi960': 'val_predictions_rtdetrx_sahi960.csv',
    'rtdetr_sahi640': 'val_predictions_rtdetrx_sahi640.csv',
    'rtm_full': 'val_predictions.csv',
    'p2_full': 'val_predictions_p2.csv',
    'rtdetr_full': 'val_predictions_rtdetrx.csv',
}
G = {}  # per-process globals: coco, sizes, preds


def _init(ann_file):
    with contextlib.redirect_stdout(io.StringIO()):
        G['coco'] = COCO(ann_file)
    G['sizes'] = {osp.splitext(i['file_name'])[0]: (i['width'], i['height'])
                  for i in G['coco'].dataset['images']}
    G['name2id'] = {osp.splitext(i['file_name'])[0]: i['id']
                    for i in G['coco'].dataset['images']}
    G['cat'] = {c['name']: c['id'] for c in G['coco'].dataset['categories']}
    G['preds'] = {k: read_csv(osp.join(P, v)) for k, v in MEMBERS.items()}


def _to_lists(member_names, img, skip):
    w, h = G['sizes'][img]
    bl, sl, ll = [], [], []
    for m in member_names:
        b = np.array([x for x in G['preds'][m].get(img, []) if x[1] >= skip],
                     dtype=np.float64).reshape(-1, 6)
        xyxy = np.stack([b[:, 2] / w, b[:, 3] / h, (b[:, 2] + b[:, 4]) / w,
                         (b[:, 3] + b[:, 5]) / h], 1) if len(b) else \
            np.zeros((0, 4))
        bl.append(np.clip(xyxy, 0, 1).tolist())
        sl.append(b[:, 1].tolist())
        ll.append(b[:, 0].tolist())
    return bl, sl, ll, w, h


def evaluate(cfg):
    members, method, iou, conf_type, weights, skip = cfg
    dets = []
    for img in G['sizes']:
        bl, sl, ll, w, h = _to_lists(members, img, skip)
        if method == 'wbf':
            b, s, l = weighted_boxes_fusion(
                bl, sl, ll, weights=weights, iou_thr=iou, skip_box_thr=skip,
                conf_type=conf_type)
        else:
            b, s, l = nms(bl, sl, ll, weights=weights, iou_thr=iou)
        order = np.argsort(-s)[:300]
        for i in order:
            dets.append(dict(
                image_id=G['name2id'][img],
                category_id=G['cat'][CLASSES[int(l[i])]],
                score=float(s[i]),
                bbox=[b[i][0] * w, b[i][1] * h, (b[i][2] - b[i][0]) * w,
                      (b[i][3] - b[i][1]) * h]))
    with contextlib.redirect_stdout(io.StringIO()):
        e = COCOeval(G['coco'], G['coco'].loadRes(dets), 'bbox')
        e.evaluate()
        e.accumulate()
        e.summarize()
    return dict(members=members, method=method, iou=iou, conf_type=conf_type,
                weights=weights, skip=skip, mAP=e.stats[0], mAP_50=e.stats[1],
                mAP_s=e.stats[3], mAP_m=e.stats[4], mAP_l=e.stats[5])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ann-file', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--workers', type=int, default=24)
    args = parser.parse_args()

    member_sets = [
        ('rtm_sahi640', 'rtdetr_sahi960'),
        ('rtm_sahi640', 'p2_sahi640', 'rtdetr_sahi960'),
        ('rtm_sahi640', 'p2_sahi640', 'rtdetr_sahi960', 'rtdetr_sahi640'),
        ('rtm_sahi640', 'p2_sahi640', 'rtdetr_sahi960', 'rtdetr_full'),
        ('rtm_sahi640', 'p2_sahi640', 'rtdetr_sahi960', 'rtdetr_sahi640',
         'rtm_full', 'p2_full', 'rtdetr_full'),
    ]
    cfgs = []
    for members in member_sets:
        n = len(members)
        weight_opts = [tuple([1] * n)]
        # favour the RTMDet members (stronger single model)
        weight_opts.append(tuple(2 if m.startswith(('rtm', 'p2')) else 1
                                 for m in members))
        for weights, skip in itertools.product(weight_opts, [0.02]):
            for iou, conf_type in itertools.product(
                    [0.7, 0.75, 0.8, 0.85],
                    ['avg', 'max', 'box_and_model_avg',
                     'absent_model_aware_avg']):
                cfgs.append((members, 'wbf', iou, conf_type, weights, skip))
            for iou in [0.6, 0.7]:
                cfgs.append((members, 'nms', iou, None, weights, skip))
    print(f'{len(cfgs)} configurations, {args.workers} workers', flush=True)

    results = []
    with Pool(args.workers, initializer=_init, initargs=(args.ann_file, )) as pool:
        for i, r in enumerate(pool.imap_unordered(evaluate, cfgs), 1):
            results.append(r)
            if i % 20 == 0:
                best = max(results, key=lambda x: x['mAP_50'])
                print(f'{i}/{len(cfgs)} done, best mAP_50 so far '
                      f'{best["mAP_50"]:.4f}', flush=True)
    results.sort(key=lambda x: -x['mAP_50'])
    with open(args.out, 'w') as f:
        json.dump(results, f, indent=1)
    for r in results[:15]:
        print(f"{r['mAP_50']:.4f} mAP={r['mAP']:.4f} s/m/l={r['mAP_s']:.3f}/"
              f"{r['mAP_m']:.3f}/{r['mAP_l']:.3f} | {r['method']} iou={r['iou']}"
              f" conf={r['conf_type']} w={r['weights']} | "
              f"{'+'.join(r['members'])}")


if __name__ == '__main__':
    main()
