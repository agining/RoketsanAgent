from data_loader import (
    load_detections,
    load_image_meta,
    load_tracks,
)

from geo import (
    bbox_center,
    pixel_to_gps,
)

from tracking import (
    group_tracks,
    find_matching_track,
)

from behavior import analyze_behavior


def main():

    detections = load_detections()
    image_meta = load_image_meta()

    track_rows = load_tracks()

    grouped_tracks = group_tracks(
        track_rows
    )

    for image_entry in detections:

        image_id = image_entry["image_id"]

        if image_id not in image_meta:
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

            cx, cy = bbox_center(
                bbox
            )

            lat, lon = pixel_to_gps(
                cx,
                cy,
                meta,
            )

            match = find_matching_track(
                detection_lat=lat,
                detection_lon=lon,
                capture_time=capture_time,
                grouped_tracks=grouped_tracks,
                max_distance_m=150,
            )

            if not match:
                continue

            track_id = match["track_id"]

            behavior = analyze_behavior(
                track_id=track_id,
                grouped_tracks=grouped_tracks,
                capture_time=capture_time,
            )

            if not behavior:
                continue

            print(
                "--------------------------------"
            )

            print(
                image_id,
                det["class"],
                track_id,
            )

            print(
                "Time:",
                capture_time
            )

            print(
                "Behavior:",
                behavior["behavior"]
            )

            print(
                "Path:",
                behavior["path_length_m"],
                "m"
            )

            print(
                "Net displacement:",
                behavior["net_displacement_m"],
                "m"
            )

            print(
                "Efficiency:",
                behavior["path_efficiency"]
            )

            print(
                "Heading change:",
                behavior[
                    "heading_change_total_deg"
                ]
            )

            print(
                "Extent:",
                behavior["extent_m"],
                "m"
            )

            print(
                "Flags:",
                behavior["flags"]
            )


if __name__ == "__main__":
    main()