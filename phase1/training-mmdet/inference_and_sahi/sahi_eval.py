"""SAHI-style sliced inference: evaluate on a COCO file and/or write a CSV.

Implements Slicing Aided Hyper Inference (https://arxiv.org/abs/2202.06934)
around an MMDetection model: every image is cut into overlapping
``--slice-size`` tiles (tiles at the border are shifted inwards to stay
inside the image), each tile is run through the model's normal test pipeline
(so it is upscaled to the model input size), optionally together with the
full image (SAHI's "standard prediction"). Tile predictions are shifted back
to image coordinates and merged with class-aware NMS or SAHI's default
greedy non-maximum merging (GREEDYNMM with intersection-over-smaller).

Several slice sizes can be combined (``--slice-size 960 1280``) and
``--slice-size 0`` disables slicing (full image only, the normal inference).

Example:
    PYTHONPATH=. python projects/roketsan/tools/sahi_eval.py <config> \
        <checkpoint> <img dir> --ann-file val.json --slice-size 960
"""
import argparse
import csv
import json
import os.path as osp

import mmcv
import numpy as np
import torch
from mmcv.ops import batched_nms
from mmcv.transforms import Compose
from mmengine.config import Config
from mmengine.dataset import pseudo_collate
from mmengine.registry import init_default_scope
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
from torch.utils.data import DataLoader, Dataset

from mmdet.apis import init_detector


def slice_starts(length, size, overlap):
    """Start offsets of tiles covering [0, length) with the given overlap."""
    if length <= size:
        return [0]
    step = max(int(size * (1 - overlap)), 1)
    starts = list(range(0, length - size, step))
    starts.append(length - size)  # last tile flush with the border
    return starts


def make_windows(width, height, slice_sizes, overlap, full_image):
    windows = []
    if full_image:
        windows.append((0, 0, width, height))
    for size in slice_sizes:
        if size >= max(width, height) and full_image:
            continue  # the tile would just be the full image again
        for y in slice_starts(height, size, overlap):
            for x in slice_starts(width, size, overlap):
                windows.append(
                    (x, y, min(x + size, width), min(y + size, height)))
    return windows


class SlicedImages(Dataset):

    def __init__(self, paths, pipeline, slice_sizes, overlap, full_image):
        self.paths = paths
        self.pipeline = pipeline
        self.slice_sizes = slice_sizes
        self.overlap = overlap
        self.full_image = full_image

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        img = mmcv.imread(self.paths[idx])
        h, w = img.shape[:2]
        windows = make_windows(w, h, self.slice_sizes, self.overlap,
                               self.full_image)
        crops = [
            self.pipeline(
                dict(img=np.ascontiguousarray(img[y1:y2, x1:x2]), img_id=idx))
            for x1, y1, x2, y2 in windows
        ]
        return idx, windows, crops


def collate(batch):
    return batch


def touches_inner_edge(bboxes, x1, y1, x2, y2, img_w, img_h, margin=2):
    """Mask of tile-local boxes touching a tile edge that is not also an
    image border, i.e. objects that are likely cut by the tile."""
    w, h = x2 - x1, y2 - y1
    mask = bboxes.new_zeros(len(bboxes), dtype=torch.bool)
    if x1 > 0:
        mask |= bboxes[:, 0] <= margin
    if y1 > 0:
        mask |= bboxes[:, 1] <= margin
    if x2 < img_w:
        mask |= bboxes[:, 2] >= w - margin
    if y2 < img_h:
        mask |= bboxes[:, 3] >= h - margin
    return mask


def greedy_nmm(bboxes, scores, labels, ios_thr):
    """SAHI GREEDYNMM: class-aware; the best-scoring box absorbs every
    remaining box whose intersection over the smaller box area is above the
    threshold, taking the union of their extents and keeping its score."""
    keep_boxes, keep_scores, keep_labels = [], [], []
    for cls in labels.unique():
        m = labels == cls
        b, s = bboxes[m], scores[m]
        order = s.argsort(descending=True)
        b, s = b[order], s[order]
        area = (b[:, 2] - b[:, 0]).clamp(min=0) * (b[:, 3] - b[:, 1]).clamp(
            min=0)
        lt = torch.max(b[:, None, :2], b[None, :, :2])
        rb = torch.min(b[:, None, 2:], b[None, :, 2:])
        inter = (rb - lt).clamp(min=0).prod(-1)
        ios = inter / torch.min(area[:, None], area[None, :]).clamp(min=1e-6)
        matches = (ios > ios_thr).cpu().numpy()
        merged = np.zeros(len(b), dtype=bool)
        b_np = b.cpu().numpy()
        for i in range(len(b)):
            if merged[i]:
                continue
            group = np.nonzero(matches[i] & ~merged)[0]
            merged[group] = True
            box = b_np[group]
            keep_boxes.append([
                box[:, 0].min(), box[:, 1].min(), box[:, 2].max(),
                box[:, 3].max()
            ])
            keep_scores.append(s[i].item())
            keep_labels.append(cls.item())
    return (bboxes.new_tensor(keep_boxes).reshape(-1, 4),
            scores.new_tensor(keep_scores), labels.new_tensor(keep_labels))


