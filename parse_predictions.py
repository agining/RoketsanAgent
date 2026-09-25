import csv
import json
from pathlib import Path

INPUT_FILE = Path("mock_data/mock_predictions.csv")
OUTPUT_FILE = Path("mock_data/detections.json")


def parse_prediction_string(prediction_string: str):
    prediction_string = prediction_string.strip()

    if not prediction_string or prediction_string.lower() == "none":
        return []

    parts = prediction_string.split()

    if len(parts) % 6 != 0:
        raise ValueError(
            f"PredictionString formatı bozuk: {prediction_string}"
        )

    detections = []

    for i in range(0, len(parts), 6):
        label = parts[i]
        confidence = float(parts[i + 1])
        x = float(parts[i + 2])
        y = float(parts[i + 3])
        w = float(parts[i + 4])
        h = float(parts[i + 5])

        detections.append({
            "class": label,
            "confidence": confidence,
            "x": x,
            "y": y,
            "w": w,
            "h": h
        })

    return detections


def main():
    results = []

    with open(INPUT_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            image_id = row["image_id"]
            prediction_string = row["PredictionString"]

            detections = parse_prediction_string(prediction_string)

            results.append({
                "image_id": image_id,
                "detections": detections
            })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(f"Tamamlandı: {OUTPUT_FILE}")
    print(f"Toplam image: {len(results)}")


if __name__ == "__main__":
    main()