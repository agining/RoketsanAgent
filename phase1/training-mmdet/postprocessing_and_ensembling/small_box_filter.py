"""Share of detections below an area threshold, and mAP with them removed.

For each prediction CSV (``label score x y w h`` format) this reports how
many detections have ``w * h < --min-area`` (all detections and those with
score >= 0.3), then scores the CSV with pycocotools (standard COCO settings)
before and after dropping those detections. Optionally writes the filtered
CSVs. The share of ground-truth boxes below the threshold is reported too.

Example:
    yolo/.venv/bin/python yolo/small_box_filter.py \
        --ann-file dataset/val_annotations_extended.json \
        --csv predictions/val_predictions_sahi640.csv --min-area 100
"""
import argparse
import os.path as osp

from ensemble_csv import CLASSES, evaluate, read_csv, write_csv
from pycocotools.coco import COCO
import contextlib
import io


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ann-file', required=True)
    parser.add_argument('--csv', nargs='+', required=True)
    parser.add_argument('--min-area', type=float, default=100.0)
    parser.add_argument('--out-dir', help='also write the filtered CSVs')
    args = parser.parse_args()

    with contextlib.redirect_stdout(io.StringIO()):
        coco = COCO(args.ann_file)
    gt_areas = [a['bbox'][2] * a['bbox'][3] for a in coco.dataset['annotations']]
    gt_small = sum(a < args.min_area for a in gt_areas)
    print(f'ground truth: {gt_small}/{len(gt_areas)} boxes '
          f'({100 * gt_small / len(gt_areas):.2f}%) below {args.min_area:g} px^2')

    for path in args.csv:
        preds = read_csv(path)
        boxes = [b for bs in preds.values() for b in bs]
        small = [b for b in boxes if b[4] * b[5] < args.min_area]
        conf = [b for b in boxes if b[1] >= 0.3]
        conf_small = [b for b in conf if b[4] * b[5] < args.min_area]
        filtered = {
            img: [b for b in bs if b[4] * b[5] >= args.min_area]
            for img, bs in preds.items()
        }
        before = evaluate(preds, coco)
        after = evaluate(filtered, coco)
        print(f'\n{osp.basename(path)}')
        print(f'  detections below {args.min_area:g} px^2: {len(small)}/'
              f'{len(boxes)} ({100 * len(small) / len(boxes):.2f}%); '
              f'with score >= 0.3: {len(conf_small)}/{len(conf)} '
              f'({100 * len(conf_small) / max(len(conf), 1):.2f}%)')
        for k in ('mAP_50', 'mAP', 'mAP_s', 'mAP_m', 'mAP_l'):
            print(f'  {k:7s} before {before[k]:.4f}  after {after[k]:.4f}  '
                  f'change {after[k] - before[k]:+.4f}')
        if args.out_dir:
            out = osp.join(args.out_dir, osp.basename(path).replace(
                '.csv', f'_min{int(args.min_area)}px.csv'))
            write_csv(filtered, out)
            print(f'  saved {out}')


if __name__ == '__main__':
    main()
