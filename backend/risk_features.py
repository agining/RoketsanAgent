from collections import defaultdict

from geo import (
    bbox_center,
    pixel_to_gps,
    analyze_position,
)

from tracking import (
    find_matching_track,
)

from movement import (
    analyze_movement,
)

from behavior import (
    analyze_behavior,
)


def index_reports_by_track(validated_reports):
    """
    Doğrulanmış raporları matched_track_id bazında indexler.
    """

    result = defaultdict(list)

    for report in validated_reports:
        track_id = report.get(
            "matched_track_id"
        )

        if track_id is None:
            continue

        result[track_id].append(
            report
        )

    return dict(result)


def compact_report(report):
    """
    LLM'e ve risk katmanına gereksiz büyük veri
    göndermemek için raporu sadeleştirir.
    """

    validation = report.get(
        "validation",
        {},
    )

    return {
        "time": report.get("time"),
        "source": report.get("source"),
        "text": report.get("text"),

        "report_type":
            report.get("report_type"),

        "vehicle_type":
            report.get("vehicle_type"),

        "matched_track_id":
            report.get(
                "matched_track_id"
            ),

        "match_distance_m":
            report.get(
                "track_match_distance_m"
            ),

        "verdict":
            validation.get(
                "verdict"
            ),

        "supported_checks":
            validation.get(
                "supported_checks",
                0,
            ),

        "contradicted_checks":
            validation.get(
                "contradicted_checks",
                0,
            ),

        "checks":
            validation.get(
                "checks",
                [],
            ),

        "reasons":
            validation.get(
                "reasons",
                [],
            ),
    }


