"""Draw the boxes of a prediction CSV on its images for manual inspection.

Reads a CSV in the submission format (``image_id,PredictionString`` with
``label score x y w h`` groups) and writes one annotated JPEG per image.
Each class has its own color and every box is labelled with its class and
score; a legend with the per-class box counts is drawn in the top-left
corner.

Example:
    python projects/roketsan/tools/visualize_csv.py \
        ../../predictions/test_predictions_sahi640.csv <test images dir> \
        ../../predictions/vis_test_sahi640 --score-thr 0.3
"""
import argparse
import csv
import os
import os.path as osp
from collections import Counter
from multiprocessing import Pool

import cv2

# BGR
COLORS = {
    'bus': (0, 165, 255),  # orange
    'car': (80, 200, 60),  # green
    'truck': (60, 60, 230),  # red
    'van': (230, 160, 40),  # blue
}
DEFAULT_COLOR = (200, 200, 200)
IMG_EXTS = ('.jpg', '.jpeg', '.png', '.bmp')


def parse_predictions(pred_str):
    tokens = pred_str.split()
    if tokens == ['none']:
        return []
    assert len(tokens) % 6 == 0, f'malformed PredictionString: {pred_str!r}'
    return [(tokens[k], float(tokens[k + 1]), *map(float, tokens[k + 2:k + 6]))
            for k in range(0, len(tokens), 6)]


def draw(job):
    img_path, out_path, preds, score_thr, quality = job
    img = cv2.imread(img_path)
    if img is None:
        return f'cannot read {img_path}'
    h, w = img.shape[:2]
    scale = max(w, h) / 1400  # line/text size relative to a 1400 px image
    thickness = max(1, round(2 * scale))
    font_scale = 0.45 * scale
    font_thick = max(1, round(scale))

    kept = [p for p in preds if p[1] >= score_thr]
    # Draw low scores first so high-score boxes end up on top
    for label, score, x, y, bw, bh in sorted(kept, key=lambda p: p[1]):
        color = COLORS.get(label, DEFAULT_COLOR)
        x1, y1, x2, y2 = round(x), round(y), round(x + bw), round(y + bh)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
        text = f'{label} {score:.2f}'
        (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX,
                                         font_scale, font_thick)
        ty = y1 - 2 if y1 - th - base - 2 >= 0 else y1 + th + base + 2
        cv2.rectangle(img, (x1, ty - th - base), (x1 + tw + 2, ty), color, -1)
        cv2.putText(img, text, (x1 + 1, ty - base), cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale, (0, 0, 0), font_thick, cv2.LINE_AA)

    # Legend with per-class counts
    counts = Counter(p[0] for p in kept)
    lines = [(f'score >= {score_thr}: {len(kept)} boxes', (255, 255, 255))]
    lines += [(f'{name}: {counts.get(name, 0)}', color)
              for name, color in COLORS.items()]
    lscale = 0.7 * scale
    lthick = max(1, round(1.5 * scale))
    line_h = int(32 * scale)
    box_w = int(330 * scale)
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (box_w, line_h * len(lines) + 10),
                  (0, 0, 0), -1)
    img = cv2.addWeighted(overlay, 0.6, img, 0.4, 0)
    for i, (text, color) in enumerate(lines):
        cv2.putText(img, text, (8, line_h * (i + 1)),
                    cv2.FONT_HERSHEY_SIMPLEX, lscale, color, lthick,
                    cv2.LINE_AA)

    cv2.imwrite(out_path, img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return None


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('csv_file')
    parser.add_argument('img_dir')
    parser.add_argument('out_dir')
    parser.add_argument('--score-thr', type=float, default=0.3)
    parser.add_argument('--quality', type=int, default=90)
    parser.add_argument('--workers', type=int, default=os.cpu_count())
    return parser.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    files = {
        osp.splitext(n)[0]: n
        for n in os.listdir(args.img_dir) if n.lower().endswith(IMG_EXTS)
    }
    jobs = []
    with open(args.csv_file) as f:
        for row in csv.DictReader(f):
            name = files[row['image_id']]
            jobs.append((osp.join(args.img_dir, name),
                         osp.join(args.out_dir,
                                  osp.splitext(name)[0] + '.jpg'),
                         parse_predictions(row['PredictionString']),
                         args.score_thr, args.quality))
    with Pool(args.workers) as pool:
        errors = [e for e in pool.imap_unordered(draw, jobs, chunksize=8)
                  if e]
    for e in errors:
        print(e)
    print(f'Wrote {len(jobs) - len(errors)} images to {args.out_dir}')


if __name__ == '__main__':
    main()
