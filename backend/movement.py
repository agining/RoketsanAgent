from geo import haversine_m, bearing_deg
from tracking import time_to_minutes


STOP_SPEED_THRESHOLD_MPS = 0.08
APPROACH_SPEED_THRESHOLD_MPS = 0.08


def angle_difference(a, b):
    return abs((a - b + 180) % 360 - 180)


def get_track_history_until(
    track_points,
    capture_time,
    lookback_minutes=120,
):
    capture_min = time_to_minutes(capture_time)
    start_min = capture_min - lookback_minutes

    return [
        p
        for p in track_points
        if start_min <= p["time_min"] <= capture_min
    ]


def calculate_segment_speed(p1, p2):
    distance_m = haversine_m(
        p1["lat"],
        p1["lon"],
        p2["lat"],
        p2["lon"],
    )

    delta_minutes = (
        p2["time_min"]
        - p1["time_min"]
    )

    if delta_minutes <= 0:
        return 0.0

    return distance_m / (delta_minutes * 60)


def detect_stops(
    history,
    speed_threshold_mps=STOP_SPEED_THRESHOLD_MPS,
):
    if len(history) < 2:
        return []

    stops = []

    stop_start = None
    stop_end = None

    for i in range(1, len(history)):
        p1 = history[i - 1]
        p2 = history[i]

        speed = calculate_segment_speed(
            p1,
            p2,
        )

        if speed <= speed_threshold_mps:

            if stop_start is None:
                stop_start = p1

            stop_end = p2

        else:

            if stop_start is not None:

                minutes = (
                    stop_end["time_min"]
                    - stop_start["time_min"]
                )

                if minutes >= 5:
                    stops.append({
                        "start": stop_start["time"],
                        "end": stop_end["time"],
                        "minutes": minutes,
                        "lat": round(
                            stop_end["lat"],
                            6,
                        ),
                        "lon": round(
                            stop_end["lon"],
                            6,
                        ),
                    })

                stop_start = None
                stop_end = None

    if stop_start is not None:

        minutes = (
            stop_end["time_min"]
            - stop_start["time_min"]
        )

        if minutes >= 5:
            stops.append({
                "start": stop_start["time"],
                "end": stop_end["time"],
                "minutes": minutes,
                "lat": round(
                    stop_end["lat"],
                    6,
                ),
                "lon": round(
                    stop_end["lon"],
                    6,
                ),
            })

    return stops


