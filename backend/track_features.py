from collections import defaultdict

from geo import analyze_position


def time_to_minutes(time_str):
    hour, minute = map(
        int,
        time_str.split(":")
    )

    return hour * 60 + minute


def most_common(values):
    if not values:
        return None

    counts = {}

    for value in values:
        counts[value] = (
            counts.get(value, 0) + 1
        )

    return max(
        counts,
        key=counts.get,
    )


def build_track_features(
    vehicle_observations,
    grouped_tracks=None,
    zones_data=None,
):
    """
    Detection bazlı observation'ları
    track bazında birleştirir.
    """

    grouped = defaultdict(list)
    untracked = []

    # --------------------------------
    # GROUP OBSERVATIONS BY TRACK
    # --------------------------------

    for vehicle in vehicle_observations:

        track_id = (
            vehicle
            .get("track", {})
            .get("track_id")
        )

        if track_id is None:
            untracked.append(
                vehicle
            )
            continue

        grouped[track_id].append(
            vehicle
        )

    # --------------------------------
    # BUILD TRACK PACKAGES
    # --------------------------------

    results = []

    for track_id, observations in grouped.items():

        observations = sorted(
            observations,
            key=lambda x: time_to_minutes(
                x["capture_time"]
            ),
        )

        first = observations[0]
        latest = observations[-1]

        # --------------------------------
        # VEHICLE CLASS
        # --------------------------------

        classes = [
            obs["detection"]["class"]
            for obs in observations
        ]

        canonical_class = most_common(
            classes
        )

        class_counts = {}

        for cls in classes:
            class_counts[cls] = (
                class_counts.get(
                    cls,
                    0
                ) + 1
            )

        class_consistent = (
            len(class_counts) == 1
        )

        # --------------------------------
        # DETECTION CONFIDENCE
        # --------------------------------

        confidences = [
            obs["detection"]["confidence"]
            for obs in observations
        ]

        avg_detection_confidence = (
            sum(confidences)
            / len(confidences)
        )

        # --------------------------------
        # DISTANCES
        # --------------------------------

        distances = [
            obs[
                "position"
            ][
                "distance_to_base_m"
            ]
            for obs in observations
        ]

        min_distance_to_base = min(
            distances
        )

        latest_distance_to_base = (
            latest[
                "position"
            ][
                "distance_to_base_m"
            ]
        )

        # --------------------------------
        # POSITION HISTORY
        # --------------------------------

        position_history = []

        if grouped_tracks is not None:

            for point in grouped_tracks.get(
                track_id,
                [],
            ):

                position = {
                    "time":
                        point[
                            "time"
                        ],

                    "lat":
                        point[
                            "lat"
                        ],

                    "lon":
                        point[
                            "lon"
                        ],
                }

                if zones_data is not None:

                    position_analysis = analyze_position(
                        point[
                            "lat"
                        ],
                        point[
                            "lon"
                        ],
                        zones_data,
                    )

                    position.update({
                        "zone":
                            position_analysis[
                                "zone"
                            ],

                        "distance_to_base_m":
                            position_analysis[
                                "distance_to_base_m"
                            ],
                    })

                position_history.append(
                    position
                )

        # --------------------------------
        # MOVEMENT HISTORY
        # --------------------------------

        movement_states = []

        for obs in observations:

            movement = obs.get(
                "movement"
            )

            if movement is None:
                continue

            movement_states.append({
                "time":
                    obs[
                        "capture_time"
                    ],

                "state":
                    movement[
                        "movement_state"
                    ],

                "speed_mps":
                    movement[
                        "speed_now_mps"
                    ],

                "closing_speed_mps":
                    movement[
                        "closing_speed_mps"
                    ],

                "eta_min":
                    movement[
                        "eta_min"
                    ],

                "distance_to_base_m":
                    movement[
                        "dist_now_m"
                    ],
            })

        # --------------------------------
        # BEHAVIOR HISTORY
        # --------------------------------

        behavior_history = []
        behavior_flags = set()

        for obs in observations:

            behavior = obs.get(
                "behavior"
            )

            if behavior is None:
                continue

            behavior_history.append({
                "time":
                    obs[
                        "capture_time"
                    ],

                "behavior":
                    behavior[
                        "behavior"
                    ],

                "path_efficiency":
                    behavior[
                        "path_efficiency"
                    ],

                "heading_change_total_deg":
                    behavior[
                        "heading_change_total_deg"
                    ],

                "flags":
                    behavior[
                        "flags"
                    ],
            })

            for flag in behavior.get(
                "flags",
                [],
            ):
                behavior_flags.add(
                    flag
                )

        # --------------------------------
        # REPORTS
        # --------------------------------

        report_map = {}

        for obs in observations:

            for report in obs.get(
                "reports",
                [],
            ):

                key = (
                    report.get("time"),
                    report.get("source"),
                    report.get("text"),
                )

                report_map[key] = report

        reports = list(
            report_map.values()
        )

        # --------------------------------
        # REPORT SUMMARY
        # --------------------------------

        report_summary = {
            "SUPPORTED": 0,
            "CONTRADICTED": 0,
            "PARTIAL": 0,
            "UNVERIFIED": 0,
            "IRRELEVANT": 0,
        }

        for report in reports:

            verdict = report.get(
                "verdict"
            )

            if verdict in report_summary:
                report_summary[
                    verdict
                ] += 1

        # --------------------------------
        # CURRENT / HISTORICAL EVIDENCE
        # --------------------------------

        current_evidence_flags = set()
        historical_evidence_flags = set()

        # Tüm geçmiş observation flag'leri
        for obs in observations:

            for flag in obs.get(
                "evidence_flags",
                [],
            ):
                historical_evidence_flags.add(
                    flag
                )

        # Sadece en son observation'ın
        # güncel flag'leri
        for flag in latest.get(
            "evidence_flags",
            [],
        ):
            current_evidence_flags.add(
                flag
            )

        # Track genelinde sınıf tutarsızlığı
        if not class_consistent:

            current_evidence_flags.add(
                "CLASS_INCONSISTENCY"
            )

            historical_evidence_flags.add(
                "CLASS_INCONSISTENCY"
            )

        # --------------------------------
        # LATEST STATE
        # --------------------------------

        latest_movement = latest.get(
            "movement"
        )

        latest_behavior = latest.get(
            "behavior"
        )

        # --------------------------------
        # FINAL TRACK PACKAGE
        # --------------------------------

        result = {
            "track_id":
                track_id,

            "first_seen":
                first[
                    "capture_time"
                ],

            "last_seen":
                latest[
                    "capture_time"
                ],

            "observation_count":
                len(
                    observations
                ),

            "vehicle_class": {
                "canonical":
                    canonical_class,

                "observed_classes":
                    class_counts,

                "consistent":
                    class_consistent,

                "average_detection_confidence":
                    round(
                        avg_detection_confidence,
                        3,
                    ),
            },

            "latest_position": {
                "lat":
                    latest[
                        "position"
                    ]["lat"],

                "lon":
                    latest[
                        "position"
                    ]["lon"],

                "zone":
                    latest[
                        "position"
                    ]["zone"],

                "distance_to_base_m":
                    latest_distance_to_base,
            },

            "position_history":
                position_history,

            "minimum_distance_to_base_m":
                min_distance_to_base,

            "latest_movement":
                latest_movement,

            "movement_history":
                movement_states,

            "latest_behavior":
                latest_behavior,

            "behavior_history":
                behavior_history,

            "behavior_flags":
                sorted(
                    behavior_flags
                ),

            "reports":
                reports,

            "report_summary":
                report_summary,

            "current_evidence_flags":
                sorted(
                    current_evidence_flags
                ),

            "historical_evidence_flags":
                sorted(
                    historical_evidence_flags
                ),
        }

        # ÇOK ÖNEMLİ:
        # Bu satır for track_id döngüsünün içinde olmalı.
        results.append(
            result
        )

    # --------------------------------
    # SORT
    # --------------------------------

    results.sort(
        key=lambda x: x[
            "track_id"
        ]
    )

    return {
        "tracks":
            results,

        "untracked_observations":
            untracked,
    }