def build_risk_features(
    detections,
    image_meta,
    zones_data,
    grouped_tracks,
    validated_reports,
):
    """
    Tüm detection'ları tek bir risk feature paketine dönüştürür.

    Çıktı her araç için:
    - detection
    - GPS
    - zone
    - base distance
    - track match
    - movement
    - behavior
    - related reports
    """

    reports_by_track = (
        index_reports_by_track(
            validated_reports
        )
    )

    base = zones_data["base"]

    base_lat = base["lat"]
    base_lon = base["lon"]

    results = []

    for image_entry in detections:

        image_id = image_entry[
            "image_id"
        ]

        if image_id not in image_meta:
            continue

        meta = image_meta[
            image_id
        ]

        capture_time = meta[
            "capture_time"
        ]

        for detection_index, det in enumerate(
            image_entry["detections"]
        ):

            bbox = [
                det["x"],
                det["y"],
                det["w"],
                det["h"],
            ]

            # -------------------------
            # PIXEL -> GPS
            # -------------------------

            cx, cy = bbox_center(
                bbox
            )

            lat, lon = pixel_to_gps(
                cx,
                cy,
                meta,
            )

            # -------------------------
            # POSITION
            # -------------------------

            position = analyze_position(
                lat,
                lon,
                zones_data,
            )

            # -------------------------
            # TRACK MATCH
            # -------------------------

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

            # -------------------------
            # MOVEMENT
            # -------------------------

            movement = None

            if track_id is not None:
                movement = analyze_movement(
                    track_id=track_id,
                    grouped_tracks=grouped_tracks,
                    capture_time=capture_time,
                    base_lat=base_lat,
                    base_lon=base_lon,
                )

            # -------------------------
            # BEHAVIOR
            # -------------------------

            behavior = None

            if track_id is not None:
                behavior = analyze_behavior(
                    track_id=track_id,
                    grouped_tracks=grouped_tracks,
                    capture_time=capture_time,
                )

            # -------------------------
            # RELATED REPORTS
            # -------------------------

            related_reports = []

            if track_id is not None:

                all_track_reports = (
                    reports_by_track.get(
                        track_id,
                        [],
                    )
                )

                # Gelecekteki raporu kullanma
                current_minutes = (
                    int(
                        capture_time.split(":")[0]
                    ) * 60
                    + int(
                        capture_time.split(":")[1]
                    )
                )

                for report in all_track_reports:

                    report_time = report[
                        "time"
                    ]

                    report_minutes = (
                        int(
                            report_time.split(":")[0]
                        ) * 60
                        + int(
                            report_time.split(":")[1]
                        )
                    )

                    if (
                        report_minutes
                        <= current_minutes
                    ):
                        related_reports.append(
                            compact_report(
                                report
                            )
                        )

            # -------------------------
            # REPORT SUMMARY
            # -------------------------

            report_verdict_counts = {
                "SUPPORTED": 0,
                "CONTRADICTED": 0,
                "PARTIAL": 0,
                "UNVERIFIED": 0,
                "IRRELEVANT": 0,
            }

            for report in related_reports:

                verdict = report.get(
                    "verdict"
                )

                if (
                    verdict
                    in report_verdict_counts
                ):
                    report_verdict_counts[
                        verdict
                    ] += 1

            # -------------------------
            # SIMPLE EVIDENCE FLAGS
            # -------------------------

            evidence_flags = []

            if track_id is None:
                evidence_flags.append(
                    "UNTRACKED"
                )

            if (
                movement
                and movement["movement_state"]
                == "APPROACHING_BASE"
            ):
                evidence_flags.append(
                    "APPROACHING_BASE"
                )

            if (
                movement
                and movement["eta_min"] is not None
            ):
                evidence_flags.append(
                    "ETA_AVAILABLE"
                )

            if (
                behavior
                and behavior["behavior"]
                == "LOITERING"
            ):
                evidence_flags.append(
                    "LOITERING"
                )

            if (
                behavior
                and behavior["behavior"]
                == "CIRCLING"
            ):
                evidence_flags.append(
                    "CIRCLING"
                )

            partial_with_contradiction = any(
                report.get("verdict") == "PARTIAL"
                and report.get(
                    "contradicted_checks",
                    0
                ) > 0
                for report in related_reports
            )

            if (
                report_verdict_counts[
                    "CONTRADICTED"
                ] > 0
                or partial_with_contradiction
            ):
                evidence_flags.append(
                    "REPORT_CONTRADICTION"
                )

            if (
                report_verdict_counts[
                    "SUPPORTED"
                ] > 0
            ):
                evidence_flags.append(
                    "REPORT_SUPPORTED"
                )

            # -------------------------
            # FINAL PACKAGE
            # -------------------------

            vehicle_id = (
                f"{image_id}_v"
                f"{detection_index}"
            )

            result = {
                "vehicle_id":
                    vehicle_id,

                "image_id":
                    image_id,

                "capture_time":
                    capture_time,

                "detection": {
                    "class":
                        det["class"],

                    "confidence":
                        det["confidence"],

                    "bbox":
                        bbox,

                    "center_pixel": [
                        round(cx, 2),
                        round(cy, 2),
                    ],
                },

                "position": {
                    "lat":
                        round(lat, 6),

                    "lon":
                        round(lon, 6),

                    "zone":
                        position["zone"],

                    "zone_center_distance_m":
                        position[
                            "zone_center_distance_m"
                        ],

                    "distance_to_base_m":
                        position[
                            "distance_to_base_m"
                        ],

                    "bearing_to_base_deg":
                        position[
                            "bearing_to_base_deg"
                        ],

                    "bearing_from_base_deg":
                        position[
                            "bearing_from_base_deg"
                        ],
                },

                "track": {
                    "track_id":
                        track_id,

                    "match_distance_m":
                        (
                            track_match[
                                "match_distance_m"
                            ]
                            if track_match
                            else None
                        ),
                },

                "movement":
                    movement,

                "behavior":
                    behavior,

                "reports":
                    related_reports,

                "report_summary":
                    report_verdict_counts,

                "evidence_flags":
                    evidence_flags,
            }

            results.append(
                result
            )

    return results