def merge(bboxes, scores, labels, method, thr, max_per_img,
          class_agnostic=False):
    if len(scores) == 0:
        return bboxes, scores, labels
    if method == 'nms':
        # class_agnostic: boxes of different classes also suppress each
        # other, so one object keeps only its best-scoring class
        _, keep = batched_nms(
            bboxes, scores, labels,
            dict(
                type='nms', iou_threshold=thr,
                class_agnostic=class_agnostic))
        bboxes, scores, labels = bboxes[keep], scores[keep], labels[keep]
    else:
        assert not class_agnostic, 'class-agnostic merging needs nms'
        bboxes, scores, labels = greedy_nmm(bboxes, scores, labels, thr)
    order = scores.argsort(descending=True)[:max_per_img]
    return bboxes[order], scores[order], labels[order]


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('config')
    parser.add_argument('checkpoint')
    parser.add_argument('img_dir')
    parser.add_argument('--ann-file', help='COCO file to predict and score')
    parser.add_argument(
        '--slice-size',
        type=int,
        nargs='+',
        default=[960],
        help='tile sizes in original-image pixels; 0 = no slicing')
    parser.add_argument('--overlap', type=float, default=0.2)
    parser.add_argument(
        '--no-full-image',
        action='store_true',
        help='do not add the full-image prediction')
    parser.add_argument(
        '--merge', choices=['nmm', 'nms'], default='nmm',
        help='nmm: SAHI GREEDYNMM (IoS), nms: class-aware NMS (IoU)')
    parser.add_argument('--merge-thr', type=float, default=0.5)
    parser.add_argument(
        '--class-agnostic',
        action='store_true',
        help='merge with class-agnostic NMS (overlapping boxes of different '
        'classes suppress each other)')
    parser.add_argument(
        '--pre-merge-score-thr',
        type=float,
        default=0.0,
        help='drop boxes below this score before merging (SAHI applies '
        'its confidence threshold, typically 0.3, before merging)')
    parser.add_argument(
        '--drop-edge-boxes',
        action='store_true',
        help='drop tile boxes touching a tile edge that is inside the image '
        '(objects cut by the tile); the full-image pass covers them')
    parser.add_argument('--max-per-img', type=int, default=300)
    parser.add_argument('--score-thr', type=float, default=0.05)
    parser.add_argument('--out-csv', help='also write a submission CSV')
    parser.add_argument('--out-json', help='write the metrics as JSON')
    parser.add_argument('--batch-images', type=int, default=4)
    parser.add_argument('--workers', type=int, default=8)
    return parser.parse_args()


