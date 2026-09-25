import json
from datetime import datetime


def index_risk_results(risk_results):
    """
    LLM risk sonuçlarını track_id -> result
    şeklinde indexler.
    """

    indexed = {}

    for item in risk_results:

        track_id = item.get(
            "track_id"
        )

        if track_id is None:
            continue

        indexed[track_id] = item

    return indexed


def build_track_entities(
    track_features,
    risk_results,
):
    """
    Track feature'ları ile LLM risk sonuçlarını
    tek yapıda birleştirir.
    """

    risk_index = index_risk_results(
        risk_results
    )

    entities = []

    for track in track_features:

        track_id = track.get(
            "track_id"
        )

        risk_item = risk_index.get(
            track_id
        )

        risk = None
        risk_error = None
        risk_model = None

        if risk_item is not None:

            risk_model = risk_item.get(
                "model"
            )

            if "assessment" in risk_item:
                risk = risk_item.get(
                    "assessment"
                )

            elif "error" in risk_item:
                risk_error = risk_item.get(
                    "error"
                )

        entity = {
            "entity_id":
                track_id,

            "track_id":
                track_id,

            "first_seen":
                track.get(
                    "first_seen"
                ),

            "last_seen":
                track.get(
                    "last_seen"
                ),

            "observation_count":
                track.get(
                    "observation_count"
                ),

            "vehicle_class":
                track.get(
                    "vehicle_class"
                ),

            "latest_position":
                track.get(
                    "latest_position"
                ),

            "position_history":
                track.get(
                    "position_history",
                    []
                ),

            "minimum_distance_to_base_m":
                track.get(
                    "minimum_distance_to_base_m"
                ),

            "latest_movement":
                track.get(
                    "latest_movement"
                ),

            "movement_history":
                track.get(
                    "movement_history",
                    []
                ),

            "latest_behavior":
                track.get(
                    "latest_behavior"
                ),

            "behavior_history":
                track.get(
                    "behavior_history",
                    []
                ),

            "behavior_flags":
                track.get(
                    "behavior_flags",
                    []
                ),

            "reports":
                track.get(
                    "reports",
                    []
                ),

            "report_summary":
                track.get(
                    "report_summary",
                    {}
                ),

            "current_evidence_flags":
                track.get(
                    "current_evidence_flags",
                    []
                ),

            "historical_evidence_flags":
                track.get(
                    "historical_evidence_flags",
                    []
                ),

            "risk": {
                "model":
                    risk_model,

                "assessment":
                    risk,

                "error":
                    risk_error,
            },
        }

        entities.append(
            entity
        )

    return entities


def summarize_risk_levels(
    entities,
):
    """
    Risk seviyelerinin adetlerini çıkarır.
    """

    counts = {
        "LOW": 0,
        "MEDIUM": 0,
        "HIGH": 0,
        "CRITICAL": 0,
        "UNKNOWN": 0,
    }

    for entity in entities:

        assessment = (
            entity
            .get("risk", {})
            .get("assessment")
        )

        if not assessment:
            counts["UNKNOWN"] += 1
            continue

        level = assessment.get(
            "risk_level"
        )

        if level in counts:
            counts[level] += 1
        else:
            counts["UNKNOWN"] += 1

    return counts


def summarize_attention_levels(
    entities,
):
    """
    recommended_attention dağılımını çıkarır.
    """

    counts = {
        "ROUTINE": 0,
        "MONITOR": 0,
        "PRIORITY": 0,
        "IMMEDIATE": 0,
        "UNKNOWN": 0,
    }

    for entity in entities:

        assessment = (
            entity
            .get("risk", {})
            .get("assessment")
        )

        if not assessment:
            counts["UNKNOWN"] += 1
            continue

        level = assessment.get(
            "recommended_attention"
        )

        if level in counts:
            counts[level] += 1
        else:
            counts["UNKNOWN"] += 1

    return counts


