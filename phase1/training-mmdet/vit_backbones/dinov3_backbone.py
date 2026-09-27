"""Frozen DINOv3 (or DINOv2) ViT as a multi-level detectron2 backbone.

Instead of ViTDet's single-layer simple feature pyramid, the pyramid is
built from several depths of the frozen ViT (as in DINO-style dense
probing): shallower layers keep more spatial detail and feed the fine
levels, deeper layers the coarse ones.

    layer_indices[0] -> x4 upsample -> p2 (stride 4)
    layer_indices[1] -> x2 upsample -> p3 (stride 8)
    layer_indices[2] -> identity     -> p4 (stride 16)
    layer_indices[3] -> 2x2 maxpool  -> p5 (stride 32)
    p5 -> maxpool                    -> p6 (stride 64, for the RPN)

Each intermediate output goes through the ViT's final LayerNorm, the CLS and
register tokens are dropped and the patch tokens are reshaped to a
(B, C, H/16, W/16) map. DINOv3 uses rotary position embeddings, so any
input size divisible by 16 works without interpolation.

DINOv2 checkpoints (e.g. facebook/dinov2-with-registers-large, patch 14)
are also supported: the image is resized to the nearest multiple of 14, the
ViT runs on that 14 px grid (its learned position embeddings are
interpolated by the model) and the feature maps are resampled bilinearly to
the stride-16 grid of the pyramid.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from detectron2.layers import Conv2d, ShapeSpec, get_norm
from detectron2.modeling.backbone import Backbone
from transformers import AutoModel, DINOv3ViTConfig, DINOv3ViTModel


def _load_vit(hf_model, config_overrides=None):
    if hf_model:
        return AutoModel.from_pretrained(
            hf_model, attn_implementation='sdpa', dtype=torch.float32)
    # random weights (pipeline tests only)
    config = DINOv3ViTConfig(**(config_overrides or {}))
    config._attn_implementation = 'sdpa'
    return DINOv3ViTModel(config)


class DINOv3MultiLevel(Backbone):
    """Frozen DINOv3 ViT + per-level fusion into a p2-p6 feature pyramid.

    Args:
        hf_model (str): Hugging Face model id or local directory of a
            DINOv3 ViT (``facebook/dinov3-vitl16-pretrain-lvd1689m``). Empty
            for random weights built from ``config_overrides``.
        layer_indices (list[int]): 0-based transformer layers for p2..p5.
        out_channels (int): Channels of every pyramid level.
        norm (str): Norm of the fusion convs ("LN" as in ViTDet).
        freeze (bool): Freeze the ViT (no gradients, kept in eval mode).
    """

    def __init__(self,
                 hf_model='',
                 layer_indices=(5, 11, 17, 23),
                 out_channels=256,
                 norm='LN',
                 freeze=True,
                 config_overrides=None):
        super().__init__()
        self.vit = _load_vit(hf_model, config_overrides)
        cfg = self.vit.config
        self.is_dinov3 = cfg.model_type == 'dinov3_vit'
        self.patch_size = cfg.patch_size
        self.num_prefix = 1 + cfg.num_register_tokens
        self.layer_indices = list(layer_indices)
        assert len(self.layer_indices) == 4
        assert max(self.layer_indices) < cfg.num_hidden_layers
        self.freeze = freeze
        if freeze:
            for p in self.vit.parameters():
                p.requires_grad = False
            self.vit.eval()

        dim = cfg.hidden_size
        use_bias = norm == ''

        def up2(cin, cout):
            return nn.ConvTranspose2d(cin, cout, kernel_size=2, stride=2)

        self.resamplers = nn.ModuleList([
            nn.Sequential(up2(dim, dim // 2), get_norm(norm, dim // 2),
                          nn.GELU(), up2(dim // 2, dim // 4)),
            up2(dim, dim // 2),
            nn.Identity(),
            nn.MaxPool2d(kernel_size=2, stride=2),
        ])
        in_dims = [dim // 4, dim // 2, dim, dim]
        self.fusion = nn.ModuleList([
            nn.Sequential(
                Conv2d(d, out_channels, 1, bias=use_bias,
                       norm=get_norm(norm, out_channels)),
                Conv2d(out_channels, out_channels, 3, padding=1,
                       bias=use_bias, norm=get_norm(norm, out_channels)))
            for d in in_dims
        ])
        self._out_features = ['p2', 'p3', 'p4', 'p5', 'p6']
        self._out_feature_strides = {
            'p2': 4, 'p3': 8, 'p4': 16, 'p5': 32, 'p6': 64}
        self._out_feature_channels = {k: out_channels
                                      for k in self._out_features}
        self._size_divisibility = 32

    @property
    def size_divisibility(self):
        return self._size_divisibility

    @property
    def padding_constraints(self):
        return {'size_divisibility': self._size_divisibility}

    def train(self, mode=True):
        super().train(mode)
        if self.freeze:
            self.vit.eval()  # no dropout/drop-path in the frozen ViT
        return self

    def _vit_features(self, x):
        if not self.is_dinov3:
            return self._dinov2_features(x)
        b, _, h, w = x.shape
        gh, gw = h // self.patch_size, w // self.patch_size
        vit = self.vit
        hidden = vit.embeddings(x.to(vit.embeddings.patch_embeddings.weight.dtype))
        rope = vit.rope_embeddings(x)
        feats, wanted = [], set(self.layer_indices)
        for i, layer in enumerate(vit.model.layer):
            hidden = layer(hidden, position_embeddings=rope)
            if i in wanted:
                tokens = vit.norm(hidden)[:, self.num_prefix:]
                feats.append(tokens.transpose(1, 2).reshape(b, -1, gh, gw))
            if i >= max(self.layer_indices):
                break
        return feats

    def _dinov2_features(self, x):
        b, _, h, w = x.shape
        p = self.patch_size
        gh, gw = round(h / p), round(w / p)
        if (gh * p, gw * p) != (h, w):
            x = F.interpolate(x, size=(gh * p, gw * p), mode='bilinear',
                              align_corners=False)
        out = self.vit(pixel_values=x, output_hidden_states=True)
        # hidden_states[0] is the embedding output, [i + 1] is after layer i
        feats = []
        for i in self.layer_indices:
            tokens = self.vit.layernorm(out.hidden_states[i + 1])
            fmap = tokens[:, self.num_prefix:].transpose(1, 2).reshape(
                b, -1, gh, gw)
            feats.append(F.interpolate(
                fmap.float(), size=(h // 16, w // 16), mode='bilinear',
                align_corners=False))
        return feats

    def forward(self, x):
        if self.freeze:
            with torch.no_grad():
                feats = self._vit_features(x)
        else:
            feats = self._vit_features(x)
        outs = {}
        for name, feat, resample, fuse in zip(
                ['p2', 'p3', 'p4', 'p5'], feats, self.resamplers,
                self.fusion):
            outs[name] = fuse(resample(feat.float()))
        outs['p6'] = nn.functional.max_pool2d(outs['p5'], 1, stride=2)
        return outs

    def output_shape(self):
        return {
            name: ShapeSpec(channels=self._out_feature_channels[name],
                            stride=self._out_feature_strides[name])
            for name in self._out_features
        }
