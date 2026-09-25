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

from movement import analyze_movement


def main():

    detections = load_detections()
    image_meta = load_image_meta()
    zones_data = load_zones()

    track_rows = load_tracks()

    grouped_tracks = group_tracks(
        track_rows
    )

    base = zones_data["base"]

    base_lat = base["lat"]
    base_lon = base["lon"]

    results = []

    for image_entry in detections:

        image_id = image_entry["image_id"]

        if image_id not in image_meta:
            continue

        meta = image_meta[image_id]

        capture_time = meta[
            "capture_time"
        ]

        for det in image_entry[
            "detections"
        ]:

            bbox = [
                det["x"],
                det["y"],
                det["w"],
                det["h"],
            ]

            # --------------------------------
            # PIXEL -> GPS
            # --------------------------------

            cx, cy = bbox_center(
                bbox
            )

            lat, lon = pixel_to_gps(
                cx,
                cy,
                meta,
            )

            # --------------------------------
            # POSITION
            # --------------------------------

            position_info = (
                analyze_position(
                    lat,
                    lon,
                    zones_data,
                )
            )

            # --------------------------------
            # TRACK MATCH
            # --------------------------------

            track_match = (
                find_matching_track(
                    detection_lat=lat,
                    detection_lon=lon,
                    capture_time=capture_time,
                    grouped_tracks=grouped_tracks,
                    max_distance_m=150,
                )
            )

            track_id = (
                track_match["track_id"]
                if track_match
                else None
            )

            # --------------------------------
            # MOVEMENT ANALYSIS
            # --------------------------------

            movement = None

            if track_id:

                movement = (
                    analyze_movement(
                        track_id=track_id,
                        grouped_tracks=grouped_tracks,
                        capture_time=capture_time,
                        base_lat=base_lat,
                        base_lon=base_lon,
                    )
                )

            # --------------------------------
            # RESULT
            # --------------------------------

            result = {

                "image_id": image_id,

                "capture_time":
                    capture_time,

                "class":
                    det["class"],

                "confidence":
                    det["confidence"],

                "lat":
                    round(lat, 6),

                "lon":
                    round(lon, 6),

                "zone":
                    position_info[
                        "zone"
                    ],

                "distance_to_base_m":
                    position_info[
                        "distance_to_base_m"
                    ],

                "track_id":
                    track_id,

                "track_match_distance_m":
                    (
                        track_match[
                            "match_distance_m"
                        ]
                        if track_match
                        else None
                    ),

                "movement":
                    movement,
            }

            results.append(result)

    print()
    print(
        "İlk hareket analizleri:"
    )
    print()

    for result in results[:15]:

        print(
            "--------------------------------"
        )

        print(
            f"{result['image_id']} "
            f"{result['class']}"
        )

        print(
            "Track:",
            result["track_id"]
        )

        print(
            "Zone:",
            result["zone"]
        )

        print(
            "Base distance:",
            result[
                "distance_to_base_m"
            ]
        )

        if result["movement"]:

            m = result["movement"]

            print(
                "Movement:",
                m["movement_state"]
            )

            print(
                "Speed:",
                m["speed_now_mps"],
                "m/s"
            )

            print(
                "Approach total:",
                m["approach_total_m"],
                "m"
            )

            print(
                "Approach last60:",
                m[
                    "approach_last60_m"
                ],
                "m"
            )

            print(
                "Heading:",
                m["heading_deg"]
            )

            print(
                "Heading offset:",
                m[
                    "heading_offset_deg"
                ]
            )

            print(
                "Closing speed:",
                m[
                    "closing_speed_mps"
                ],
                "m/s"
            )

            print(
                "ETA:",
                m["eta_min"],
                "min"
            )

            print(
                "Stops:",
                m["stops"]
            )

        else:

            print(
                "Movement: TRACK YOK"
            )


if __name__ == "__main__":
    main()