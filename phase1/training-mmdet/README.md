# RoketsanDetect – code written during development

All files are new code (no edits to MMDetection / detectron2 / Ultralytics
source). Configs are not included. Each file keeps its original name; its
location in the repository is listed below.

Environments: `.venv` = MMDetection 3.3 (project root), `yolo/.venv` =
Ultralytics 8.4 + ensemble-boxes, `ijepa_vitdet/.venv` = detectron2 +
transformers.

## mmdetection_extensions/
Custom MMDetection modules, imported with `custom_imports` /
`PYTHONPATH=.` from `Train/mmdetection-main/projects/roketsan/`.

| File | What it adds |
|---|---|
| `__init__.py` | Registers the modules below |
| `transforms.py` | `DarkenBrightImage` (gamma darkening of images categorized as bright), `RandomBrightnessContrast` |
| `losses.py` | `ClassBalancedQualityFocalLoss` (per-class weights), `ConfusionPenaltyQualityFocalLoss` (class-confusion penalty), `WIoULoss` (Wise-IoU v1/v3 box loss) |
| `necks.py` | `CSPNeXtPAFPNWithP2` (RTMDet neck with an extra stride-4 P2 branch) |
| `hooks.py` | `FreezeModulesHook` (freeze e.g. the backbone for the first N epochs) |

## data_preparation/
| File | Origin | Purpose |
|---|---|---|
| `categorize_brightness.py` | `projects/roketsan/tools/` | Step 1 of bright-image darkening: mean luminance per image, Otsu bright/dark split |
| `class_weights.py` | `projects/roketsan/tools/` | Inverse-sqrt-frequency class weights from COCO object counts |
| `extend_train_split.py` | `projects/roketsan/tools/` | Move a fraction of val into train (train/val_annotations_extended.json) |
| `coco_to_yolo.py` | `yolo/` | COCO json -> Ultralytics dataset (symlinked images, txt labels, data.yaml) |

## model_conversion/
| File | Origin | Purpose |
|---|---|---|
| `add_p2_to_checkpoint.py` | `projects/roketsan/tools/` | Convert a 3-level RTMDet checkpoint for the P2 model (shift head levels, init P2 from stride 8) |
| `convert_ijepa.py` | `ijepa_vitdet/work/` | I-JEPA target encoder -> detectron2 ViT keys |

## vit_backbones/
| File | Origin | Purpose |
|---|---|---|
| `dinov3_backbone.py` | `dinov3_vitdet/work/` | Frozen DINOv3 / DINOv2 ViT as a multi-level detectron2 backbone (layers 6/12/18/24 -> p2..p5) |
| `ijepa_utils.py` | `ijepa_vitdet/work/` | Freeze the ViT inside ViTDet (LazyCall wrapper) |

## inference_and_sahi/
| File | Origin | Purpose |
|---|---|---|
| `predict_csv.py` | `projects/roketsan/tools/` | MMDetection model -> submission CSV (`label score x y w h`) |
| `sahi_eval.py` | `projects/roketsan/tools/` | SAHI sliced inference for MMDetection models (full image + tiles, edge-box dropping, NMS / greedy-NMM merge), COCO evaluation and CSV output |
| `predict_yolo.py` | `yolo/` | Ultralytics YOLO / RT-DETR -> submission CSV |
| `sahi_yolo.py` | `yolo/` | SAHI sliced inference for Ultralytics YOLO / RT-DETR |

## postprocessing_and_ensembling/
All run with `yolo/.venv`; the other scripts import `ensemble_csv.py`.

| File | Purpose |
|---|---|
| `ensemble_csv.py` | Score a CSV with pycocotools; fuse CSVs with WBF / NMS / soft-NMS |
| `ensemble_search.py` | Parallel grid search over ensemble members and fusion settings |
| `postprocess_csv.py` | NMS (per-class or class-agnostic) + confidence cut-off on a CSV |
| `car_van_calibration.py` | Pairwise car/van score calibration, with a tuning search |
| `small_box_filter.py` | Share of tiny detections and mAP with them removed |

## analysis_and_visualization/
| File | Origin | Purpose |
|---|---|---|
| `confusion_penalty.py` | `projects/roketsan/tools/` | Confusion matrix from predictions -> class-confusion penalty matrix |
| `visualize_csv.py` | `projects/roketsan/tools/` | Draw a prediction CSV on its images |
