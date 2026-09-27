import torch
import torch.nn.functional as F

from mmdet.models.losses import QualityFocalLoss
from mmdet.models.losses.utils import weight_reduce_loss
from mmdet.registry import MODELS


@MODELS.register_module()
class ClassBalancedQualityFocalLoss(QualityFocalLoss):
    """Quality Focal Loss with per-class reweighting of positive samples.

    Each positive prediction's loss (its whole row over all classes, as a
    softmax class weight would) is multiplied by the weight of its
    ground-truth class; background predictions keep weight 1. This raises the
    classification loss of minority classes and lowers it for the majority
    class. Weights come from ``projects/roketsan/tools/class_weights.py``.

    Args:
        class_weight (list[float]): One weight per class.
        **kwargs: Passed to :class:`QualityFocalLoss`.
    """

    def __init__(self, class_weight, **kwargs):
        super().__init__(**kwargs)
        self.register_buffer(
            'class_weight', torch.tensor(class_weight, dtype=torch.float32))

    def forward(self, pred, target, weight=None, **kwargs):
        assert isinstance(target, tuple), \
            'ClassBalancedQualityFocalLoss needs (label, score) targets'
        label = target[0]
        num_classes = pred.size(1)
        assert len(self.class_weight) == num_classes
        # FG cat_id: [0, num_classes - 1], BG cat_id: num_classes
        pos = (label >= 0) & (label < num_classes)
        sample_weight = pred.new_ones(label.shape)
        sample_weight[pos] = self.class_weight.to(pred.dtype)[label[pos]]
        if weight is not None:
            sample_weight = sample_weight * weight
        return super().forward(pred, target, sample_weight, **kwargs)


@MODELS.register_module()
class ConfusionPenaltyQualityFocalLoss(ClassBalancedQualityFocalLoss):
    """Class-balanced Quality Focal Loss with a class-confusion penalty.

    On top of the per-class weights of
    :class:`ClassBalancedQualityFocalLoss`, the loss of a positive prediction
    of ground-truth class ``i`` on the score of another class ``j`` (the term
    that pushes the wrong class ``j`` down) is multiplied by
    ``confusion_penalty[i][j]``, so pairs of classes the model often confuses
    are penalized more. Background predictions are unaffected. Penalties come
    from ``projects/roketsan/tools/confusion_penalty.py``.

    Args:
        class_weight (list[float]): One weight per class.
        confusion_penalty (list[list[float]]): ``C x C`` matrix, rows are the
            ground-truth class, columns the confused class. The diagonal is
            ignored (the true-class term is not penalized).
        **kwargs: Passed to :class:`QualityFocalLoss`.
    """

    def __init__(self, class_weight, confusion_penalty, **kwargs):
        super().__init__(class_weight, **kwargs)
        assert not self.activated, 'only logits input is supported'
        penalty = torch.tensor(confusion_penalty, dtype=torch.float32)
        assert penalty.shape == (len(class_weight), len(class_weight))
        penalty.fill_diagonal_(1.0)
        self.register_buffer('confusion_penalty', penalty)

    def forward(self,
                pred,
                target,
                weight=None,
                avg_factor=None,
                reduction_override=None):
        assert reduction_override in (None, 'none', 'mean', 'sum')
        reduction = (
            reduction_override if reduction_override else self.reduction)
        assert isinstance(target, tuple), \
            'ConfusionPenaltyQualityFocalLoss needs (label, score) targets'
        label, score = target
        num_classes = pred.size(1)

        # Element-wise QFL, as mmdet's quality_focal_loss before its sum over
        # classes: negatives are supervised by 0 quality score
        pred_sigmoid = pred.sigmoid()
        loss = F.binary_cross_entropy_with_logits(
            pred, pred.new_zeros(pred.shape),
            reduction='none') * pred_sigmoid.pow(self.beta)
        # FG cat_id: [0, num_classes - 1], BG cat_id: num_classes
        pos = ((label >= 0) & (label < num_classes)).nonzero().squeeze(1)
        pos_label = label[pos].long()
        # positives are supervised by bbox quality (IoU) score
        scale_factor = score[pos] - pred_sigmoid[pos, pos_label]
        loss[pos, pos_label] = F.binary_cross_entropy_with_logits(
            pred[pos, pos_label], score[pos],
            reduction='none') * scale_factor.abs().pow(self.beta)

        # Penalize the wrong-class scores of positives by confusion amount
        loss[pos] = loss[pos] * self.confusion_penalty.to(
            loss.dtype)[pos_label]
        loss = loss.sum(dim=1)

        sample_weight = pred.new_ones(label.shape)
        sample_weight[pos] = self.class_weight.to(pred.dtype)[pos_label]
        if weight is not None:
            sample_weight = sample_weight * weight
        loss = weight_reduce_loss(loss, sample_weight, reduction, avg_factor)
        return self.loss_weight * loss


