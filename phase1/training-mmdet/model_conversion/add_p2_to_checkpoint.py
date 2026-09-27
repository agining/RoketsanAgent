"""Convert a 3-level (P3-P5) RTMDet checkpoint for the 4-level P2 model.

The backbone and the P3-P5 part of ``CSPNeXtPAFPNWithP2`` keep their keys.
The head's per-level modules (``cls_convs``, ``reg_convs``, ``rtm_cls``,
``rtm_reg``) move up one level index, and the new level 0 (stride 4) is
initialized as a copy of the old stride-8 level. The new neck P2 branch is
not in the checkpoint and keeps its random initialization.

Example:
    python projects/roketsan/tools/add_p2_to_checkpoint.py \
        work_dirs/rtmdet_l_2h_a100_aug_ext/epoch_31.pth p2_init.pth
"""
import argparse
import re
from collections import OrderedDict

import torch

LEVEL_KEY = re.compile(
    r'^(bbox_head\.(?:cls_convs|reg_convs|rtm_cls|rtm_reg|rtm_obj))\.(\d+)\.'
    r'(.*)$')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('src')
    parser.add_argument('dst')
    args = parser.parse_args()

    ckpt = torch.load(args.src, map_location='cpu')
    state = ckpt['state_dict']
    new_state = OrderedDict()
    num_shifted = num_copied = 0
    for key, value in state.items():
        m = LEVEL_KEY.match(key)
        if m is None:
            new_state[key] = value
            continue
        prefix, level, rest = m.group(1), int(m.group(2)), m.group(3)
        new_state[f'{prefix}.{level + 1}.{rest}'] = value
        num_shifted += 1
        if level == 0:
            new_state[f'{prefix}.0.{rest}'] = value.clone()
            num_copied += 1
    torch.save(dict(meta=ckpt.get('meta', {}), state_dict=new_state), args.dst)
    print(f'{num_shifted} head keys moved up one level, {num_copied} copied '
          f'from stride 8 to the new stride-4 level; saved to {args.dst}')


if __name__ == '__main__':
    main()
