from data_loader import (
    load_detections,
    load_image_meta,
    load_zones,
)

from geo import (
    bbox_center,
    pixel_to_gps,
    analyze_position,
)


def main():
    detections = load_detections()
    image_meta = load_image_meta()
    zones_data = load_zones()

    enriched_results = []

    for image_entry in detections:
        image_id = image_entry["image_id"]

        if image_id not in image_meta:
            print(
                f"Metadata bulunamadı: {image_id}"
            )
            continue

        meta = image_meta[image_id]

        for det in image_entry["detections"]:
            bbox = [
                det["x"],
                det["y"],
                det["w"],
                det["h"],
            ]

            cx, cy = bbox_center(
                bbox
            )

            lat, lon = pixel_to_gps(
                cx,
                cy,
                meta,
            )

            position_info = analyze_position(
                lat,
                lon,
                zones_data,
            )

            result = {
                "image_id": image_id,
                "capture_time": meta[
                    "capture_time"
                ],
                "class": det["class"],
                "confidence": det[
                    "confidence"
                ],
                "bbox": bbox,
                "center_pixel": [
                    round(cx, 2),
                    round(cy, 2),
                ],
                "lat": round(
                    lat,
                    6,
                ),
                "lon": round(
                    lon,
                    6,
                ),
                **position_info,
            }

            enriched_results.append(
                result
            )

    print()
    print("İlk sonuçlar:")
    print()

    for item in enriched_results[:10]:
        print(item)
        print()


if __name__ == "__main__":
    main()