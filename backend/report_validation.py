from movement import analyze_movement
from tracking import time_to_minutes


def is_stationary_at_report_time(
    movement,
    report_time,
):
    """
    Rapor anında araç gerçekten stationary mi?

    Geçmişte herhangi bir stop olmuş olması yeterli değildir.
    Rapor anında:
    - movement_state STATIONARY olmalı
    veya
    - rapor zamanı aktif bir stop aralığının içinde olmalı.
    """

    if movement["movement_state"] == "STATIONARY":
        return True

    report_min = time_to_minutes(
        report_time
    )

    for stop in movement.get(
        "stops",
        []
    ):
        start_min = time_to_minutes(
            stop["start"]
        )

        end_min = time_to_minutes(
            stop["end"]
        )

        if (
            start_min
            <= report_min
            <= end_min
            and stop["minutes"] >= 10
        ):
            return True

    return False


def validate_report(
    report,
    grouped_tracks,
    base_lat,
    base_lon,
):
    """
    Bir saha raporunu eşleştiği track'in gerçek hareketiyle karşılaştırır.

    Çıktı:
    - SUPPORTED
    - CONTRADICTED
    - PARTIAL
    - UNVERIFIED
    - IRRELEVANT
    """

    track_id = report.get(
        "matched_track_id"
    )

    report_type = report.get(
        "report_type"
    )

    # --------------------------------
    # GENEL / İLGİSİZ RAPOR
    # --------------------------------

    if report_type == "GENERAL":
        return {
            "verdict": "IRRELEVANT",
            "reasons": [
                "Rapor doğrudan doğrulanabilir bir araç gözlemi içermiyor."
            ],
            "supported_checks": 0,
            "contradicted_checks": 0,
            "checks": [],
            "movement": None,
        }

    # --------------------------------
    # ARAÇ RAPORU AMA TRACK YOK
    # --------------------------------

    if (
        report_type
        == "VEHICLE_OBSERVATION"
        and track_id is None
    ):
        return {
            "verdict": "UNVERIFIED",
            "reasons": [
                "Rapora uygun bir track bulunamadı."
            ],
            "supported_checks": 0,
            "contradicted_checks": 0,
            "checks": [],
            "movement": None,
        }

    # --------------------------------
    # FRIENDLY / EXERCISE GİBİ
    # GENEL BAĞLAMSAL RAPORLAR
    # --------------------------------

    if track_id is None:
        return {
            "verdict": "UNVERIFIED",
            "reasons": [
                "Rapor belirli bir track ile doğrulanamıyor."
            ],
            "supported_checks": 0,
            "contradicted_checks": 0,
            "checks": [],
            "movement": None,
        }

    # --------------------------------
    # MOVEMENT ANALYSIS
    # --------------------------------

    movement = analyze_movement(
        track_id=track_id,
        grouped_tracks=grouped_tracks,
        capture_time=report["time"],
        base_lat=base_lat,
        base_lon=base_lon,
    )

    if movement is None:
        return {
            "verdict": "UNVERIFIED",
            "reasons": [
                "Track için yeterli hareket geçmişi bulunamadı."
            ],
            "supported_checks": 0,
            "contradicted_checks": 0,
            "checks": [],
            "movement": None,
        }

    checks = []

    supported = 0
    contradicted = 0

    # --------------------------------
    # VEHICLE TYPE
    # --------------------------------

    if report.get(
        "vehicle_type"
    ) is not None:

        type_match = report.get(
            "vehicle_type_match"
        )

        if type_match is True:
            supported += 1

            checks.append({
                "claim": "vehicle_type",
                "result": "SUPPORTED",
                "value": {
                    "reported":
                        report.get(
                            "vehicle_type"
                        ),
                    "observed":
                        report.get(
                            "matched_track_class"
                        ),
                },
            })

        elif type_match is False:
            contradicted += 1

            checks.append({
                "claim": "vehicle_type",
                "result": "CONTRADICTED",
                "value": {
                    "reported":
                        report.get(
                            "vehicle_type"
                        ),
                    "observed":
                        report.get(
                            "matched_track_class"
                        ),
                },
            })

    # --------------------------------
    # STATIONARY CLAIM
    # --------------------------------

    if report.get(
        "claims_stationary"
    ):

        actually_stationary = (
            is_stationary_at_report_time(
                movement,
                report["time"],
            )
        )

        if actually_stationary:

            supported += 1

            checks.append({
                "claim": "stationary",
                "result": "SUPPORTED",
                "value": {
                    "movement_state":
                        movement[
                            "movement_state"
                        ],
                    "speed_now_mps":
                        movement[
                            "speed_now_mps"
                        ],
                    "stopped_minutes_total":
                        movement[
                            "stopped_minutes_total"
                        ],
                },
            })

        else:

            contradicted += 1

            checks.append({
                "claim": "stationary",
                "result": "CONTRADICTED",
                "value": {
                    "movement_state":
                        movement[
                            "movement_state"
                        ],
                    "speed_now_mps":
                        movement[
                            "speed_now_mps"
                        ],
                    "stopped_minutes_total":
                        movement[
                            "stopped_minutes_total"
                        ],
                },
            })

    # --------------------------------
    # LEAVING CLAIM
    # --------------------------------

    if report.get(
        "claims_leaving"
    ):

        actually_leaving = (
            movement[
                "movement_state"
            ]
            == "LEAVING_BASE"
        )

        if actually_leaving:

            supported += 1

            checks.append({
                "claim": "leaving",
                "result": "SUPPORTED",
                "value": {
                    "movement_state":
                        movement[
                            "movement_state"
                        ],
                    "closing_speed_mps":
                        movement[
                            "closing_speed_mps"
                        ],
                },
            })

        else:

            contradicted += 1

            checks.append({
                "claim": "leaving",
                "result": "CONTRADICTED",
                "value": {
                    "movement_state":
                        movement[
                            "movement_state"
                        ],
                    "closing_speed_mps":
                        movement[
                            "closing_speed_mps"
                        ],
                },
            })

    # --------------------------------
    # APPROACHING CLAIM
    # --------------------------------

    if report.get(
        "claims_approaching"
    ):

        actually_approaching = (
            movement[
                "movement_state"
            ]
            == "APPROACHING_BASE"
        )

        if actually_approaching:

            supported += 1

            checks.append({
                "claim": "approaching",
                "result": "SUPPORTED",
                "value": {
                    "movement_state":
                        movement[
                            "movement_state"
                        ],
                    "closing_speed_mps":
                        movement[
                            "closing_speed_mps"
                        ],
                },
            })

        else:

            contradicted += 1

            checks.append({
                "claim": "approaching",
                "result": "CONTRADICTED",
                "value": {
                    "movement_state":
                        movement[
                            "movement_state"
                        ],
                    "closing_speed_mps":
                        movement[
                            "closing_speed_mps"
                        ],
                },
            })

    # --------------------------------
    # FAST CLAIM
    # --------------------------------

    if report.get(
        "claims_fast"
    ):

        actually_fast = (
            movement[
                "speed_now_mps"
            ]
            >= 2.0
        )

        if actually_fast:

            supported += 1

            checks.append({
                "claim": "fast",
                "result": "SUPPORTED",
                "value": {
                    "speed_now_mps":
                        movement[
                            "speed_now_mps"
                        ]
                },
            })

        else:

            contradicted += 1

            checks.append({
                "claim": "fast",
                "result": "CONTRADICTED",
                "value": {
                    "speed_now_mps":
                        movement[
                            "speed_now_mps"
                        ]
                },
            })

    # --------------------------------
    # MOVING CLAIM
    # --------------------------------

    if (
        report.get(
            "claims_moving"
        )
        and not report.get(
            "claims_leaving"
        )
        and not report.get(
            "claims_approaching"
        )
        and not report.get(
            "claims_fast"
        )
    ):

        actually_moving = (
            movement[
                "moving_now"
            ]
        )

        if actually_moving:

            supported += 1

            checks.append({
                "claim": "moving",
                "result": "SUPPORTED",
                "value": {
                    "speed_now_mps":
                        movement[
                            "speed_now_mps"
                        ]
                },
            })

        else:

            contradicted += 1

            checks.append({
                "claim": "moving",
                "result": "CONTRADICTED",
                "value": {
                    "speed_now_mps":
                        movement[
                            "speed_now_mps"
                        ]
                },
            })

    # --------------------------------
    # VERDICT
    # --------------------------------

    if (
        supported > 0
        and contradicted == 0
    ):
        verdict = "SUPPORTED"

    elif (
        contradicted > 0
        and supported == 0
    ):
        verdict = "CONTRADICTED"

    elif (
        supported > 0
        and contradicted > 0
    ):
        verdict = "PARTIAL"

    else:
        verdict = "UNVERIFIED"

    # --------------------------------
    # HUMAN-READABLE REASONS
    # --------------------------------

    reasons = []

    for check in checks:

        if check["result"] == "SUPPORTED":
            reasons.append(
                f"{check['claim']} iddiası hareket verisiyle uyumlu."
            )

        elif check["result"] == "CONTRADICTED":
            reasons.append(
                f"{check['claim']} iddiası hareket verisiyle çelişiyor."
            )

    return {
        "verdict": verdict,

        "supported_checks":
            supported,

        "contradicted_checks":
            contradicted,

        "checks":
            checks,

        "reasons":
            reasons,

        "movement":
            movement,
    }


def validate_reports(
    matched_reports,
    grouped_tracks,
    base_lat,
    base_lon,
):
    """
    Tüm eşleştirilmiş raporları doğrular.
    """

    results = []

    for report in matched_reports:

        validation = validate_report(
            report=report,
            grouped_tracks=grouped_tracks,
            base_lat=base_lat,
            base_lon=base_lon,
        )

        results.append({
            **report,
            "validation":
                validation,
        })

    return results