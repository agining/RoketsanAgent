"""Run a detector on a folder of images and write a submission CSV.

Output format, one row per image (image id is the file name without
extension; boxes are in original-image pixels, x/y is the top-left corner):

    image_id,PredictionString
    img_000001,car 0.93 976 533 98 95 van 0.71 1012 276 150 76
    img_000002,none

Example:
    PYTHONPATH=. python projects/roketsan/tools/predict_csv.py \
        configs/rtmdet/rtmdet_l_2h_a100_aug.py <checkpoint> \
        <test images dir> test_predictions.csv
    # only the images of a COCO file, e.g. the validation set:
    ... <train images dir> val_predictions.csv --ann-file val.json
"""
import argparse
import csv
import json
import os
import os.path as osp

import torch
from mmcv.transforms import Compose
from mmengine.config import Config
from mmengine.dataset import pseudo_collate
from mmengine.registry import init_default_scope
from torch.utils.data import DataLoader, Dataset

from mmdet.apis import init_detector

IMG_EXTS = ('.jpg', '.jpeg', '.png', '.bmp')


class ImageFolder(Dataset):

    def __init__(self, paths, pipeline):
        self.paths = paths
        self.pipeline = pipeline

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        return self.pipeline(dict(img_path=self.paths[idx], img_id=idx))


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('config')
    parser.add_argument('checkpoint')
    parser.add_argument('img_dir')
    parser.add_argument('out_file', help='output CSV file')
    parser.add_argument(
        '--ann-file',
        help='COCO file; if given, only its images are predicted')
    parser.add_argument('--score-thr', type=float, default=0.05)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--device', default='cuda:0')
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = Config.fromfile(args.config)
    init_default_scope(cfg.get('default_scope', 'mmdet'))

    if args.ann_file:
        with open(args.ann_file) as f:
            names = sorted(img['file_name'] for img in json.load(f)['images'])
    else:
        names = sorted(
            n for n in os.listdir(args.img_dir)
            if n.lower().endswith(IMG_EXTS))
    paths = [osp.join(args.img_dir, n) for n in names]

    model = init_detector(cfg, args.checkpoint, device=args.device)
    classes = model.dataset_meta['classes']
    # Test pipeline without ground truth loading
    pipeline = Compose([
        t for t in cfg.test_dataloader.dataset.pipeline
        if t['type'] != 'LoadAnnotations'
    ])
    loader = DataLoader(
        ImageFolder(paths, pipeline),
        batch_size=args.batch_size,
        num_workers=args.workers,
        collate_fn=pseudo_collate)

    rows = []
    num_boxes = 0
    with torch.no_grad():
        for data in loader:
            for result in model.test_step(data):
                pred = result.pred_instances
                keep = pred.scores >= args.score_thr
                bboxes = pred.bboxes[keep].cpu().tolist()
                scores = pred.scores[keep].cpu().tolist()
                labels = pred.labels[keep].cpu().tolist()
                parts = []
                for (x1, y1, x2, y2), score, label in zip(
                        bboxes, scores, labels):
                    parts.append(f'{classes[label]} {score:.2f} '
                                 f'{round(x1)} {round(y1)} '
                                 f'{round(x2 - x1)} {round(y2 - y1)}')
                num_boxes += len(parts)
                image_id = osp.splitext(osp.basename(result.img_path))[0]
                rows.append((image_id, ' '.join(parts) if parts else 'none'))
            print(f'{len(rows)}/{len(paths)} images', end='\r', flush=True)

    with open(args.out_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['image_id', 'PredictionString'])
        writer.writerows(rows)
    num_empty = sum(r[1] == 'none' for r in rows)
    print(f'\n{len(rows)} images, {num_boxes} boxes '
          f'(score >= {args.score_thr}), {num_empty} images with none')
    print(f'Saved to {args.out_file}')


if __name__ == '__main__':
    main()
