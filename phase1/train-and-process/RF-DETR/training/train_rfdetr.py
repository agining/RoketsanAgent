"""Fine-tune RF-DETR Large (COCO-pretrained) on the Roketsan vehicle dataset.

Usage: python train_rfdetr.py --epochs 30 --resolution 960 --output-dir outputs/rfdetr_large_roketsan_960
       python train_rfdetr.py --epochs 30 --resolution 960 --dataset-dir data/roketsan_full \
           --car-van-penalty 3 --output-dir outputs/rfdetr_large_full_auairval_960
Dataset (data/roketsan/{train,valid}) is the same split and class ids as the DEIMv2 run:
bus=0, car=1, truck=2, van=3. data/roketsan_full = Roketsan train+val for training, AU-AIR subset for validation.
"""
import argparse

from rfdetr import RFDETRLarge

parser = argparse.ArgumentParser()
parser.add_argument("--epochs", type=int, default=20)
parser.add_argument("--batch-size", type=int, default=8)
parser.add_argument("--grad-accum", type=int, default=2)  # effective batch 16, same as DEIMv2
parser.add_argument("--resolution", type=int, default=704)  # must be divisible by 32
parser.add_argument("--dataset-dir", default="data/roketsan")
parser.add_argument("--car-van-penalty", type=float, default=1.0,
                    help="multiply the car->van and van->car classification loss terms by this factor")
parser.add_argument("--init-weights", default=None,
                    help="start from this RF-DETR checkpoint instead of the COCO-pretrained weights")
parser.add_argument("--output-dir", default="outputs/rfdetr_large_roketsan")
args = parser.parse_args()

CAR, VAN = 1, 3
if args.car_van_penalty != 1.0:
    import confusion_criterion

    confusion_criterion.install(pairs=[(CAR, VAN), (VAN, CAR)], penalty=args.car_van_penalty)

model = RFDETRLarge(pretrain_weights=args.init_weights) if args.init_weights else RFDETRLarge()
model.train(
    dataset_dir=args.dataset_dir,
    output_dir=args.output_dir,
    epochs=args.epochs,
    resolution=args.resolution,
    batch_size=args.batch_size,
    grad_accum_steps=args.grad_accum,
    num_workers=16,
    class_names=["bus", "car", "truck", "van"],
    progress_bar="tqdm",
    tensorboard=True,
)
