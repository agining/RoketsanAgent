import logging


def freeze_backbone_net(model):
    """Freeze the ViT inside ViTDet's SimpleFeaturePyramid.

    Sets ``requires_grad=False`` on ``model.backbone.net`` (the pretrained
    ViT), so detectron2's optimizer builder skips its parameters and no
    activations are kept for backward through it. The simple feature pyramid,
    RPN and ROI heads stay trainable. Returns the model, so it can be used as
    a LazyCall around the model config.
    """
    net = model.backbone.net
    for param in net.parameters():
        param.requires_grad = False
    frozen = sum(p.numel() for p in net.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logging.getLogger('detectron2').info(
        f'Frozen ViT backbone: {frozen / 1e6:.1f}M parameters frozen, '
        f'{trainable / 1e6:.1f}M trainable')
    return model