def get_priority_entities(
    entities,
):
    """
    HIGH / CRITICAL veya PRIORITY / IMMEDIATE
    olan track'leri kısa özet halinde çıkarır.
    """

    result = []

    for entity in entities:

        assessment = (
            entity
            .get("risk", {})
            .get("assessment")
        )

        if not assessment:
            continue

        risk_level = assessment.get(
            "risk_level"
        )

        attention = assessment.get(
            "recommended_attention"
        )

        if (
            risk_level in [
                "HIGH",
                "CRITICAL",
            ]
            or attention in [
                "PRIORITY",
                "IMMEDIATE",
            ]
        ):

            result.append({
                "track_id":
                    entity.get(
                        "track_id"
                    ),

                "risk_level":
                    risk_level,

                "recommended_attention":
                    attention,

                "summary":
                    assessment.get(
                        "summary"
                    ),

                "vehicle_class":
                    (
                        entity
                        .get(
                            "vehicle_class",
                            {}
                        )
                        .get(
                            "canonical"
                        )
                    ),

                "zone":
                    (
                        entity
                        .get(
                            "latest_position",
                            {}
                        )
                        .get(
                            "zone"
                        )
                    ),

                "distance_to_base_m":
                    (
                        entity
                        .get(
                            "latest_position",
                            {}
                        )
                        .get(
                            "distance_to_base_m"
                        )
                    ),
            })

    return result


def build_operation_summary(
    entities,
    untracked_observations,
):
    """
    Final JSON için genel operasyon özeti.
    """

    risk_counts = summarize_risk_levels(
        entities
    )

    attention_counts = (
        summarize_attention_levels(
            entities
        )
    )

    priority_entities = (
        get_priority_entities(
            entities
        )
    )

    tracked_with_report_contradiction = 0
    tracked_with_class_inconsistency = 0
    approaching_now = 0
    leaving_now = 0
    loitering_now = 0
    circling_now = 0

    for entity in entities:

        flags = entity.get(
            "current_evidence_flags",
            []
        )

        movement = entity.get(
            "latest_movement"
        )

        behavior = entity.get(
            "latest_behavior"
        )

        if (
            "REPORT_CONTRADICTION"
            in flags
        ):
            tracked_with_report_contradiction += 1

        if (
            "CLASS_INCONSISTENCY"
            in flags
        ):
            tracked_with_class_inconsistency += 1

        if movement:

            state = movement.get(
                "movement_state"
            )

            if state == "APPROACHING_BASE":
                approaching_now += 1

            elif state == "LEAVING_BASE":
                leaving_now += 1

        if behavior:

            behavior_name = behavior.get(
                "behavior"
            )

            if behavior_name == "LOITERING":
                loitering_now += 1

            elif behavior_name == "CIRCLING":
                circling_now += 1

    return {
        "tracked_entity_count":
            len(entities),

        "untracked_observation_count":
            len(
                untracked_observations
            ),

        "risk_counts":
            risk_counts,

        "attention_counts":
            attention_counts,

        "current_state_counts": {
            "approaching_base":
                approaching_now,

            "leaving_base":
                leaving_now,

            "loitering":
                loitering_now,

            "circling":
                circling_now,

            "report_contradiction":
                tracked_with_report_contradiction,

            "class_inconsistency":
                tracked_with_class_inconsistency,
        },

        "priority_entities":
            priority_entities,
    }


def build_analysis(
    zones_data,
    track_data,
    risk_results,
):
    """
    Final analysis yapısını oluşturur.
    """

    entities = build_track_entities(
        track_features=
            track_data.get(
                "tracks",
                []
            ),

        risk_results=
            risk_results,
    )

    untracked_observations = (
        track_data.get(
            "untracked_observations",
            []
        )
    )

    operation_summary = (
        build_operation_summary(
            entities=
                entities,

            untracked_observations=
                untracked_observations,
        )
    )

    return {
        "generated_at":
            datetime.now().isoformat(
                timespec="seconds"
            ),

        "base":
            zones_data.get(
                "base"
            ),

        "zones":
            zones_data.get(
                "zones",
                []
            ),

        "operation_summary":
            operation_summary,

        "entities":
            entities,

        "untracked_observations":
            untracked_observations,
    }


def save_analysis(
    analysis,
    output_path="analysis.json",
):
    """
    Final analysis JSON'u diske yazar.
    """

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            analysis,
            f,
            indent=2,
            ensure_ascii=False,
        )
