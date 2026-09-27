import json
import os.path as osp
from typing import Tuple

import cv2
import numpy as np
from mmcv.transforms import BaseTransform
from mmcv.transforms.utils import cache_randomness

from mmdet.registry import TRANSFORMS


@TRANSFORMS.register_module()
class DarkenBrightImage(BaseTransform):
    """Darken images, but only those categorized as bright.

    Step 2 of the darkening augmentation. Step 1
    (``projects/roketsan/tools/categorize_brightness.py``) measures every
    image's mean luminance offline and labels it ``bright`` or ``dark``; this
    transform looks the image up by file name and applies a gamma curve
    (gamma > 1) to bright images only, simulating dusk / low-light conditions
    without pushing already-dark night images into pure black. Images missing
    from the file are left unchanged.

    Must run before Mosaic/MixUp so the category matches the source image.

    Required Keys:

    - img
    - img_path

    Modified Keys:

    - img

    Args:
        brightness_file (str): JSON file written by
            ``categorize_brightness.py``.
        prob (float): Probability of darkening a bright image.
        gamma_range (tuple[float, float]): Range the gamma is sampled from.
            Output is ``255 * (img / 255) ** gamma``.
    """

    def __init__(self,
                 brightness_file: str,
                 prob: float = 0.5,
                 gamma_range: Tuple[float, float] = (1.5, 3.0)) -> None:
        assert 0 <= prob <= 1
        assert 1 <= gamma_range[0] <= gamma_range[1]
        self.brightness_file = brightness_file
        self.prob = prob
        self.gamma_range = gamma_range
        with open(brightness_file) as f:
            images = json.load(f)['images']
        self.bright_images = {
            name
            for name, info in images.items() if info['category'] == 'bright'
        }

    @cache_randomness
    def _sample_gamma(self):
        if np.random.rand() >= self.prob:
            return None
        return np.random.uniform(*self.gamma_range)

    def transform(self, results: dict) -> dict:
        if osp.basename(results['img_path']) not in self.bright_images:
            return results
        gamma = self._sample_gamma()
        if gamma is None:
            return results
        lut = (255 * (np.arange(256) / 255)**gamma).round().astype(np.uint8)
        results['img'] = cv2.LUT(results['img'], lut)
        return results

    def __repr__(self):
        return (f'{self.__class__.__name__}('
                f'brightness_file={self.brightness_file}, prob={self.prob}, '
                f'gamma_range={self.gamma_range}, '
                f'num_bright_images={len(self.bright_images)})')


@TRANSFORMS.register_module()
class RandomBrightnessContrast(BaseTransform):
    """Randomly change brightness and contrast, like albumentations'
    ``RandomBrightnessContrast``: ``img * alpha + beta * 255`` with
    ``alpha = 1 + U(-contrast_limit, contrast_limit)`` and
    ``beta = U(-brightness_limit, brightness_limit)``.

    Required Keys:

    - img

    Modified Keys:

    - img

    Args:
        brightness_limit (float): Max brightness shift as a fraction of 255.
        contrast_limit (float): Max contrast change as a fraction of 1.
        prob (float): Probability of applying the transform.
    """

    def __init__(self,
                 brightness_limit: float = 0.2,
                 contrast_limit: float = 0.2,
                 prob: float = 0.5) -> None:
        assert 0 <= prob <= 1
        self.brightness_limit = brightness_limit
        self.contrast_limit = contrast_limit
        self.prob = prob

    @cache_randomness
    def _sample_params(self):
        if np.random.rand() >= self.prob:
            return None
        alpha = 1 + np.random.uniform(-self.contrast_limit,
                                      self.contrast_limit)
        beta = np.random.uniform(-self.brightness_limit,
                                 self.brightness_limit)
        return alpha, beta

    def transform(self, results: dict) -> dict:
        params = self._sample_params()
        if params is None:
            return results
        alpha, beta = params
        lut = np.clip(np.arange(256) * alpha + beta * 255, 0,
                      255).astype(np.uint8)
        results['img'] = cv2.LUT(results['img'], lut)
        return results

    def __repr__(self):
        return (f'{self.__class__.__name__}('
                f'brightness_limit={self.brightness_limit}, '
                f'contrast_limit={self.contrast_limit}, prob={self.prob})')
