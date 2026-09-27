"""Compute per-class loss weights from the object counts of a COCO file.

``w_c = (1 / n_c) ** power``, normalized so the object-weighted mean weight is
1 (``sum_c n_c * w_c == sum_c n_c``), which keeps the overall loss scale
unchanged. ``power=0.5`` (inverse square root frequency) is a softer
rebalancing than full inverse frequency (``power=1``), which tends to hurt the
majority class too much.

Example:
    python projects/roketsan/tools/class_weights.py ../../dataset/train_coco.json
"""
import argparse
import json
from collections import Counter


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('ann_file', help='COCO annotation file')
    parser.add_argument('--power', type=float, default=0.5)
    args = parser.parse_args()

    with open(args.ann_file) as f:
        coco = json.load(f)
    cats = sorted(coco['categories'], key=lambda c: c['id'])
    counts = Counter(a['category_id'] for a in coco['annotations'])
    n = [counts[c['id']] for c in cats]
    raw = [(1 / c)**args.power for c in n]
    scale = sum(n) / sum(c * w for c, w in zip(n, raw))
    weights = [round(w * scale, 3) for w in raw]

    for cat, count, w in zip(cats, n, weights):
        print(f'{cat["name"]:>10}: {count:7d} objects -> weight {w}')
    print(f'class_weight={weights}')


if __name__ == '__main__':
    main()