def main():
    args = parse_args()
    slice_sizes = [s for s in args.slice_size if s > 0]
    full_image = not args.no_full_image
    assert slice_sizes or full_image, 'nothing to predict'

    cfg = Config.fromfile(args.config)
    init_default_scope(cfg.get('default_scope', 'mmdet'))
    model = init_detector(cfg, args.checkpoint, device='cuda:0')
    classes = model.dataset_meta['classes']
    # Keep the per-tile score threshold low; the final one is applied after
    # merging
    model.test_cfg.score_thr = min(model.test_cfg.score_thr, args.score_thr)

    pipeline = []
    for t in cfg.test_dataloader.dataset.pipeline:
        if t['type'] == 'LoadAnnotations':
            continue
        if t['type'] == 'LoadImageFromFile':
            t = dict(type='mmdet.LoadImageFromNDArray')
        pipeline.append(t)
    pipeline = Compose(pipeline)

    if args.ann_file:
        coco = COCO(args.ann_file)
        images = sorted(coco.dataset['images'], key=lambda i: i['id'])
    else:
        import os
        images = [
            dict(id=i, file_name=n) for i, n in enumerate(
                sorted(n for n in os.listdir(args.img_dir)
                       if n.lower().endswith(('.jpg', '.jpeg', '.png'))))
        ]
    paths = [osp.join(args.img_dir, img['file_name']) for img in images]
    loader = DataLoader(
        SlicedImages(paths, pipeline, slice_sizes, args.overlap, full_image),
        batch_size=args.batch_images,
        num_workers=args.workers,
        collate_fn=collate)

    coco_dets, rows, num_windows = [], [], 0
    with torch.no_grad():
        for batch in loader:
            crops = [c for _, _, cs in batch for c in cs]
            results = []
            for i in range(0, len(crops), 32):
                results += model.test_step(pseudo_collate(crops[i:i + 32]))
            k = 0
            for idx, windows, _ in batch:
                bboxes, scores, labels = [], [], []
                # windows always cover the whole image
                img_w = max(w[2] for w in windows)
                img_h = max(w[3] for w in windows)
                for x1, y1, x2, y2 in windows:
                    pred = results[k].pred_instances
                    k += 1
                    is_full = (x1, y1, x2, y2) == (0, 0, img_w, img_h)
                    if args.drop_edge_boxes and not is_full:
                        pred = pred[~touches_inner_edge(
                            pred.bboxes, x1, y1, x2, y2, img_w, img_h)]
                    if args.pre_merge_score_thr > 0:
                        pred = pred[pred.scores >= args.pre_merge_score_thr]
                    offset = pred.bboxes.new_tensor([x1, y1, x1, y1])
                    bboxes.append(pred.bboxes + offset)
                    scores.append(pred.scores)
                    labels.append(pred.labels)
                num_windows += len(windows)
                bboxes, scores, labels = merge(
                    torch.cat(bboxes), torch.cat(scores), torch.cat(labels),
                    args.merge, args.merge_thr, args.max_per_img,
                    args.class_agnostic)
                keep = scores >= args.score_thr
                bboxes = bboxes[keep].cpu().tolist()
                scores = scores[keep].cpu().tolist()
                labels = labels[keep].cpu().tolist()
                img = images[idx]
                parts = []
                for (x1, y1, x2, y2), s, lab in zip(bboxes, scores, labels):
                    coco_dets.append(
                        dict(
                            image_id=img['id'],
                            category_id=lab,  # mapped to cat ids below
                            bbox=[x1, y1, x2 - x1, y2 - y1],
                            score=s))
                    parts.append(f'{classes[lab]} {s:.2f} {round(x1)} '
                                 f'{round(y1)} {round(x2 - x1)} '
                                 f'{round(y2 - y1)}')
                rows.append((osp.splitext(img['file_name'])[0],
                             ' '.join(parts) if parts else 'none'))
            print(f'{len(rows)}/{len(images)} images', end='\r', flush=True)
    print(f'\n{len(images)} images, {num_windows / len(images):.1f} '
          f'windows per image, {len(coco_dets)} boxes')

    if args.out_csv:
        with open(args.out_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['image_id', 'PredictionString'])
            writer.writerows(rows)
        print(f'Saved to {args.out_csv}')

    if args.ann_file:
        cat_ids = coco.getCatIds(catNms=list(classes))
        name_to_cat = {c['name']: c['id'] for c in coco.loadCats(cat_ids)}
        label_to_cat = [name_to_cat[n] for n in classes]
        for d in coco_dets:
            d['category_id'] = label_to_cat[d['category_id']]
        # Standard COCO settings (up to 100 detections per image), which
        # reproduce the mAP/mAP_50 reported by mmdet during training
        coco_eval = COCOeval(coco, coco.loadRes(coco_dets), 'bbox')
        coco_eval.evaluate()
        coco_eval.accumulate()
        coco_eval.summarize()
        s = coco_eval.stats
        metrics = dict(
            mAP=s[0], mAP_50=s[1], mAP_75=s[2], mAP_s=s[3], mAP_m=s[4],
            mAP_l=s[5])
        # per-class AP50 (precision: [T, R, K, A, M])
        prec = coco_eval.eval['precision']
        for k, name in enumerate(classes):
            p = prec[0, :, k, 0, -1]
            metrics[f'{name}_AP50'] = float(p[p > -1].mean())
        print('RESULT ' + ' '.join(f'{k}={v:.4f}' for k, v in metrics.items()))
        if args.out_json:
            with open(args.out_json, 'w') as f:
                json.dump(dict(args=vars(args), metrics=metrics), f, indent=1)


if __name__ == '__main__':
    main()
