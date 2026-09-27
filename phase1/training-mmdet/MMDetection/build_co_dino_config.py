"""Resolve co_dino_5scale_r50_roketsan.py into a standalone config with num_classes set in every head.

Usage (from the MMDet root): python configs/roketsan/build_co_dino_config.py [--src ...] [--dst ...]
"""
import argparse

from mmengine.config import Config

parser = argparse.ArgumentParser()
parser.add_argument('--src', default='configs/roketsan/co_dino_5scale_r50_roketsan.py')
parser.add_argument('--dst', default='configs/roketsan/co_dino_5scale_r50_roketsan_full.py')
args = parser.parse_args()

cfg = Config.fromfile(args.src)
num_classes = len(cfg.metainfo['classes'])
cfg.model.query_head.num_classes = num_classes
for head in cfg.model.roi_head:
    head.bbox_head.num_classes = num_classes
for head in cfg.model.bbox_head:
    head.num_classes = num_classes
cfg.dump(args.dst)
print(f'wrote {args.dst} with num_classes={num_classes}')
