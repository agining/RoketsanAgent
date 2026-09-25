from collections import defaultdict

from geo import haversine_m


def time_to_minutes(time_str):
    """
    '12:05' -> 725
    """
    hour, minute = map(int, time_str.split(":"))
    return hour * 60 + minute


def group_tracks(track_rows):
    """
    tracks.csv satırlarını track_id bazında gruplar.

    {
        "T0001": [
            {"time": "12:00", "lat": ..., "lon": ...},
            ...
        ]
    }
    """

    grouped = defaultdict(list)

    for row in track_rows:
        grouped[row["track_id"]].append({
            "time": row["time"],
            "time_min": time_to_minutes(row["time"]),
            "lat": row["lat"],
            "lon": row["lon"],
        })

    # Her track'i zamana göre sırala
    for track_id in grouped:
        grouped[track_id].sort(
            key=lambda x: x["time_min"]
        )

    return dict(grouped)


def interpolate_track_position(
    points,
    target_time,
):
    """
    Bir track'in target_time anındaki yaklaşık
    konumunu hesaplar.

    Tam zaman varsa direkt kullanır.
    İki nokta arasındaysa lineer interpolation yapar.
    """

    target_min = time_to_minutes(target_time)

    # Track zaman aralığının dışındaysa eşleştirme yapma
    if target_min < points[0]["time_min"]:
        return None

    if target_min > points[-1]["time_min"]:
        return None

    # Tam aynı zaman varsa direkt dön
    for point in points:
        if point["time_min"] == target_min:
            return {
                "lat": point["lat"],
                "lon": point["lon"],
            }

    # Önceki ve sonraki noktayı bul
    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i + 1]

        if (
            p1["time_min"]
            < target_min
            < p2["time_min"]
        ):
            total_delta = (
                p2["time_min"]
                - p1["time_min"]
            )

            target_delta = (
                target_min
                - p1["time_min"]
            )

            ratio = target_delta / total_delta

            lat = (
                p1["lat"]
                + (p2["lat"] - p1["lat"])
                * ratio
            )

            lon = (
                p1["lon"]
                + (p2["lon"] - p1["lon"])
                * ratio
            )

            return {
                "lat": lat,
                "lon": lon,
            }

    return None


def find_matching_track(
    detection_lat,
    detection_lon,
    capture_time,
    grouped_tracks,
    max_distance_m=150.0,
):
    """
    Detection GPS konumunu capture_time anındaki
    track konumlarıyla karşılaştırır.

    En yakın track'i döndürür.

    150 metreden uzaktaysa eşleşme kabul edilmez.
    """

    best_match = None
    best_distance = float("inf")

    for track_id, points in grouped_tracks.items():

        position = interpolate_track_position(
            points,
            capture_time,
        )

        if position is None:
            continue

        distance = haversine_m(
            detection_lat,
            detection_lon,
            position["lat"],
            position["lon"],
        )

        if distance < best_distance:
            best_distance = distance

            best_match = {
                "track_id": track_id,
                "track_lat": position["lat"],
                "track_lon": position["lon"],
                "match_distance_m": distance,
            }

    # Yakında hiçbir track yoksa eşleşme yok
    if (
        best_match is None
        or best_distance > max_distance_m
    ):
        return None

    best_match["track_lat"] = round(
        best_match["track_lat"],
        6,
    )

    best_match["track_lon"] = round(
        best_match["track_lon"],
        6,
    )

    best_match["match_distance_m"] = round(
        best_match["match_distance_m"],
        1,
    )

    return best_match