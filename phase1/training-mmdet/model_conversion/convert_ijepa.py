"""Convert an I-JEPA checkpoint's target encoder to a detectron2 ViT backbone.

Keeps only the EMA ``target_encoder`` (the ``encoder``, ``predictor`` and
optimizer state are dropped), strips DistributedDataParallel's ``module.``
prefix, drops the final ``norm`` (detectron2's ViT has none) and prefixes
the keys with ``backbone.net.`` for ViTDet's SimpleFeaturePyramid.

Example:
    python convert_ijepa.py ../checkpoints/IN1K-vit.h.16-448px-300e.pth.tar \
        ../checkpoints/ijepa_vith16_448_d2.pth
"""
import argparse

import torch


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('src')
    parser.add_argument('dst')
    args = parser.parse_args()

    ckpt = torch.load(args.src, map_location='cpu')
    print('checkpoint keys:', list(ckpt.keys()))
    enc = ckpt['target_encoder']
    new_sd, dropped = {}, []
    for k, v in enc.items():
        k = k.replace('module.', '', 1)
        if k.startswith('norm.'):
            dropped.append(k)
            continue
        new_sd['backbone.net.' + k] = v
    torch.save({'model': new_sd}, args.dst)
    blocks = {k.split('.')[3] for k in new_sd if k.startswith('backbone.net.blocks.')}
    print(f'{len(new_sd)} tensors saved ({len(blocks)} blocks), dropped '
          f'{dropped}; pos_embed {tuple(new_sd["backbone.net.pos_embed"].shape)}'
          f', patch_embed {tuple(new_sd["backbone.net.patch_embed.proj.weight"].shape)}')
    print(f'saved to {args.dst}')


if __name__ == '__main__':
    main()
