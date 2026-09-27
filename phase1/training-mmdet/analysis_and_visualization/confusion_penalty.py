"""Derive a class-confusion penalty matrix from validation predictions.

Builds the detection confusion matrix with MMDetection's
``tools/analysis_tools/confusion_matrix.py`` matching rules (a prediction
above ``--score-thr`` that overlaps a ground truth of another class with
IoU >= ``--tp-iou-thr`` counts as a confusion), normalizes each row by the
number of ground-truth objects of that class, and turns the rates into
penalties for ``ConfusionPenaltyQualityFocalLoss``:

    rate[i][j]    = objects of class i detected as class j / objects of class i
    penalty[i][j] = 1 + (max_penalty - 1) * rate[i][j] / max_offdiag_rate

Pairs with a rate below ``--min-rate`` get no penalty (1.0), as does the
diagonal. The most confused pair gets ``--max-penalty``.

Example:
    python tools/test.py <config> <checkpoint> --out preds.pkl
    python projects/roketsan/tools/confusion_penalty.py <config> preds.pkl \
        confusion_penalty.json
"""
import argparse
import json
import os.path as osp
import sys

import numpy as np
from mmengine import Config
from mmengine.fileio import load
from mmengine.registry import init_default_scope

from mmdet.registry import DATASETS

sys.path.insert(
    0, osp.join(osp.dirname(__file__), '../../../tools/analysis_tools'))
from confusion_matrix import calculate_confusion_matrix  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('config', help='config whose test set was predicted')
    parser.add_argument('prediction_path', help='.pkl from tools/test.py')
    parser.add_argument('out_file', help='output JSON file')
    parser.add_argument('--score-thr', type=float, default=0.3)
    parser.add_argument('--tp-iou-thr', type=float, default=0.5)
    parser.add_argument('--max-penalty', type=float, default=3.0)
    parser.add_argument('--min-rate', type=float, default=0.01)
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = Config.fromfile(args.config)
    init_default_scope(cfg.get('default_scope', 'mmdet'))
    dataset = DATASETS.build(cfg.test_dataloader.dataset)
    classes = list(dataset.metainfo['classes'])
    num_classes = len(classes)

    results = load(args.prediction_path)
    cm = calculate_confusion_matrix(
        dataset, results, score_thr=args.score_thr, tp_iou_thr=args.tp_iou_thr)

    gt_counts = np.zeros(num_classes)
    for idx in range(len(dataset)):
        for inst in dataset.get_data_info(idx)['instances']:
            gt_counts[inst['bbox_label']] += 1

    rate = cm[:num_classes, :num_classes] / gt_counts[:, None]
    offdiag = rate.copy()
    np.fill_diagonal(offdiag, 0)
    offdiag[offdiag < args.min_rate] = 0
    penalty = 1 + (args.max_penalty - 1) * offdiag / offdiag.max()

    result = dict(
        classes=classes,
        score_thr=args.score_thr,
        tp_iou_thr=args.tp_iou_thr,
        max_penalty=args.max_penalty,
        min_rate=args.min_rate,
        gt_counts=gt_counts.astype(int).tolist(),
        confusion_matrix=cm.astype(int).tolist(),
        confusion_rate=np.round(rate, 4).tolist(),
        penalty=np.round(penalty, 3).tolist())
    with open(args.out_file, 'w') as f:
        json.dump(result, f, indent=1)

    names = classes + ['background']
    print('\nConfusion matrix (rows: ground truth, cols: prediction)')
    print(' ' * 12 + ''.join(f'{n:>12}' for n in names))
    for i, n in enumerate(names):
        print(f'{n:>12}' + ''.join(f'{int(v):12d}' for v in cm[i]))
    print('\nConfusion rate (row-normalized by ground-truth count)')
    print(' ' * 12 + ''.join(f'{n:>12}' for n in classes))
    for i, n in enumerate(classes):
        print(f'{n:>12}' + ''.join(f'{v:12.4f}' for v in rate[i]))
    print('\nPenalty (rows: ground truth, cols: confused prediction)')
    print(' ' * 12 + ''.join(f'{n:>12}' for n in classes))
    for i, n in enumerate(classes):
        print(f'{n:>12}' + ''.join(f'{v:12.3f}' for v in penalty[i]))
    print(f'\nconfusion_penalty={np.round(penalty, 3).tolist()}')
    print(f'Saved to {args.out_file}')


if __name__ == '__main__':
    main()
