"""Run an MMDetection model on a folder of images and dump predictions as JSON.

Output format:
{"img_xxx": [{"label": str, "confidence": float, "bbox": [x, y, w, h]}, ...], ...}
"""
import argparse
import json
from pathlib import Path

from torchvision.ops import nms

from mmdet.apis import inference_detector, init_detector

IMG_EXTS = {'.jpg', '.jpeg', '.png', '.bmp'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('config')
    parser.add_argument('checkpoint')
    parser.add_argument('img_dir')
    parser.add_argument('out')
    parser.add_argument('--score-thr', type=float, default=0.25)
    parser.add_argument('--device', default='cuda:0')
    parser.add_argument(
        '--agnostic-iou', type=float, default=None,
        help='if set, apply class-agnostic NMS with this IoU threshold so '
        'overlapping boxes of different classes keep only the best score')
    args = parser.parse_args()

    model = init_detector(args.config, args.checkpoint, device=args.device)
    classes = model.dataset_meta['classes']

    imgs = sorted(p for p in Path(args.img_dir).iterdir()
                  if p.suffix.lower() in IMG_EXTS)
    results = {}
    for img in imgs:
        pred = inference_detector(model, str(img)).pred_instances.cpu()
        if args.agnostic_iou is not None:
            pred = pred[nms(pred.bboxes, pred.scores, args.agnostic_iou)]
        dets = []
        for (x1, y1, x2, y2), score, label in zip(
                pred.bboxes.tolist(), pred.scores.tolist(),
                pred.labels.tolist()):
            if score < args.score_thr:
                continue
            dets.append({
                'label': classes[label],
                'confidence': round(score, 2),
                'bbox': [round(x1), round(y1),
                         round(x2 - x1), round(y2 - y1)],
            })
        results[img.stem] = dets
        print(f'{img.stem}: {len(dets)} detections')

    with open(args.out, 'w') as f:
        json.dump(results, f, indent=1)
    print(f'Wrote {len(results)} images to {args.out}')


if __name__ == '__main__':
    main()
