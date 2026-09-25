from geo import haversine_m, bearing_deg
from movement import get_track_history_until


def angle_difference(a, b):
    return abs((a - b + 180) % 360 - 180)


def analyze_behavior(
    track_id,
    grouped_tracks,
    capture_time,
):
    if track_id not in grouped_tracks:
        return None

    history = get_track_history_until(
        grouped_tracks[track_id],
        capture_time,
        lookback_minutes=120,
    )

    if len(history) < 3:
        return None

    # -------------------------
    # PATH LENGTH
    # -------------------------

    path_length = 0.0

    for i in range(1, len(history)):
        path_length += haversine_m(
            history[i - 1]["lat"],
            history[i - 1]["lon"],
            history[i]["lat"],
            history[i]["lon"],
        )

    # -------------------------
    # NET DISPLACEMENT
    # -------------------------

    first = history[0]
    last = history[-1]

    net_displacement = haversine_m(
        first["lat"],
        first["lon"],
        last["lat"],
        last["lon"],
    )

    # 1'e yakınsa düz hareket
    # 0'a yakınsa çok dolaşmış
    path_efficiency = (
        net_displacement / path_length
        if path_length > 0
        else 1.0
    )

    # -------------------------
    # HEADING CHANGES
    # -------------------------

    headings = []

    for i in range(1, len(history)):
        heading = bearing_deg(
            history[i - 1]["lat"],
            history[i - 1]["lon"],
            history[i]["lat"],
            history[i]["lon"],
        )

        headings.append(heading)

    heading_change_total = 0.0

    for i in range(1, len(headings)):
        heading_change_total += angle_difference(
            headings[i - 1],
            headings[i],
        )

    # -------------------------
    # AREA / EXTENT
    # -------------------------

    max_extent = 0.0

    for i in range(len(history)):
        for j in range(i + 1, len(history)):
            d = haversine_m(
                history[i]["lat"],
                history[i]["lon"],
                history[j]["lat"],
                history[j]["lon"],
            )

            if d > max_extent:
                max_extent = d

    # -------------------------
    # BEHAVIOR FLAGS
    # -------------------------

    flags = []

    # Çok yol yapmış ama başlangıçtan fazla uzaklaşmamış
    if (
        path_length >= 300
        and path_efficiency < 0.55
    ):
        flags.append("LOW_PATH_EFFICIENCY")

    # Sürekli yön değiştiriyor
    if heading_change_total >= 120:
        flags.append("HIGH_HEADING_CHANGE")

    # Sınırlı bir bölgede dönüp dolaşma
    if (
        path_length >= 300
        and path_efficiency < 0.55
        and heading_change_total >= 120
    ):
        flags.append("POSSIBLE_LOITERING")

    # Daha güçlü circling sinyali
    if (
        path_length >= 500
        and path_efficiency < 0.40
        and heading_change_total >= 180
    ):
        flags.append("POSSIBLE_CIRCLING")

    # -------------------------
    # SIMPLE BEHAVIOR LABEL
    # -------------------------

    if "POSSIBLE_CIRCLING" in flags:
        behavior = "CIRCLING"

    elif "POSSIBLE_LOITERING" in flags:
        behavior = "LOITERING"

    else:
        behavior = "NORMAL_PATH"

    return {
        "track_id": track_id,
        "behavior": behavior,

        "path_length_m": round(
            path_length,
            1,
        ),

        "net_displacement_m": round(
            net_displacement,
            1,
        ),

        "path_efficiency": round(
            path_efficiency,
            3,
        ),

        "heading_change_total_deg": round(
            heading_change_total,
            1,
        ),

        "extent_m": round(
            max_extent,
            1,
        ),

        "flags": flags,
    }