@MODELS.register_module()
class WIoULoss(torch.nn.Module):
    """Wise-IoU box loss (https://arxiv.org/abs/2301.10051), v1 or v3.

    v1 scales the IoU loss by a distance attention
    ``R = exp(center_dist^2 / (Wg^2 + Hg^2))`` (enclosing box size detached),
    which focuses on boxes whose centers are off. v3 adds a dynamic
    non-monotonic focusing factor ``r = beta / (delta * alpha**(beta - delta))``
    with outlier degree ``beta = L_IoU / running_mean(L_IoU)``: ordinary
    boxes get the most gradient, while very good boxes (small beta) and
    low-quality outliers (large beta) get less.

    Args:
        version (str): 'v1' or 'v3'.
        alpha (float), delta (float): v3 focusing parameters.
        momentum (float): Update rate of the running mean of L_IoU.
        eps (float): Numerical epsilon.
        reduction (str), loss_weight (float): As mmdet's IoU losses.
    """

    def __init__(self,
                 version='v3',
                 alpha=1.9,
                 delta=3.0,
                 momentum=0.01,
                 eps=1e-7,
                 reduction='mean',
                 loss_weight=1.0):
        super().__init__()
        assert version in ('v1', 'v3')
        self.version = version
        self.alpha = alpha
        self.delta = delta
        self.momentum = momentum
        self.eps = eps
        self.reduction = reduction
        self.loss_weight = loss_weight
        self.register_buffer('iou_loss_mean', torch.tensor(1.0))

    def forward(self,
                pred,
                target,
                weight=None,
                avg_factor=None,
                reduction_override=None):
        if weight is not None and not torch.any(weight > 0):
            if pred.dim() == weight.dim() + 1:
                weight = weight.unsqueeze(1)
            return (pred * weight).sum()  # 0
        assert reduction_override in (None, 'none', 'mean', 'sum')
        reduction = (
            reduction_override if reduction_override else self.reduction)
        if weight is not None and weight.dim() > 1:
            weight = weight.mean(-1)
        pred, target = pred.float(), target.float()

        # IoU
        lt = torch.max(pred[:, :2], target[:, :2])
        rb = torch.min(pred[:, 2:], target[:, 2:])
        inter = (rb - lt).clamp(min=0).prod(-1)
        area_p = (pred[:, 2:] - pred[:, :2]).clamp(min=0).prod(-1)
        area_t = (target[:, 2:] - target[:, :2]).clamp(min=0).prod(-1)
        iou = inter / (area_p + area_t - inter + self.eps)
        iou_loss = 1 - iou

        # v1: distance attention, enclosing box size detached
        center_p = (pred[:, :2] + pred[:, 2:]) / 2
        center_t = (target[:, :2] + target[:, 2:]) / 2
        enclose_wh = (torch.max(pred[:, 2:], target[:, 2:]) -
                      torch.min(pred[:, :2], target[:, :2])).detach()
        r_wiou = torch.exp(((center_p - center_t)**2).sum(-1) /
                           ((enclose_wh**2).sum(-1) + self.eps))
        loss = r_wiou * iou_loss

        if self.version == 'v3':
            if self.training:
                self.iou_loss_mean.mul_(1 - self.momentum).add_(
                    self.momentum * iou_loss.detach().mean())
            beta = iou_loss.detach() / self.iou_loss_mean.clamp(min=self.eps)
            focus = beta / (self.delta * self.alpha**(beta - self.delta))
            loss = focus * loss

        loss = weight_reduce_loss(loss, weight, reduction, avg_factor)
        return self.loss_weight * loss
