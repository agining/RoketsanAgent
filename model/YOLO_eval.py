import os
import cv2
import glob
import json

from ultralytics import YOLO

# Constants

IMAGE_DIR = "stage2/images"
OUTPUT_JSON = "detections.json"
MODEL_NAME = "yolo26x_custom.pt"
MODEL_OUTPUT_DIR = "YOLO_outputs"

TRACK_CLASSES = [0, 1, 2, 3]
CONFIDENCE = 0.3
IOU = 0.7
FPS = 20

# Visual Details
COLORS = {
    "bus" : (0, 255, 0),
    "car" : (255, 0, 0), 
    "truck": (255, 255, 0), 
    "van": (0, 0, 255) 
}



model = YOLO(MODEL_NAME)

def detect_frame(frame):
    result = model.predict(
        source=frame,
        conf=CONFIDENCE,
        iou=IOU,
        classes=TRACK_CLASSES,
        verbose=False
    )[0]

    boxes = result.boxes

    detected_objects = []

    if boxes is not None and len(boxes) > 0:
        xyxy = boxes.xyxy.cpu().numpy()
        class_ids = boxes.cls.cpu().numpy().astype(int)
        confidences = boxes.conf.cpu().numpy()

        for box, class_id, confidence in zip(
            xyxy,
            class_ids,
            confidences
        ):
            # xyxy = x1, y1, x2, y2
            x1, y1, x2, y2 = map(int, box)

            # Convert to x, y, width, height
            x = x1
            y = y1
            w = x2 - x1
            h = y2 - y1

            class_name = model.names[class_id]

            # Draw bounding box
            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                COLORS[class_name],
                1
            )

            # Detection label
            label = f"{class_name} | {confidence:.2f}"


            detection = {
                "label": class_name,
                "confidence": float(confidence),
                "bbox": [x, y, w, h]
            }

            detected_objects.append(detection)

            # Get text size
            (text_w, text_h), _ = cv2.getTextSize(
                label,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                2
            )

            # Draw semi-transparent black background
            overlay = frame.copy()

            cv2.rectangle(
                overlay,
                (x1, y1 - text_h - 10),
                (x1 + text_w + 5, y1),
                (0, 0, 0),
                -1
            )

            cv2.addWeighted(
                overlay,
                0.5,
                frame,
                0.5,
                0,
                frame
            )

            # Draw label
            cv2.putText(
                frame,
                label,
                (x1, max(y1 - 10, 0)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )

        

    return frame, detected_objects


def main():
    image_paths = sorted(
        glob.glob(os.path.join(IMAGE_DIR, "*.jpg"))
    )

    os.makedirs(MODEL_OUTPUT_DIR, exist_ok=True)

    detection_json = {}

    for _, image_path in enumerate(image_paths):

        image_id = image_path[len(IMAGE_DIR) + 1:-4]

        img = cv2.imread(image_path)

        frame, detected_objects = detect_frame(img)

        detection_json[image_id] = detected_objects

        # Save visualization
        frame = cv2.resize(frame, (1280, 640))

        save_dir = f"{MODEL_OUTPUT_DIR}/{image_id}.jpg"

        print(save_dir)

        cv2.imwrite(save_dir, frame)

    with open(OUTPUT_JSON, 'w') as f:
        json.dump(detection_json, f)

    print(f"json output saved to: {OUTPUT_JSON }")


if __name__ == "__main__":
    main()
