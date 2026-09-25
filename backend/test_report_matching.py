from data_loader import (
    load_reports,
    load_zones,
    load_tracks,
    load_detections,
    load_image_meta,
)

from reports import parse_reports

from tracking import (
    group_tracks,
    find_matching_track,
)

from geo import (
    bbox_center,
    pixel_to_gps,
)

from report_matching import (
    build_track_class_index,
    match_reports_to_tracks,
)


def main():

    reports = load_reports()
    zones_data = load_zones()
    tracks = load_tracks()

    detections = load_detections()
    image_meta = load_image_meta()

    grouped_tracks = group_tracks(
        tracks
    )

    # Detection'lardan track araç tiplerini öğren
    track_classes = build_track_class_index(
        detections=detections,
        image_meta=image_meta,
        grouped_tracks=grouped_tracks,
        bbox_center_func=bbox_center,
        pixel_to_gps_func=pixel_to_gps,
        find_matching_track_func=find_matching_track,
    )

    print("\nTrack class index:")
    print(track_classes)

    parsed_reports = parse_reports(
        reports,
        zones_data,
    )

    matched_reports = match_reports_to_tracks(
        parsed_reports=parsed_reports,
        grouped_tracks=grouped_tracks,
        track_classes=track_classes,
        max_distance_m=200,
    )

    print()
    print("Rapor - Track eşleşmeleri:")
    print()

    for report in matched_reports[:30]:

        print(
            "--------------------------------"
        )

        print(
            "Time:",
            report["time"]
        )

        print(
            "Text:",
            report["text"]
        )

        print(
            "Report vehicle:",
            report["vehicle_type"]
        )

        print(
            "Matched track:",
            report["matched_track_id"]
        )

        print(
            "Track class:",
            report["matched_track_class"]
        )

        print(
            "Type match:",
            report["vehicle_type_match"]
        )

        print(
            "Distance:",
            report[
                "track_match_distance_m"
            ]
        )


if __name__ == "__main__":
    main()