def analyze_movement(
    track_id,
    grouped_tracks,
    capture_time,
    base_lat,
    base_lon,
):

    if track_id not in grouped_tracks:
        return None

    history = get_track_history_until(
        grouped_tracks[track_id],
        capture_time,
        lookback_minutes=120,
    )

    if len(history) < 2:
        return None

    first = history[0]
    last = history[-1]

    # --------------------------------
    # DISTANCE TO BASE
    # --------------------------------

    base_distances = []

    for point in history:

        distance = haversine_m(
            point["lat"],
            point["lon"],
            base_lat,
            base_lon,
        )

        base_distances.append(distance)

    dist_start = base_distances[0]
    dist_now = base_distances[-1]

    dist_min = min(base_distances)
    dist_max = max(base_distances)

    approach_total = (
        dist_start - dist_now
    )

    # --------------------------------
    # SPEED
    # --------------------------------

    speeds = []

    for i in range(1, len(history)):

        speed = calculate_segment_speed(
            history[i - 1],
            history[i],
        )

        speeds.append(speed)

    speed_now = (
        speeds[-1]
        if speeds
        else 0
    )

    avg_speed = (
        sum(speeds) / len(speeds)
        if speeds
        else 0
    )

    max_speed = (
        max(speeds)
        if speeds
        else 0
    )

    # --------------------------------
    # HEADING
    # --------------------------------

    prev = history[-2]

    heading = bearing_deg(
        prev["lat"],
        prev["lon"],
        last["lat"],
        last["lon"],
    )

    bearing_to_base = bearing_deg(
        last["lat"],
        last["lon"],
        base_lat,
        base_lon,
    )

    heading_offset = angle_difference(
        heading,
        bearing_to_base,
    )

    # --------------------------------
    # LAST 60 MIN
    # --------------------------------

    capture_min = time_to_minutes(
        capture_time
    )

    last60 = [
        p
        for p in history
        if p["time_min"]
        >= capture_min - 60
    ]

    approach_last60 = 0

    if len(last60) >= 2:

        d1 = haversine_m(
            last60[0]["lat"],
            last60[0]["lon"],
            base_lat,
            base_lon,
        )

        d2 = haversine_m(
            last60[-1]["lat"],
            last60[-1]["lon"],
            base_lat,
            base_lon,
        )

        approach_last60 = d1 - d2

    # --------------------------------
    # CLOSING SPEED
    # --------------------------------

    delta_seconds = (
        last["time_min"]
        - prev["time_min"]
    ) * 60

    closing_speed = 0

    if delta_seconds > 0:

        closing_speed = (
            base_distances[-2]
            - base_distances[-1]
        ) / delta_seconds

    # --------------------------------
    # ETA
    # --------------------------------

    eta_min = None

    if closing_speed > APPROACH_SPEED_THRESHOLD_MPS:

        eta_min = (
            dist_now
            / closing_speed
            / 60
        )

    # --------------------------------
    # PATH
    # --------------------------------

    path_length = 0

    for i in range(1, len(history)):

        path_length += haversine_m(
            history[i - 1]["lat"],
            history[i - 1]["lon"],
            history[i]["lat"],
            history[i]["lon"],
        )

    net_displacement = haversine_m(
        first["lat"],
        first["lon"],
        last["lat"],
        last["lon"],
    )

    # --------------------------------
    # STOPS
    # --------------------------------

    stops = detect_stops(
        history
    )

    stopped_minutes_total = sum(
        x["minutes"]
        for x in stops
    )

    moving_now = (
        speed_now
        > STOP_SPEED_THRESHOLD_MPS
    )

    # --------------------------------
    # MOVEMENT STATE
    # --------------------------------

    if (
        speed_now
        <= STOP_SPEED_THRESHOLD_MPS
    ):

        movement_state = "STATIONARY"

    elif (
        closing_speed
        > APPROACH_SPEED_THRESHOLD_MPS
        and heading_offset < 45
    ):

        movement_state = "APPROACHING_BASE"

    elif (
        closing_speed
        < -APPROACH_SPEED_THRESHOLD_MPS
    ):

        movement_state = "LEAVING_BASE"

    else:

        movement_state = "TRANSIT"

    return {
        "track_id": track_id,

        "t_start": first["time"],
        "t_end": last["time"],

        "dist_start_m": round(
            dist_start,
            1,
        ),

        "dist_now_m": round(
            dist_now,
            1,
        ),

        "dist_min_m": round(
            dist_min,
            1,
        ),

        "dist_max_m": round(
            dist_max,
            1,
        ),

        "approach_total_m": round(
            approach_total,
            1,
        ),

        "approach_last60_m": round(
            approach_last60,
            1,
        ),

        "speed_now_mps": round(
            speed_now,
            2,
        ),

        "avg_speed_mps": round(
            avg_speed,
            2,
        ),

        "max_speed_mps": round(
            max_speed,
            2,
        ),

        "closing_speed_mps": round(
            closing_speed,
            2,
        ),

        "heading_deg": round(
            heading,
            1,
        ),

        "bearing_to_base_deg": round(
            bearing_to_base,
            1,
        ),

        "heading_offset_deg": round(
            heading_offset,
            1,
        ),

        "eta_min": (
            round(eta_min, 1)
            if eta_min is not None
            else None
        ),

        "moving_now": moving_now,

        "movement_state":
            movement_state,

        "path_length_m": round(
            path_length,
            1,
        ),

        "net_displacement_m": round(
            net_displacement,
            1,
        ),

        "stops": stops,

        "stopped_minutes_total":
            stopped_minutes_total,
    }