"""Run an Ultralytics YOLO model on a folder and write a submission CSV.

Same format as the MMDetection prediction CSVs:
    image_id,PredictionString
    img_000001,car 0.93 976 533 98 95 van 0.71 1012 276 150 76

Run with the YOLO environment (Ultralytics is kept out of the MMDetection
environment because it needs newer numpy/opencv):
    yolo/.venv/bin/python yolo/predict_yolo.py yolo/best.pt <img dir> out.csv \
        [--ann-file val.json]
"""
import argparse
import csv
import json
import os
import os.path as osp

from ultralytics import RTDETR, YOLO

IMG_EXTS = ('.jpg', '.jpeg', '.png', '.bmp')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('weights')
    parser.add_argument('img_dir')
    parser.add_argument('out_file')
    parser.add_argument('--ann-file', help='only predict the images of it')
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--conf', type=float, default=0.01)
    parser.add_argument('--max-det', type=int, default=300)
    parser.add_argument('--batch', type=int, default=16)
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
    paths = [osp.join(args.img_dir, n) for n in names]

    model = (RTDETR if args.arch == 'rtdetr' else YOLO)(args.weights)
    classes = model.names
    rows, num_boxes = [], 0
    for i in range(0, len(paths), 256):
        for res in model.predict(
                paths[i:i + 256],
                imgsz=args.imgsz,
                conf=args.conf,
                max_det=args.max_det,
                batch=args.batch,
                half=True,
                verbose=False,
                stream=True):
            boxes = res.boxes
            parts = []
            for (x1, y1, x2, y2), s, c in zip(boxes.xyxy.tolist(),
                                              boxes.conf.tolist(),
                                              boxes.cls.int().tolist()):
                parts.append(f'{classes[c]} {s:.2f} {round(x1)} {round(y1)} '
                             f'{round(x2 - x1)} {round(y2 - y1)}')
            num_boxes += len(parts)
            rows.append((osp.splitext(osp.basename(res.path))[0],
                         ' '.join(parts) if parts else 'none'))
        print(f'{len(rows)}/{len(paths)} images', end='\r', flush=True)

    with open(args.out_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['image_id', 'PredictionString'])
        writer.writerows(rows)
    print(f'\n{len(rows)} images, {num_boxes} boxes (conf >= {args.conf}); '
          f'saved to {args.out_file}')


if __name__ == '__main__':
    main()
