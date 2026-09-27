"""Step 1 of the bright-image darkening augmentation.

Measure the mean luminance of every image in a folder and categorize each one
as ``bright`` or ``dark``. The result is written to a JSON file that the
``DarkenBrightImage`` transform (step 2, see ``projects/roketsan/transforms.py``)
reads at training time, so only bright images are ever darkened.

The threshold defaults to Otsu's method over the per-image mean luminances,
i.e. the split that best separates the two brightness populations of the
dataset. A fixed threshold (0-255) can be given instead.

Example:
    python projects/roketsan/tools/categorize_brightness.py \
        /path/to/train/images ../../dataset/train_brightness.json
"""
import argparse
import json
import os
from multiprocessing import Pool

import cv2
import numpy as np

IMG_EXTS = ('.jpg', '.jpeg', '.png', '.bmp')


def mean_luminance(path):
    # 1/4-resolution grayscale decode is plenty for a global mean and ~10x
    # faster than decoding the full image
    img = cv2.imread(path, cv2.IMREAD_REDUCED_GRAYSCALE_4)
    if img is None:
        raise IOError(f'Cannot read image: {path}')
    return float(img.mean())


def otsu_threshold(values):
    """Otsu's threshold over a 1-D array of values in [0, 255]."""
    hist, edges = np.histogram(values, bins=256, range=(0, 256))
    hist = hist.astype(np.float64)
    centers = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m0 = np.cumsum(hist * centers)
    mu0 = m0 / np.maximum(w0, 1e-12)
    mu1 = (m0[-1] - m0) / np.maximum(w1, 1e-12)
    between_var = w0 * w1 * (mu0 - mu1)**2
    return float(edges[np.argmax(between_var) + 1])


def parse_args():
    parser = argparse.ArgumentParser(
        description='Categorize images as bright or dark by mean luminance')
    parser.add_argument('img_dir', help='folder with the images')
    parser.add_argument('out_file', help='output JSON file')
    parser.add_argument(
        '--threshold',
        default='otsu',
        help='"otsu" or a fixed mean-luminance threshold in [0, 255]; '
        'images with mean luminance >= threshold are "bright"')
    parser.add_argument('--workers', type=int, default=os.cpu_count())
    return parser.parse_args()


def main():
    args = parse_args()
    names = sorted(
        n for n in os.listdir(args.img_dir) if n.lower().endswith(IMG_EXTS))
    paths = [os.path.join(args.img_dir, n) for n in names]
    with Pool(args.workers) as pool:
        means = np.array(pool.map(mean_luminance, paths, chunksize=32))

    if args.threshold == 'otsu':
        threshold = otsu_threshold(means)
    else:
        threshold = float(args.threshold)

    images = {
        name: dict(
            mean_luminance=round(m, 2),
            category='bright' if m >= threshold else 'dark')
        for name, m in zip(names, means)
    }
    num_bright = int((means >= threshold).sum())
    with open(args.out_file, 'w') as f:
        json.dump(dict(threshold=threshold, images=images), f, indent=1)

    print(f'{len(names)} images, mean luminance: '
          f'min {means.min():.1f}, median {np.median(means):.1f}, '
          f'max {means.max():.1f}')
    print(f'threshold {threshold:.1f}: {num_bright} bright, '
          f'{len(names) - num_bright} dark')
    hist, edges = np.histogram(means, bins=16, range=(0, 256))
    for count, lo in zip(hist, edges[:-1]):
        print(f'  {lo:5.0f}-{lo + 16:<5.0f} {count:5d} {"#" * (count // 20)}')
    print(f'Saved to {args.out_file}')


if __name__ == '__main__':
    main()
