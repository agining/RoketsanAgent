# Code changes — Roketsan vehicle detection

Code only (no configs, logs, data or checkpoints). Class ids everywhere: bus=0, car=1, truck=2, van=3.

## DEIMv2/ — library fix (modified upstream files)
Upstream: https://github.com/Intellindust-AI-Lab/DEIMv2 at the commit in `UPSTREAM_COMMIT.txt`.
- `deimv2_oom_fix.patch` — `git apply` it on a fresh clone.
- `modified_files/engine/deim/box_ops.py` — adds `paired_box_iou` / `paired_generalized_box_iou`
  (element-wise IoU/GIoU, O(N) memory).
- `modified_files/engine/deim/deim_criterion.py` — replaces every `torch.diag(pairwise NxN IoU)` with the
  paired versions. Fixes the CUDA OOM once Mosaic/CopyBlend produce images with hundreds of boxes;
  results are numerically identical.

## RF-DETR/ — scripts written for RF-DETR Large (rfdetr 1.11.0)
- `training/train_rfdetr.py` — fine-tuning entry point (`--resolution`, `--dataset-dir`, `--init-weights`,
  `--car-van-penalty`, batch / grad-accum / epochs).
- `training/confusion_criterion.py` — `SetCriterion` subclass: multiplies the IA-BCE loss terms for
  car-predicted-as-van and van-predicted-as-car by a penalty (3x used); everything else unchanged.
- `evaluation/eval_sahi.py` — COCO mAP50 / mAP50-95 of a checkpoint with whole-image or SAHI sliced inference.
- `inference/predict_test_sahi.py` — test-set prediction with SAHI (960 px tiles + full image),
  class-agnostic NMS, confidence >= 0.50, writes `label confidence x y w h` (supports `--shard/--num-shards`).
- `inference/merge_submission_shards.py` — merges shard CSVs into sample_submission order and checks coverage.
- `inference/run_predict.sh` — runs 3 prediction shards in parallel on one GPU, then merges.

## MMDetection/
- `build_co_dino_config.py` — resolves the Co-DINO config and sets `num_classes` in all three heads
  (they sit in list-valued fields a child config cannot partially override). No MMDetection library code changed.

## data_preparation/
- `csv_to_coco.py` — converts `train_annotations.csv` / `val_annotations.csv` (x, y, w, h top-left pixels)
  to COCO json; keeps unannotated images from `train.txt` / `val.txt` as negatives.
