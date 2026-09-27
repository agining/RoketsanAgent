"""Convert COCO annotation files to an Ultralytics (YOLO txt) dataset.

For each split, images are symlinked into ``<out>/images/<split>`` and a
label file ``<out>/labels/<split>/<name>.txt`` is written with one
``class cx cy w h`` line per box (normalized to [0, 1]); class indices follow
the COCO category order. A ``data.yaml`` for Ultralytics is written too.

Example:
    yolo/.venv/bin/python yolo/coco_to_yolo.py <img dir> yolo/data_roketsan \
        --split train dataset/train_annotations_extended.json \
        --split val dataset/val_annotations_extended.json
"""
import argparse
import json
import os
import os.path as osp
from collections import defaultdict


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('img_dir')
    parser.add_argument('out_dir')
    parser.add_argument('--split', nargs=2, action='append', required=True,
                        metavar=('NAME', 'COCO_JSON'))
    args = parser.parse_args()

    names = None
    for split, ann_file in args.split:
        with open(ann_file) as f:
            coco = json.load(f)
        cats = sorted(coco['categories'], key=lambda c: c['id'])
        if names is None:
            names = [c['name'] for c in cats]
        assert names == [c['name'] for c in cats], 'category mismatch'
        cat_to_idx = {c['id']: i for i, c in enumerate(cats)}
        anns = defaultdict(list)
        for a in coco['annotations']:
            anns[a['image_id']].append(a)

        img_out = osp.join(args.out_dir, 'images', split)
        lbl_out = osp.join(args.out_dir, 'labels', split)
        os.makedirs(img_out, exist_ok=True)
        os.makedirs(lbl_out, exist_ok=True)
        num_boxes = 0
        for img in coco['images']:
            src = osp.join(args.img_dir, img['file_name'])
            dst = osp.join(img_out, img['file_name'])
            if not osp.lexists(dst):
                os.symlink(src, dst)
            w, h = img['width'], img['height']
            lines = []
            for a in anns[img['id']]:
                x, y, bw, bh = a['bbox']
                x1, y1 = max(x, 0), max(y, 0)
                x2, y2 = min(x + bw, w), min(y + bh, h)
                if x2 <= x1 or y2 <= y1:
                    continue
                lines.append(
                    f'{cat_to_idx[a["category_id"]]} {(x1 + x2) / 2 / w:.6f} '
                    f'{(y1 + y2) / 2 / h:.6f} {(x2 - x1) / w:.6f} '
                    f'{(y2 - y1) / h:.6f}')
            num_boxes += len(lines)
            stem = osp.splitext(img['file_name'])[0]
            with open(osp.join(lbl_out, stem + '.txt'), 'w') as f:
                f.write('\n'.join(lines) + ('\n' if lines else ''))
        print(f'{split}: {len(coco["images"])} images, {num_boxes} boxes')

    splits = [s for s, _ in args.split]
    with open(osp.join(args.out_dir, 'data.yaml'), 'w') as f:
        f.write(f'path: {osp.abspath(args.out_dir)}\n')
        for s in splits:
            f.write(f'{s}: images/{s}\n')
        f.write('names:\n')
        for i, n in enumerate(names):
            f.write(f'  {i}: {n}\n')
    print(f'classes: {names}; wrote {osp.join(args.out_dir, "data.yaml")}')


if __name__ == '__main__':
    main()
