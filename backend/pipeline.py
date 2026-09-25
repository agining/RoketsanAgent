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

from analysis_builder import (
    build_analysis,
    save_analysis,
)


def run_pipeline():

    print("1/8 Data loading...")

    detections = load_detections()
    image_meta = load_image_meta()
    zones_data = load_zones()
    tracks = load_tracks()
    reports = load_reports()

    print("2/8 Track grouping...")

    grouped_tracks = group_tracks(
        tracks
    )

    print("3/8 Track class indexing...")

    track_classes = build_track_class_index(
        detections=detections,
        image_meta=image_meta,
        grouped_tracks=grouped_tracks,
        bbox_center_func=bbox_center,
        pixel_to_gps_func=pixel_to_gps,
        find_matching_track_func=find_matching_track,
    )

    print("4/8 Report parsing/matching...")

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

    print("5/8 Report validation...")

    base = zones_data["base"]

    validated_reports = validate_reports(
        matched_reports=matched_reports,
        grouped_tracks=grouped_tracks,
        base_lat=base["lat"],
        base_lon=base["lon"],
    )

    print("6/8 Observation feature extraction...")

    vehicle_observations = build_risk_features(
        detections=detections,
        image_meta=image_meta,
        zones_data=zones_data,
        grouped_tracks=grouped_tracks,
        validated_reports=validated_reports,
    )

    print("7/8 Track aggregation...")

    track_data = build_track_features(
        vehicle_observations,
        grouped_tracks=grouped_tracks,
        zones_data=zones_data,
    )

    tracks_for_llm = track_data["tracks"]

    print(
        f"  Observations: {len(vehicle_observations)}"
    )

    print(
        f"  Unique tracks: {len(tracks_for_llm)}"
    )

    print(
        f"  Untracked: "
        f"{len(track_data['untracked_observations'])}"
    )

    print("8/8 LLM risk assessment...")

    risk_results = assess_tracks(
        tracks_for_llm,
        limit=None,
    )

    analysis = build_analysis(
        zones_data=zones_data,
        track_data=track_data,
        risk_results=risk_results,
    )

    save_analysis(
        analysis,
        output_path="analysis.json",
    )

    with open(
        "llm_track_risk_results.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            risk_results,
            f,
            indent=2,
            ensure_ascii=False,
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
    print("Pipeline tamamlandı.")
    print("analysis.json oluşturuldu.")

    print()
    print("OPERATION SUMMARY")
    print("-----------------")

    print(
        json.dumps(
            analysis["operation_summary"],
            indent=2,
            ensure_ascii=False,
        )
    )

    return analysis


if __name__ == "__main__":
    run_pipeline()
