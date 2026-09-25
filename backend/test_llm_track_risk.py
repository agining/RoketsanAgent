import json

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

from llm_risk import (
    assess_tracks,
)


def main():

    # --------------------------------
    # LOAD
    # --------------------------------

    detections = load_detections()
    image_meta = load_image_meta()
    zones_data = load_zones()
    tracks = load_tracks()
    reports = load_reports()

    # --------------------------------
    # TRACK DATA
    # --------------------------------

    grouped_tracks = group_tracks(
        tracks
    )

    # --------------------------------
    # TRACK CLASS INDEX
    # --------------------------------

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

    # --------------------------------
    # REPORT PIPELINE
    # --------------------------------

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

    # --------------------------------
    # DETECTION FEATURES
    # --------------------------------

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

    # --------------------------------
    # TRACK AGGREGATION
    # --------------------------------

    track_data = build_track_features(
        vehicle_observations,
        grouped_tracks=grouped_tracks,
        zones_data=zones_data,
    )

    tracks_for_llm = track_data[
        "tracks"
    ]

    # --------------------------------
    # INFO
    # --------------------------------

    print()
    print(
        "Vehicle observations:",
        len(vehicle_observations)
    )

    print(
        "Unique tracks:",
        len(tracks_for_llm)
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

    # --------------------------------
    # LLM
    # --------------------------------
    #
    # İlk testte sadece 4 track gönderiyoruz.
    # T0001, T0002, T0003, T0004
    #

    results = assess_tracks(
        tracks_for_llm,
        limit=None,
    )

    with open(
        "llm_track_risk_results.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            results,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(
        "llm_track_risk_results.json oluşturuldu."
    )
    print()
    print(
        "TRACK LLM RISK RESULTS"
    )
    print()

    for result in results:

        print(
            "--------------------------------"
        )

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
