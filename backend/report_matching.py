from collections import defaultdict, Counter

from geo import haversine_m
from tracking import (
    interpolate_track_position,
)


def build_track_class_index(
    detections,
    image_meta,
    grouped_tracks,
    bbox_center_func,
    pixel_to_gps_func,
    find_matching_track_func,
    max_distance_m=150.0,
):
    """
    Detection -> track eşleşmelerinden her track için
    gözlenen araç sınıfını çıkarır.

    ground_truth.json kullanılmaz.

    Örnek:
    T0001 -> van
    T0002 -> truck
    """

    observations = defaultdict(list)

    for image_entry in detections:

        image_id = image_entry["image_id"]

        if image_id not in image_meta:
            continue

        meta = image_meta[image_id]
        capture_time = meta["capture_time"]

        for det in image_entry["detections"]:

            bbox = [
                det["x"],
                det["y"],
                det["w"],
                det["h"],
            ]

            cx, cy = bbox_center_func(
                bbox
            )

            lat, lon = pixel_to_gps_func(
                cx,
                cy,
                meta,
            )

            match = find_matching_track_func(
                detection_lat=lat,
                detection_lon=lon,
                capture_time=capture_time,
                grouped_tracks=grouped_tracks,
                max_distance_m=max_distance_m,
            )

            if not match:
                continue

            track_id = match["track_id"]

            observations[
                track_id
            ].append(
                det["class"]
            )

    track_classes = {}

    for track_id, classes in observations.items():

        most_common = Counter(
            classes
        ).most_common(1)

        if not most_common:
            continue

        track_classes[
            track_id
        ] = most_common[0][0]

    return track_classes


def match_report_to_track(
    parsed_report,
    grouped_tracks,
    track_classes=None,
    max_distance_m=200.0,
):
    """
    Bir saha raporunu uygun track ile eşleştirir.

    Kriterler:
    - rapor zamanı
    - rapor koordinatı
    - track koordinatı
    - araç tipi

    Araç tipi raporda biliniyorsa ve çevrede aynı tipte
    uygun bir track yoksa yanlış tipe zorla eşleştirme yapılmaz.
    """

    coord = parsed_report.get(
        "coord"
    )

    # Koordinat yoksa şimdilik track eşleştiremiyoruz
    if coord is None:
        return None

    report_time = parsed_report[
        "time"
    ]

    report_vehicle_type = (
        parsed_report.get(
            "vehicle_type"
        )
    )

    report_lat = coord["lat"]
    report_lon = coord["lon"]

    candidates = []

    # --------------------------------
    # RAPOR SAATİNDEKİ TRACKLER
    # --------------------------------

    for track_id, points in grouped_tracks.items():

        position = interpolate_track_position(
            points,
            report_time,
        )

        if position is None:
            continue

        distance = haversine_m(
            report_lat,
            report_lon,
            position["lat"],
            position["lon"],
        )

        # Çok uzaktaki trackleri aday yapma
        if distance > max_distance_m:
            continue

        observed_class = None

        if track_classes is not None:
            observed_class = (
                track_classes.get(
                    track_id
                )
            )

        # --------------------------------
        # TYPE MATCH
        # --------------------------------

        type_match = None

        if (
            report_vehicle_type
            is not None
            and observed_class
            is not None
        ):
            type_match = (
                report_vehicle_type
                == observed_class
            )

        candidates.append({
            "track_id": track_id,

            "track_lat":
                position["lat"],

            "track_lon":
                position["lon"],

            "distance_m":
                distance,

            "observed_class":
                observed_class,

            "type_match":
                type_match,
        })

    # --------------------------------
    # ADAY YOK
    # --------------------------------

    if not candidates:
        return None

    # --------------------------------
    # ARAÇ TİPİ FİLTRESİ
    # --------------------------------

    if report_vehicle_type is not None:

        same_type_candidates = [
            candidate
            for candidate in candidates
            if candidate[
                "type_match"
            ] is True
        ]

        # Rapor belirli araç tipi söylüyor
        # ancak yakınlarda o tipte track yok.
        #
        # Örneğin:
        # report = van
        # nearby track = car
        #
        # Böyle durumda yanlış eşleşme yapma.
        if not same_type_candidates:
            return None

        candidates = (
            same_type_candidates
        )

    # --------------------------------
    # EN YAKIN UYUMLU TRACK
    # --------------------------------

    best = min(
        candidates,
        key=lambda x: x[
            "distance_m"
        ],
    )

    return {
        "track_id":
            best["track_id"],

        "track_lat": round(
            best["track_lat"],
            6,
        ),

        "track_lon": round(
            best["track_lon"],
            6,
        ),

        "match_distance_m": round(
            best["distance_m"],
            1,
        ),

        "observed_class":
            best["observed_class"],

        "type_match":
            best["type_match"],
    }


def match_reports_to_tracks(
    parsed_reports,
    grouped_tracks,
    track_classes=None,
    max_distance_m=200.0,
):
    """
    Tüm parse edilmiş raporları tracklerle eşleştirir.
    """

    results = []

    for report in parsed_reports:

        match = match_report_to_track(
            parsed_report=report,
            grouped_tracks=grouped_tracks,
            track_classes=track_classes,
            max_distance_m=max_distance_m,
        )

        result = {
            **report,

            "matched_track_id": (
                match["track_id"]
                if match
                else None
            ),

            "track_match_distance_m": (
                match[
                    "match_distance_m"
                ]
                if match
                else None
            ),

            "matched_track_lat": (
                match["track_lat"]
                if match
                else None
            ),

            "matched_track_lon": (
                match["track_lon"]
                if match
                else None
            ),

            "matched_track_class": (
                match[
                    "observed_class"
                ]
                if match
                else None
            ),

            "vehicle_type_match": (
                match[
                    "type_match"
                ]
                if match
                else None
            ),
        }

        results.append(
            result
        )

    return results