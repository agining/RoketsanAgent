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

from llm_risk import (
    assess_vehicles,
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
    # TRACKS
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
    # RISK FEATURES
    # --------------------------------

    vehicles = build_risk_features(
        detections=detections,
        image_meta=image_meta,
        zones_data=zones_data,
        grouped_tracks=grouped_tracks,
        validated_reports=
            validated_reports,
    )

    print()
    print(
        f"Toplam vehicle observation: "
        f"{len(vehicles)}"
    )
    print()

    # İlk testte sadece 3 API çağrısı.
    # Gereksiz kredi harcamayalım.
    assessments = assess_vehicles(
        vehicles,
        limit=3,
    )

    print()
    print(
        "LLM RISK RESULTS"
    )
    print()

    for result in assessments:

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