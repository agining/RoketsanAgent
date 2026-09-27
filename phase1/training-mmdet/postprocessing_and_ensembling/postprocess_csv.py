"""Apply NMS and a confidence cut-off to a prediction CSV.

YOLO26 is NMS-free, so its low-confidence output keeps overlapping
duplicates of the same object; this runs NMS on them (per class, or
class-agnostic) and then drops boxes below ``--score-thr``.

Example:
    yolo/.venv/bin/python yolo/postprocess_csv.py in.csv out.csv \
        --nms-iou 0.65 --score-thr 0.4
"""
import argparse
import csv

import torch
from torchvision.ops import batched_nms, nms


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('in_csv')
    parser.add_argument('out_csv')
    parser.add_argument('--nms-iou', type=float, default=0.65)
    parser.add_argument('--class-agnostic', action='store_true')
    parser.add_argument('--score-thr', type=float, default=0.4)
    args = parser.parse_args()

    num_in = num_out = num_none = 0
    with open(args.in_csv) as fin, open(args.out_csv, 'w', newline='') as fout:
        writer = csv.writer(fout)
        writer.writerow(['image_id', 'PredictionString'])
        for row in csv.DictReader(fin):
            t = row['PredictionString'].split()
            groups = [] if t == ['none'] else [
                t[k:k + 6] for k in range(0, len(t), 6)
            ]
            num_in += len(groups)
            keep_parts = []
            if groups:
                labels = [g[0] for g in groups]
                label_ids = torch.tensor(
                    [sorted(set(labels)).index(lab) for lab in labels])
                scores = torch.tensor([float(g[1]) for g in groups])
                xywh = torch.tensor([[float(v) for v in g[2:]]
                                     for g in groups])
                boxes = torch.cat([xywh[:, :2], xywh[:, :2] + xywh[:, 2:]], 1)
                if args.class_agnostic:
                    keep = nms(boxes, scores, args.nms_iou)
                else:
                    keep = batched_nms(boxes, scores, label_ids, args.nms_iou)
                # keep is sorted by descending score
                keep_parts = [
                    ' '.join(groups[i]) for i in keep.tolist()
                    if scores[i] >= args.score_thr
                ]
            num_out += len(keep_parts)
            num_none += not keep_parts
            writer.writerow([
                row['image_id'], ' '.join(keep_parts) if keep_parts else 'none'
            ])
    print(f'{num_in} boxes in, {num_out} out; {num_none} images with none; '
          f'saved to {args.out_csv}')


if __name__ == '__main__':
    main()
