"""RF-DETR criterion with an extra penalty for confusing specific class pairs (car <-> van).

RF-DETR's classification loss (IA-BCE) is a per-class sigmoid loss. For a query matched to a ground-truth box of
class ``a``, the term on class ``b != a`` is the loss for scoring that query as ``b``. This criterion multiplies that
term by ``penalty`` for every configured confusion pair (a, b), in all decoder / auxiliary / encoder layers.
Everything else (positives, other negatives, unmatched queries, box losses) is unchanged.

Usage: call ``install(pairs=[(1, 3), (3, 1)], penalty=3.0)`` before the model is built.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import Tensor

import rfdetr.models.lwdetr as lwdetr
from rfdetr.models.criterion import SetCriterion
from rfdetr.utilities import box_ops

CONFUSION_PAIRS: list[tuple[int, int]] = []
CONFUSION_PENALTY = 1.0


class ConfusionPenaltySetCriterion(SetCriterion):
    """SetCriterion whose IA-BCE loss up-weights the listed (true class, predicted class) confusions."""

    def loss_labels(self, outputs, targets, indices, num_boxes, log=True, matched_targets=None):
        if not self.ia_bce_loss or not CONFUSION_PAIRS or CONFUSION_PENALTY == 1.0:
            return super().loss_labels(outputs, targets, indices, num_boxes, log, matched_targets)
        if not getattr(self, "_announced", False):
            print(f"[confusion_criterion] active: pairs={CONFUSION_PAIRS} penalty={CONFUSION_PENALTY}", flush=True)
            self._announced = True

        src_logits = outputs["pred_logits"]
        valid_mask = self._matched_valid_mask(targets, indices)
        if matched_targets is None:
            idx = self._get_src_permutation_idx(indices)
            target_classes_o = torch.cat([t["labels"][J] for t, (_, J) in zip(targets, indices)])
            target_boxes = torch.cat([t["boxes"][i] for t, (_, i) in zip(targets, indices)], dim=0)
        else:
            idx = matched_targets.source_indices
            target_classes_o = matched_targets.labels
            target_boxes = matched_targets.boxes

        # --- stock IA-BCE weights (same as SetCriterion.loss_labels, ia_bce branch) ---
        alpha, gamma = self.focal_alpha, 2
        src_boxes = outputs["pred_boxes"][idx]
        iou_targets, _ = box_ops.elementwise_box_iou(
            box_ops.box_cxcywh_to_xyxy(src_boxes.detach()), box_ops.box_cxcywh_to_xyxy(target_boxes))
        pos_ious = iou_targets.clone().detach()
        prob = src_logits.sigmoid()
        pos_weights = torch.zeros_like(src_logits)
        neg_weights = prob**gamma
        pos_ind = (*idx, target_classes_o)
        t = torch.clamp(prob[pos_ind].pow(alpha) * pos_ious.pow(1 - alpha), 0.01).detach()
        if valid_mask is None:
            pos_weights[pos_ind] = t.to(pos_weights.dtype)
            neg_weights[pos_ind] = 1 - t.to(neg_weights.dtype)
        else:
            keep = valid_mask.to(torch.bool)
            pos_weights[pos_ind] = (t * valid_mask).to(pos_weights.dtype)
            neg_weights[pos_ind] = torch.where(keep, (1 - t).to(neg_weights.dtype), neg_weights[pos_ind])
        loss_ce = neg_weights * src_logits - F.logsigmoid(src_logits) * (pos_weights + neg_weights)

        # --- confusion penalty: scale the (matched query, wrong class) terms of the listed pairs ---
        confusion_weights = torch.ones_like(loss_ce)
        keep = valid_mask.to(torch.bool) if valid_mask is not None else torch.ones_like(target_classes_o, dtype=torch.bool)
        for true_cls, wrong_cls in CONFUSION_PAIRS:
            sel = (target_classes_o == true_cls) & keep
            if sel.any():
                sel = sel.to(idx[0].device)  # matcher indices may live on the CPU
                confusion_weights[idx[0][sel], idx[1][sel], wrong_cls] = CONFUSION_PENALTY
        loss_ce = (loss_ce * confusion_weights).sum() / num_boxes

        losses = {"loss_ce": loss_ce}
        if log:
            matched_logits = src_logits[idx]
            losses["class_error"] = 100 - 100 * (matched_logits.argmax(-1) == target_classes_o).float().mean()
        return losses


def install(pairs: list[tuple[int, int]], penalty: float) -> None:
    """Make RF-DETR build ConfusionPenaltySetCriterion instead of SetCriterion."""
    global CONFUSION_PAIRS, CONFUSION_PENALTY
    CONFUSION_PAIRS = list(pairs)
    CONFUSION_PENALTY = float(penalty)
    lwdetr.SetCriterion = ConfusionPenaltySetCriterion
