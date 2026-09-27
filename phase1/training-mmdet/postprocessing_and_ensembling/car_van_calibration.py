"""Car/van class calibration of a prediction CSV (post-processing only).

Car and van boxes of the same vehicle usually both exist in the output
(per-class NMS keeps one box per class). For each van box that overlaps a
car box with IoU >= ``iou``: if ``van_score >= ratio * car_score`` (e.g.
ratio 0.67 turns "van 0.40 vs car 0.60" into a van), the van box takes the
car box's score and the car box's score is multiplied by ``demote``
(0 removes it). Otherwise nothing changes. A global rescaling of one class
would not change mAP (AP ranks within a class), this pairwise rule does.

--search tunes (iou, ratio, demote) on a labelled CSV; --apply writes a
calibrated CSV with given parameters.

Examples:
    yolo/.venv/bin/python yolo/car_van_calibration.py --search \
        --csv predictions/val_predictions_sahi640.csv \
        --ann-file dataset/val_annotations_extended.json
    yolo/.venv/bin/python yolo/car_van_calibration.py --apply \
        --csv predictions/test.csv --out predictions/test_cal.csv \
        --iou 0.7 --ratio 0.67 --demote 0.5
"""
import argparse
import itertools
import json
from multiprocessing import Pool

import numpy as np

from ensemble_csv import CLASSES, evaluate, read_csv, write_csv

CAR, VAN = CLASSES.index('car'), CLASSES.index('van')
G = {}


def iou_matrix(a, b):
    """IoU between xywh boxes a (N, 4) and b (M, 4)."""
    ax2, ay2 = a[:, 0] + a[:, 2], a[:, 1] + a[:, 3]
    bx2, by2 = b[:, 0] + b[:, 2], b[:, 1] + b[:, 3]
    iw = (np.minimum(ax2[:, None], bx2[None]) -
          np.maximum(a[:, None, 0], b[None, :, 0])).clip(min=0)
    ih = (np.minimum(ay2[:, None], by2[None]) -
          np.maximum(a[:, None, 1], b[None, :, 1])).clip(min=0)
    inter = iw * ih
    union = (a[:, 2] * a[:, 3])[:, None] + (b[:, 2] * b[:, 3])[None] - inter
    return inter / np.maximum(union, 1e-9)


def calibrate(preds, iou, ratio, demote):
    out, changed = {}, 0
    for img, boxes in preds.items():
        b = np.array(boxes, dtype=np.float64).reshape(-1, 6)
        if len(b):
            vans = np.nonzero(b[:, 0] == VAN)[0]
            cars = np.nonzero(b[:, 0] == CAR)[0]
            if len(vans) and len(cars):
                ious = iou_matrix(b[vans, 2:], b[cars, 2:])
                best = ious.argmax(1)
                for vi, cj in enumerate(best):
                    if ious[vi, cj] < iou:
                        continue
                    v, c = vans[vi], cars[cj]
                    if b[v, 1] >= ratio * b[c, 1] and b[c, 1] > b[v, 1]:
                        b[v, 1] = b[c, 1]
                        b[c, 1] *= demote
                        changed += 1
            b = b[b[:, 1] > 0]
        out[img] = [(int(x[0]), *map(float, x[1:])) for x in b]
    return out, changed


def _init(csv_path, ann_file):
    import contextlib, io
    from pycocotools.coco import COCO
    with contextlib.redirect_stdout(io.StringIO()):
        G['coco'] = COCO(ann_file)
    G['preds'] = read_csv(csv_path)


def _score(params):
    iou, ratio, demote = params
    cal, changed = calibrate(G['preds'], iou, ratio, demote)
    m = evaluate(cal, G['coco'])
    return dict(iou=iou, ratio=ratio, demote=demote, changed=changed, **m)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--csv', required=True)
    parser.add_argument('--ann-file')
    parser.add_argument('--out')
    parser.add_argument('--search', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--iou', type=float, default=0.7)
    parser.add_argument('--ratio', type=float, default=0.67)
    parser.add_argument('--demote', type=float, default=0.5)
    parser.add_argument('--workers', type=int, default=24)
    args = parser.parse_args()

    if args.search:
        grid = list(itertools.product(
            [0.5, 0.7, 0.85], [0.3, 0.5, 0.67, 0.8, 0.9, 1.0],
            [0.0, 0.3, 0.5, 0.7, 0.9]))
        grid.append((0.7, 99.0, 1.0))  # ratio 99: never fires = baseline
        with Pool(args.workers, initializer=_init,
                  initargs=(args.csv, args.ann_file)) as pool:
            res = pool.map(_score, grid)
        res.sort(key=lambda r: -r['mAP_50'])
        base = [r for r in res if r['ratio'] == 99.0][0]
        print(f"baseline mAP_50 {base['mAP_50']:.4f} car {base['car_AP50']:.4f}"
              f" van {base['van_AP50']:.4f}")
        for r in res[:12]:
            print(f"mAP_50 {r['mAP_50']:.4f} ({r['mAP_50'] - base['mAP_50']:+.4f})"
                  f" car {r['car_AP50']:.4f} van {r['van_AP50']:.4f} mAP "
                  f"{r['mAP']:.4f} | iou={r['iou']} ratio={r['ratio']} "
                  f"demote={r['demote']} pairs={r['changed']}")
        if args.out:
            with open(args.out, 'w') as f:
                json.dump(res, f, indent=1)
    if args.apply:
        preds = read_csv(args.csv)
        cal, changed = calibrate(preds, args.iou, args.ratio, args.demote)
        write_csv(cal, args.out)
        print(f'{changed} car/van pairs recalibrated; saved {args.out}')
        if args.ann_file:
            import contextlib, io
            from pycocotools.coco import COCO
            with contextlib.redirect_stdout(io.StringIO()):
                coco = COCO(args.ann_file)
            print('RESULT', {k: round(v, 4) for k, v in
                             evaluate(cal, coco).items()})


if __name__ == '__main__':
    main()
