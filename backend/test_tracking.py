from data_loader import (
    load_detections,
    load_image_meta,
    load_zones,
    load_tracks,
)

from geo import (
    bbox_center,
    pixel_to_gps,
    analyze_position,
)

from tracking import (
    group_tracks,
    find_matching_track,
)


def main():

    detections = load_detections()
    image_meta = load_image_meta()
    zones_data = load_zones()

    track_rows = load_tracks()

    grouped_tracks = group_tracks(
        track_rows
    )

    results = []

    for image_entry in detections:

        image_id = image_entry["image_id"]

        if image_id not in image_meta:
            print(
                f"Metadata bulunamadı: {image_id}"
            )
            continue

        meta = image_meta[image_id]

        capture_time = meta["capture_time"]

        for det in image_entry["detections"]:

            bbox = [
                det["x"],
                det["y"],
                det["w"],
                det["h"],
            ]

            # 1. bbox merkezi
            cx, cy = bbox_center(
                bbox
            )

            # 2. piksel -> GPS
            lat, lon = pixel_to_gps(
                cx,
                cy,
                meta,
            )

            # 3. zone + üs bilgisi
            position_info = analyze_position(
                lat,
                lon,
                zones_data,
            )

            # 4. track eşleştirme
            track_match = find_matching_track(
                detection_lat=lat,
                detection_lon=lon,
                capture_time=capture_time,
                grouped_tracks=grouped_tracks,
                max_distance_m=150.0,
            )

            result = {
                "image_id": image_id,
                "capture_time": capture_time,

                "class": det["class"],
                "confidence": det["confidence"],

                "bbox": bbox,

                "center_pixel": [
                    round(cx, 2),
                    round(cy, 2),
                ],

                "lat": round(lat, 6),
                "lon": round(lon, 6),

                **position_info,

                "track_id": (
                    track_match["track_id"]
                    if track_match
                    else None
                ),

                "track_match_distance_m": (
                    track_match[
                        "match_distance_m"
                    ]
                    if track_match
                    else None
                ),

                "track_lat": (
                    track_match["track_lat"]
                    if track_match
                    else None
                ),

                "track_lon": (
                    track_match["track_lon"]
                    if track_match
                    else None
                ),
            }

            results.append(result)

    print()
    print("İlk track eşleşmeleri:")
    print()

    for item in results[:15]:
        print(item)
        print()


if __name__ == "__main__":
    main()