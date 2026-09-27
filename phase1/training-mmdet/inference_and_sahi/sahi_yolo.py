"""SAHI-style sliced inference for an Ultralytics YOLO model -> CSV.

Same procedure as projects/roketsan/tools/sahi_eval.py for RTMDet: the full
image plus overlapping ``--slice-size`` tiles are predicted, tile boxes that
touch a tile edge inside the image (objects cut by the tile) are dropped,
boxes are shifted to image coordinates and merged with NMS; then boxes below
``--score-thr`` are removed.

Example:
    yolo/.venv/bin/python yolo/sahi_yolo.py yolo/best.pt <img dir> out.csv \
        --ann-file val.json --slice-size 640 --score-thr 0.4
"""
import argparse
import csv
import json
import os
import os.path as osp

import cv2
import torch
from torchvision.ops import batched_nms, nms
from ultralytics import RTDETR, YOLO

IMG_EXTS = ('.jpg', '.jpeg', '.png', '.bmp')


def slice_starts(length, size, overlap):
    if length <= size:
        return [0]
    step = max(int(size * (1 - overlap)), 1)
    starts = list(range(0, length - size, step))
    starts.append(length - size)
    return starts


def make_windows(w, h, size, overlap):
    windows = [(0, 0, w, h)]
    if size < max(w, h):
        for y in slice_starts(h, size, overlap):
            for x in slice_starts(w, size, overlap):
                windows.append((x, y, min(x + size, w), min(y + size, h)))
    return windows


def touches_inner_edge(b, x1, y1, x2, y2, img_w, img_h, margin=2):
    w, h = x2 - x1, y2 - y1
    mask = torch.zeros(len(b), dtype=torch.bool, device=b.device)
    if x1 > 0:
        mask |= b[:, 0] <= margin
    if y1 > 0:
        mask |= b[:, 1] <= margin
    if x2 < img_w:
        mask |= b[:, 2] >= w - margin
    if y2 < img_h:
        mask |= b[:, 3] >= h - margin
    return mask


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('weights')
    parser.add_argument('img_dir')
    parser.add_argument('out_file')
    parser.add_argument('--ann-file', help='only predict the images of it')
    parser.add_argument('--slice-size', type=int, default=640)
    parser.add_argument('--overlap', type=float, default=0.2)
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--tile-conf', type=float, default=0.01)
    parser.add_argument('--nms-iou', type=float, default=0.65)
    parser.add_argument('--class-agnostic', action='store_true')
    parser.add_argument('--score-thr', type=float, default=0.4)
    parser.add_argument('--max-per-img', type=int, default=300)
    parser.add_argument('--batch', type=int, default=32)
    parser.add_argument(
        '--arch', choices=['yolo', 'rtdetr'], default='yolo',
        help='rtdetr: load with the RTDETR class (NMS-free predictor)')
    args = parser.parse_args()

    if args.ann_file:
        with open(args.ann_file) as f:
            names = sorted(i['file_name'] for i in json.load(f)['images'])
    else:
        names = sorted(n for n in os.listdir(args.img_dir)
                       if n.lower().endswith(IMG_EXTS))

    model = (RTDETR if args.arch == 'rtdetr' else YOLO)(args.weights)
    classes = model.names
    rows, num_boxes, num_windows = [], 0, 0
    for n, name in enumerate(names):
        img = cv2.imread(osp.join(args.img_dir, name))
        h, w = img.shape[:2]
        windows = make_windows(w, h, args.slice_size, args.overlap)
        num_windows += len(windows)
        crops = [img[y1:y2, x1:x2] for x1, y1, x2, y2 in windows]
        results = []
        for i in range(0, len(crops), args.batch):
            results += model.predict(
                crops[i:i + args.batch], imgsz=args.imgsz,
                conf=args.tile_conf, max_det=300, half=True, verbose=False)
        bboxes, scores, labels = [], [], []
        for (x1, y1, x2, y2), res in zip(windows, results):
            b = res.boxes.xyxy
            s = res.boxes.conf
            c = res.boxes.cls
            if (x1, y1, x2, y2) != (0, 0, w, h):
                keep = ~touches_inner_edge(b, x1, y1, x2, y2, w, h)
                b, s, c = b[keep], s[keep], c[keep]
            bboxes.append(b + b.new_tensor([x1, y1, x1, y1]))
            scores.append(s)
            labels.append(c)
        b, s, c = torch.cat(bboxes), torch.cat(scores), torch.cat(labels)
        if len(s):
            keep = (nms(b, s, args.nms_iou) if args.class_agnostic else
                    batched_nms(b, s, c.long(), args.nms_iou))
            keep = keep[s[keep] >= args.score_thr][:args.max_per_img]
            b, s, c = b[keep], s[keep], c[keep]
        parts = [
            f'{classes[int(lab)]} {sc:.2f} {round(x1)} {round(y1)} '
            f'{round(x2 - x1)} {round(y2 - y1)}'
            for (x1, y1, x2, y2), sc, lab in zip(b.tolist(), s.tolist(),
                                                 c.tolist())
        ]
        num_boxes += len(parts)
        rows.append((osp.splitext(name)[0], ' '.join(parts) if parts else
                     'none'))
        if n % 50 == 0:
            print(f'{n + 1}/{len(names)} images', end='\r', flush=True)

    with open(args.out_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['image_id', 'PredictionString'])
        writer.writerows(rows)
    num_none = sum(r[1] == 'none' for r in rows)
    print(f'\n{len(rows)} images, {num_windows / len(rows):.1f} windows per '
          f'image, {num_boxes} boxes (score >= {args.score_thr}), '
          f'{num_none} images with none; saved to {args.out_file}')


if __name__ == '__main__':
    main()
