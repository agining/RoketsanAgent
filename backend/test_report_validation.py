from data_loader import (
    load_reports,
    load_zones,
    load_tracks,
    load_detections,
    load_image_meta,
)

from reports import (
    parse_reports,
)

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

from report_validation import (
    validate_reports,
)


def main():

    # --------------------------------
    # LOAD DATA
    # --------------------------------

    reports = load_reports()
    zones_data = load_zones()
    tracks = load_tracks()
    detections = load_detections()
    image_meta = load_image_meta()

    # --------------------------------
    # GROUP TRACKS
    # --------------------------------

    grouped_tracks = group_tracks(
        tracks
    )

    # --------------------------------
    # LEARN TRACK VEHICLE CLASSES
    # FROM DETECTIONS
    # --------------------------------

    track_classes = build_track_class_index(
        detections=detections,
        image_meta=image_meta,
        grouped_tracks=grouped_tracks,
        bbox_center_func=bbox_center,
        pixel_to_gps_func=pixel_to_gps,
        find_matching_track_func=find_matching_track,
    )

    # --------------------------------
    # PARSE REPORTS
    # --------------------------------

    parsed_reports = parse_reports(
        reports,
        zones_data,
    )

    # --------------------------------
    # MATCH REPORTS -> TRACKS
    # --------------------------------

    matched_reports = (
        match_reports_to_tracks(
            parsed_reports=
                parsed_reports,

            grouped_tracks=
                grouped_tracks,

            track_classes=
                track_classes,

            max_distance_m=200,
        )
    )

    # --------------------------------
    # BASE
    # --------------------------------

    base = zones_data[
        "base"
    ]

    # --------------------------------
    # VALIDATE REPORTS
    # --------------------------------

    validated_reports = (
        validate_reports(
            matched_reports=
                matched_reports,

            grouped_tracks=
                grouped_tracks,

            base_lat=
                base["lat"],

            base_lon=
                base["lon"],
        )
    )

    # --------------------------------
    # PRINT
    # --------------------------------

    print()
    print(
        "Rapor doğrulama sonuçları:"
    )
    print()

    for report in validated_reports[:40]:

        validation = report[
            "validation"
        ]

        print(
            "--------------------------------"
        )

        print(
            "Time:",
            report["time"]
        )

        print(
            "Source:",
            report["source"]
        )

        print(
            "Text:",
            report["text"]
        )

        print(
            "Track:",
            report[
                "matched_track_id"
            ]
        )

        print(
            "Track class:",
            report[
                "matched_track_class"
            ]
        )

        print(
            "Verdict:",
            validation[
                "verdict"
            ]
        )

        print(
            "Supported:",
            validation[
                "supported_checks"
            ]
        )

        print(
            "Contradicted:",
            validation[
                "contradicted_checks"
            ]
        )

        print(
            "Checks:",
            validation[
                "checks"
            ]
        )

        print(
            "Reasons:",
            validation[
                "reasons"
            ]
        )


if __name__ == "__main__":
    main()