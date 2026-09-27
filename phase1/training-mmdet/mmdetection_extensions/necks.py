from typing import Sequence, Tuple

import torch
from mmcv.cnn import ConvModule
from torch import Tensor

from mmdet.models.layers import CSPLayer
from mmdet.models.necks import CSPNeXtPAFPN
from mmdet.registry import MODELS


@MODELS.register_module()
class CSPNeXtPAFPNWithP2(CSPNeXtPAFPN):
    """CSPNeXtPAFPN with an extra stride-4 (P2) output branch.

    The regular 3-level PAFPN runs unchanged on ``inputs[1:]`` (P3-P5), so a
    checkpoint of the 3-level model loads into it one-to-one and produces the
    same P3-P5 features. The P2 output is a separate top-down branch: the
    stride-8 top-down feature is reduced, upsampled, concatenated with the
    stride-4 backbone feature, fused by a CSP layer and projected to
    ``out_channels``. Outputs are ordered (P2, P3, P4, P5).

    Args:
        in_channels (Sequence[int]): Channels of the 4 backbone outputs,
            strides 4, 8, 16, 32.
        out_channels (int): Channels of every output level.
        **kwargs: Passed to :class:`CSPNeXtPAFPN`.
    """

    def __init__(self, in_channels: Sequence[int], out_channels: int,
                 **kwargs) -> None:
        assert len(in_channels) == 4, 'expects strides 4, 8, 16 and 32'
        super().__init__(in_channels[1:], out_channels, **kwargs)
        self.p2_in_channels = in_channels[0]
        conv_cfg = kwargs.get('conv_cfg')
        norm_cfg = kwargs.get('norm_cfg',
                              dict(type='BN', momentum=0.03, eps=0.001))
        act_cfg = kwargs.get('act_cfg', dict(type='Swish'))
        self.p2_reduce = ConvModule(
            in_channels[1],
            in_channels[0],
            1,
            conv_cfg=conv_cfg,
            norm_cfg=norm_cfg,
            act_cfg=act_cfg)
        self.p2_top_down = CSPLayer(
            in_channels[0] * 2,
            in_channels[0],
            num_blocks=kwargs.get('num_csp_blocks', 3),
            add_identity=False,
            use_depthwise=kwargs.get('use_depthwise', False),
            use_cspnext_block=True,
            expand_ratio=kwargs.get('expand_ratio', 0.5),
            conv_cfg=conv_cfg,
            norm_cfg=norm_cfg,
            act_cfg=act_cfg)
        self.p2_out_conv = ConvModule(
            in_channels[0],
            out_channels,
            3,
            padding=1,
            conv_cfg=conv_cfg,
            norm_cfg=norm_cfg,
            act_cfg=act_cfg)

    def forward(self, inputs: Tuple[Tensor, ...]) -> Tuple[Tensor, ...]:
        assert len(inputs) == 4
        p2_in, inputs = inputs[0], inputs[1:]
        num_levels = len(self.in_channels)

        # top-down path, as CSPNeXtPAFPN
        inner_outs = [inputs[-1]]
        for idx in range(num_levels - 1, 0, -1):
            feat_high = self.reduce_layers[num_levels - 1 - idx](
                inner_outs[0])
            inner_outs[0] = feat_high
            inner_out = self.top_down_blocks[num_levels - 1 - idx](
                torch.cat([self.upsample(feat_high), inputs[idx - 1]], 1))
            inner_outs.insert(0, inner_out)

        # bottom-up path, as CSPNeXtPAFPN
        outs = [inner_outs[0]]
        for idx in range(num_levels - 1):
            downsample_feat = self.downsamples[idx](outs[-1])
            outs.append(self.bottom_up_blocks[idx](
                torch.cat([downsample_feat, inner_outs[idx + 1]], 1)))
        outs = [conv(out) for conv, out in zip(self.out_convs, outs)]

        # extra P2 branch from the stride-8 top-down feature
        p2 = self.p2_top_down(
            torch.cat(
                [self.upsample(self.p2_reduce(inner_outs[0])), p2_in], 1))
        return (self.p2_out_conv(p2), *outs)
