import json
import sys

from data_loader import (
    load_detections,
    load_image_meta,
    load_zones,
    load_tracks,
    load_reports,
)

from tracking import (
    group_tracks,
    find_matching_track,
)

from geo import (
    bbox_center,
    pixel_to_gps,
)

from reports import (
    parse_reports,
)

from report_matching import (
    build_track_class_index,
    match_reports_to_tracks,
)

from report_validation import (
    validate_reports,
)

from risk_features import (
    build_risk_features,
)

from track_features import (
    build_track_features,
)


def main():

    output_file = "track_features_output.txt"

    original_stdout = sys.stdout

    with open(
        output_file,
        "w",
        encoding="utf-8",
    ) as f:

        sys.stdout = f

        detections = load_detections()
        image_meta = load_image_meta()
        zones_data = load_zones()
        tracks = load_tracks()
        reports = load_reports()

        grouped_tracks = group_tracks(
            tracks
        )

        track_classes = (
            build_track_class_index(
                detections=detections,
                image_meta=image_meta,
                grouped_tracks=grouped_tracks,
                bbox_center_func=bbox_center,
                pixel_to_gps_func=pixel_to_gps,
                find_matching_track_func=find_matching_track,
            )
        )

        parsed_reports = parse_reports(
            reports,
            zones_data,
        )

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

        base = zones_data[
            "base"
        ]

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

        vehicle_observations = (
            build_risk_features(
                detections=
                    detections,

                image_meta=
                    image_meta,

                zones_data=
                    zones_data,

                grouped_tracks=
                    grouped_tracks,

                validated_reports=
                    validated_reports,
            )
        )

        track_data = build_track_features(
            vehicle_observations,
            grouped_tracks=grouped_tracks,
            zones_data=zones_data,
        )
        with open(
            "track_features_output.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                track_data,
                f,
                indent=2,
                ensure_ascii=False,
            )

        print()
        print(
            "Vehicle observations:",
            len(vehicle_observations)
        )

        print(
            "Unique tracks:",
            len(track_data["tracks"])
        )

        print(
            "Untracked observations:",
            len(
                track_data[
                    "untracked_observations"
                ]
            )
        )

        print()

        for track in track_data[
            "tracks"
        ]:

            print(
                "--------------------------------"
            )

            print(
                json.dumps(
                    track,
                    indent=2,
                    ensure_ascii=False,
                )
            )

        sys.stdout = original_stdout

    print(
        f"Çıktı kaydedildi: {output_file}"
    )


if __name__ == "__main__":
    main()
