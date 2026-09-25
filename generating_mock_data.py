from __future__ import annotations

import csv
import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

SEED = 42
random.seed(SEED)

OUT_DIR = Path(__file__).resolve().parent / "mock_data"
OUT_DIR.mkdir(exist_ok=True)

BASE = {
    "name": "Merkez Us",
    "lat": 39.92184,
    "lon": 32.85306
}

ZONES = [
    {"name": "Kuzey Yolu",             "center": [39.950586, 32.853060]},
    {"name": "Kuzeydogu Kavsagi",      "center": [39.944000, 32.878000]},
    {"name": "Dogu Yolu",              "center": [39.921840, 32.890542]},
    {"name": "Guneydogu Yerlesimi",    "center": [39.902000, 32.877000]},
    {"name": "Guney Kapisi Yaklasimi", "center": [39.897000, 32.853060]},
    {"name": "Guneybati Yolu",         "center": [39.903000, 32.831000]},
    {"name": "Bati Yerlesimi",         "center": [39.921840, 32.817000]},
    {"name": "Kuzeybati Yolu",         "center": [39.944000, 32.829000]},
]

VEHICLE_CLASSES = ["car", "van", "truck", "bus"]

SCENARIOS = [
    "approaching_base",
    "leaving_base",
    "stationary_then_move",
    "circling",
    "normal_crossing",
    "patrol",
]

# Track: 12:00 -> 14:00
START_TIME = datetime(2026, 9, 26, 12, 0)

# 12:00 dahil 14:00 dahil = 25 nokta
N_STEPS = 25
STEP_MIN = 5

IMAGE_WIDTH = 960
IMAGE_HEIGHT = 540

# Detection modeli kusursuz olmasin diye mock hata oranlari
MISS_RATE = 0.05
MISCLASS_RATE = 0.07
FALSE_POSITIVE_RATE = 0.08

PIXEL_JITTER_STD = 4.0


# ============================================================
# HELPERS
# ============================================================

def tstr(dt):
    return dt.strftime("%H:%M")


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_point(a, b, t):
    return (
        lerp(a[0], b[0], t),
        lerp(a[1], b[1], t)
    )


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)

    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1)
        * math.cos(p2)
        * math.sin(dl / 2) ** 2
    )

    return 2 * r * math.asin(math.sqrt(a))


def offset_point(lat, lon, north_km=0, east_km=0):
    """
    Verilen GPS noktasini yaklasik olarak
    north/east kadar kaydirir.
    """

    dlat = north_km / 111.0

    dlon = east_km / (
        111.0 * math.cos(math.radians(lat))
    )

    return lat + dlat, lon + dlon


def jitter_geo(lat, lon, meters=20):
    """
    Noktaya bir miktar GPS gurultusu ekler.
    """

    angle = random.random() * 2 * math.pi
    radius_km = random.uniform(0, meters / 1000)

    north = radius_km * math.cos(angle)
    east = radius_km * math.sin(angle)

    return offset_point(
        lat,
        lon,
        north_km=north,
        east_km=east
    )


# ============================================================
# TRACK GENERATION
# ============================================================

def generate_track(zone_center, scenario, phase=0):
    zone = tuple(zone_center)

    base = (
        BASE["lat"],
        BASE["lon"]
    )

    # ayni bolgedeki iki arac birebir ust uste binmesin
    zone = offset_point(
        zone[0],
        zone[1],
        north_km=0.10 * math.sin(phase),
        east_km=0.10 * math.cos(phase)
    )

    points = []

    # --------------------------------------------------------
    # 1) USSE YAKLASAN
    # --------------------------------------------------------

    if scenario == "approaching_base":

        # tamamen usse girmesin
        end = lerp_point(zone, base, 0.72)

        for i in range(N_STEPS):

            t = i / (N_STEPS - 1)

            lat, lon = lerp_point(
                zone,
                end,
                t
            )

            # rotayi hafif dogal yap
            lat, lon = offset_point(
                lat,
                lon,
                north_km=
                0.03 * math.sin(
                    t * 3 * math.pi + phase
                )
            )

            points.append((lat, lon))

    # --------------------------------------------------------
    # 2) USTEN UZAKLASAN
    # --------------------------------------------------------

    elif scenario == "leaving_base":

        start = lerp_point(
            base,
            zone,
            0.20
        )

        for i in range(N_STEPS):

            t = i / (N_STEPS - 1)

            points.append(
                lerp_point(
                    start,
                    zone,
                    t
                )
            )

    # --------------------------------------------------------
    # 3) 45 DK BEKLE -> HAREKET ET
    # --------------------------------------------------------

    elif scenario == "stationary_then_move":

        hold_until = 9

        start = offset_point(
            zone[0],
            zone[1],
            north_km=0.08,
            east_km=-0.05
        )

        end = lerp_point(
            zone,
            base,
            0.58
        )

        for i in range(N_STEPS):

            if i <= hold_until:

                lat, lon = jitter_geo(
                    start[0],
                    start[1],
                    meters=8
                )

            else:

                t = (
                    (i - hold_until)
                    /
                    (N_STEPS - 1 - hold_until)
                )

                lat, lon = lerp_point(
                    start,
                    end,
                    t
                )

            points.append((lat, lon))

    # --------------------------------------------------------
    # 4) BOLGEDE DONEN / DOLASAN
    # --------------------------------------------------------

    elif scenario == "circling":

        for i in range(N_STEPS):

            angle = (
                phase
                + 2 * math.pi
                * (i / (N_STEPS - 1))
                * 0.85
            )

            north = 0.22 * math.sin(angle)
            east = 0.22 * math.cos(angle)

            points.append(
                offset_point(
                    zone[0],
                    zone[1],
                    north_km=north,
                    east_km=east
                )
            )

    # --------------------------------------------------------
    # 5) NORMAL YOLDAN GECEN
    # --------------------------------------------------------

    elif scenario == "normal_crossing":

        bvec_lat = zone[0] - base[0]
        bvec_lon = zone[1] - base[1]

        norm = math.hypot(
            bvec_lat,
            bvec_lon
        )

        if norm == 0:
            norm = 1

        # radial hatta dik yon
        p_lat = -bvec_lon / norm
        p_lon = bvec_lat / norm

        start = (
            zone[0] - p_lat * 0.007,
            zone[1] - p_lon * 0.007
        )

        end = (
            zone[0] + p_lat * 0.007,
            zone[1] + p_lon * 0.007
        )

        for i in range(N_STEPS):

            points.append(
                lerp_point(
                    start,
                    end,
                    i / (N_STEPS - 1)
                )
            )

    # --------------------------------------------------------
    # 6) DEVRİYE / ZIGZAG
    # --------------------------------------------------------

    elif scenario == "patrol":

        for i in range(N_STEPS):

            t = i / (N_STEPS - 1)

            north = (
                0.18
                * math.sin(
                    t * 4 * math.pi + phase
                )
            )

            east = (
                0.28
                * math.sin(
                    t * 2 * math.pi + phase
                )
            )

            drift = lerp_point(
                zone,
                base,
                0.10 * t
            )

            points.append(
                offset_point(
                    drift[0],
                    drift[1],
                    north_km=north,
                    east_km=east
                )
            )

    return points


# ============================================================
# MOTION ANALYSIS
# ============================================================

def classify_motion(track_points, idx):

    prev_i = max(
        0,
        idx - 1
    )

    next_i = min(
        len(track_points) - 1,
        idx + 1
    )

    p0 = track_points[prev_i]
    p2 = track_points[next_i]

    dist_before = haversine_km(
        p0[0],
        p0[1],
        BASE["lat"],
        BASE["lon"]
    )

    dist_after = haversine_km(
        p2[0],
        p2[1],
        BASE["lat"],
        BASE["lon"]
    )

    local_distance = haversine_km(
        p0[0],
        p0[1],
        p2[0],
        p2[1]
    )

    minutes = max(
        5,
        (next_i - prev_i) * STEP_MIN
    )

    speed = (
        local_distance
        /
        (minutes / 60)
    )

    if speed < 2:
        return "stationary", speed

    if dist_after < dist_before - 0.04:
        return "approaching_base", speed

    if dist_after > dist_before + 0.04:
        return "leaving_base", speed

    return "moving_in_area", speed


def motion_text(motion):

    mapping = {
        "stationary":
            "uzun suredir bekliyor",

        "approaching_base":
            "usse dogru ilerliyor",

        "leaving_base":
            "usten uzaklasiyor",

        "moving_in_area":
            "bolgede hareket ediyor"
    }

    return mapping[motion]


def wrong_motion_text(motion):

    if motion == "approaching_base":
        return "usten uzaklasiyor"

    if motion == "leaving_base":
        return "usse dogru ilerliyor"

    if motion == "stationary":
        return "bolgeden hizla uzaklasiyor"

    return "uzun suredir hareketsiz bekliyor"


# ============================================================
# IMAGE GEOMETRY
# ============================================================

def point_to_pixel(lat, lon, corners):

    top_lat = corners["top_left"][0]
    bottom_lat = corners["bottom_left"][0]

    left_lon = corners["top_left"][1]
    right_lon = corners["top_right"][1]

    u = (
        (lon - left_lon)
        /
        (right_lon - left_lon)
    )

    v = (
        (top_lat - lat)
        /
        (top_lat - bottom_lat)
    )

    x = u * IMAGE_WIDTH
    y = v * IMAGE_HEIGHT

    return x, y


def in_footprint(lat, lon, corners):

    top = corners["top_left"][0]
    bottom = corners["bottom_left"][0]

    left = corners["top_left"][1]
    right = corners["top_right"][1]

    return (
        bottom <= lat <= top
        and
        left <= lon <= right
    )


# ============================================================
# 1. ZONES.JSON
# ============================================================

zones_payload = {
    "base": BASE,
    "zones": ZONES
}

with open(
    OUT_DIR / "zones.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        zones_payload,
        f,
        ensure_ascii=False,
        indent=2
    )


# ============================================================
# 2. TRACKS
# ============================================================

tracks = {}
track_meta = {}

track_id_num = 1

for zone_index, zone in enumerate(ZONES):

    # Her zone icin 2 arac
    for local_index in range(2):

        track_id = (
            f"T{track_id_num:04d}"
        )

        vehicle_class = VEHICLE_CLASSES[
            (track_id_num + zone_index)
            %
            len(VEHICLE_CLASSES)
        ]

        scenario = SCENARIOS[
            (
                zone_index * 2
                + local_index
            )
            %
            len(SCENARIOS)
        ]

        points = generate_track(
            zone["center"],
            scenario,
            phase=
            0.7 * local_index
            + zone_index * 0.25
        )

        tracks[track_id] = points

        track_meta[track_id] = {
            "vehicle_class":
                vehicle_class,

            "zone":
                zone["name"],

            "scenario":
                scenario
        }

        track_id_num += 1


track_times = [
    START_TIME
    + timedelta(
        minutes=STEP_MIN * i
    )
    for i in range(N_STEPS)
]


# ============================================================
# tracks.csv
# ============================================================

with open(
    OUT_DIR / "tracks.csv",
    "w",
    encoding="utf-8",
    newline=""
) as f:

    writer = csv.writer(f)

    writer.writerow([
        "track_id",
        "time",
        "lat",
        "lon"
    ])

    for track_id, points in tracks.items():

        for dt, (lat, lon) in zip(
            track_times,
            points
        ):

            writer.writerow([
                track_id,
                tstr(dt),
                f"{lat:.6f}",
                f"{lon:.6f}"
            ])


# ============================================================
# 3. IMAGE_META.JSON
#
# 8 zone x 5 image = 40 image
# ============================================================

image_meta = {}
image_truth = {}

image_counter = 860

# 12:05
# 12:30
# 13:00
# 13:30
# 14:00

time_indices = [
    1,
    6,
    12,
    18,
    24
]


zone_to_tracks = {}

for track_id, meta in track_meta.items():

    zone_to_tracks.setdefault(
        meta["zone"],
        []
    ).append(track_id)


for zone in ZONES:

    zone_tracks = zone_to_tracks[
        zone["name"]
    ]

    for j, idx in enumerate(
        time_indices
    ):

        image_id = (
            f"img_{image_counter:06d}"
        )

        image_counter += 1

        primary_track = (
            zone_tracks[
                j % len(zone_tracks)
            ]
        )

        primary_lat, primary_lon = (
            tracks[primary_track][idx]
        )

        # Drone merkezi aracin tam uzerinde olmasin
        camera_lat, camera_lon = (
            jitter_geo(
                primary_lat,
                primary_lon,
                meters=90
            )
        )

        # Yaklasik 600-800 m goruntu alani
        half_lat = random.uniform(
            0.0026,
            0.0032
        )

        half_lon = random.uniform(
            0.0035,
            0.0043
        )

        corners = {

            "top_left": [
                camera_lat + half_lat,
                camera_lon - half_lon
            ],

            "top_right": [
                camera_lat + half_lat,
                camera_lon + half_lon
            ],

            "bottom_left": [
                camera_lat - half_lat,
                camera_lon - half_lon
            ],

            "bottom_right": [
                camera_lat - half_lat,
                camera_lon + half_lon
            ]
        }

        image_meta[image_id] = {

            "width_px":
                IMAGE_WIDTH,

            "height_px":
                IMAGE_HEIGHT,

            "capture_time":
                tstr(track_times[idx]),

            "corner_coordinates":
                corners
        }

        # O anda bu kameranin icinde hangi araclar var?
        visible = []

        for track_id, points in tracks.items():

            lat, lon = points[idx]

            if in_footprint(
                lat,
                lon,
                corners
            ):

                visible.append({

                    "track_id":
                        track_id,

                    "vehicle_class":
                        track_meta[
                            track_id
                        ]["vehicle_class"],

                    "lat":
                        lat,

                    "lon":
                        lon
                })

        image_truth[image_id] = {

            "zone":
                zone["name"],

            "capture_time":
                tstr(track_times[idx]),

            "time_index":
                idx,

            "primary_track":
                primary_track,

            "visible_tracks":
                visible
        }


with open(
    OUT_DIR / "image_meta.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        image_meta,
        f,
        ensure_ascii=False,
        indent=2
    )


# ============================================================
# 4. MOCK 1. ASAMA PREDICTIONS
#
# image_id,PredictionString
# ============================================================

prediction_rows = []
prediction_truth = {}


for image_id, truth in (
    image_truth.items()
):

    corners = (
        image_meta[
            image_id
        ]["corner_coordinates"]
    )

    predictions = []
    true_boxes = []

    for obj in truth["visible_tracks"]:

        cx, cy = point_to_pixel(
            obj["lat"],
            obj["lon"],
            corners
        )

        # 200 px2'den buyuk bboxlar
        width = random.randint(
            36,
            105
        )

        height = random.randint(
            24,
            70
        )

        gt_x = int(round(
            max(
                0,
                min(
                    IMAGE_WIDTH - width,
                    cx - width / 2
                )
            )
        ))

        gt_y = int(round(
            max(
                0,
                min(
                    IMAGE_HEIGHT - height,
                    cy - height / 2
                )
            )
        ))

        true_boxes.append({

            "track_id":
                obj["track_id"],

            "class":
                obj["vehicle_class"],

            "bbox": [
                gt_x,
                gt_y,
                width,
                height
            ],

            "gps": [
                obj["lat"],
                obj["lon"]
            ]
        })

        # Bazen detection kacirsin
        if random.random() < MISS_RATE:
            continue

        pred_class = (
            obj["vehicle_class"]
        )

        # Bazen sinifi yanlis tahmin etsin
        if (
            random.random()
            <
            MISCLASS_RATE
        ):

            pred_class = random.choice([
                c
                for c
                in VEHICLE_CLASSES
                if c != pred_class
            ])

        noisy_cx = (
            cx
            + random.gauss(
                0,
                PIXEL_JITTER_STD
            )
        )

        noisy_cy = (
            cy
            + random.gauss(
                0,
                PIXEL_JITTER_STD
            )
        )

        x = int(round(
            max(
                0,
                min(
                    IMAGE_WIDTH - width,
                    noisy_cx - width / 2
                )
            )
        ))

        y = int(round(
            max(
                0,
                min(
                    IMAGE_HEIGHT - height,
                    noisy_cy - height / 2
                )
            )
        ))

        confidence = round(
            random.uniform(
                0.72,
                0.98
            ),
            2
        )

        predictions.append((
            pred_class,
            confidence,
            x,
            y,
            width,
            height
        ))

    # Bazen false positive
    if (
        random.random()
        <
        FALSE_POSITIVE_RATE
    ):

        fp_class = random.choice(
            VEHICLE_CLASSES
        )

        width = random.randint(
            30,
            80
        )

        height = random.randint(
            20,
            55
        )

        x = random.randint(
            0,
            IMAGE_WIDTH - width
        )

        y = random.randint(
            0,
            IMAGE_HEIGHT - height
        )

        confidence = round(
            random.uniform(
                0.35,
                0.62
            ),
            2
        )

        predictions.append((
            fp_class,
            confidence,
            x,
            y,
            width,
            height
        ))

    if predictions:

        prediction_string = " ".join(

            f"{cls} {conf:.2f} "
            f"{x} {y} {w} {h}"

            for (
                cls,
                conf,
                x,
                y,
                w,
                h
            )
            in predictions
        )

    else:

        prediction_string = "none"

    prediction_rows.append([
        image_id,
        prediction_string
    ])

    prediction_truth[image_id] = {

        "true_objects":
            true_boxes,

        "mock_prediction_count":
            len(predictions)
    }


with open(
    OUT_DIR / "mock_predictions.csv",
    "w",
    encoding="utf-8",
    newline=""
) as f:

    writer = csv.writer(f)

    writer.writerow([
        "image_id",
        "PredictionString"
    ])

    writer.writerows(
        prediction_rows
    )


# ============================================================
# 5. FIELD REPORTS
# ============================================================

def format_coord(lat, lon):

    return (
        f"{lat:.5f}N "
        f"{lon:.5f}E"
    )


# Rapor turlerinin dagilimi
REPORT_TYPES = [

    ("supported", 0.45),

    ("wrong_class", 0.15),

    ("wrong_motion", 0.10),

    ("stale", 0.10),

    ("wrong_location", 0.10),

    ("irrelevant", 0.10),
]


def weighted_report_type():

    r = random.random()

    total = 0

    for name, probability in REPORT_TYPES:

        total += probability

        if r <= total:
            return name

    return "irrelevant"


def make_vehicle_report(
    track_id,
    idx,
    report_type
):

    meta = track_meta[track_id]

    true_class = (
        meta["vehicle_class"]
    )

    lat, lon = (
        tracks[track_id][idx]
    )

    motion, speed = (
        classify_motion(
            tracks[track_id],
            idx
        )
    )

    source = (
        "official"
        if random.random() < 0.68
        else "third_party"
    )

    report_dt = (
        track_times[idx]
    )

    reported_lat, reported_lon = (
        jitter_geo(
            lat,
            lon,
            meters=random.randint(
                5,
                35
            )
        )
    )

    claimed_class = true_class

    claimed_motion = (
        motion_text(motion)
    )

    # --------------------------------------------------------
    # YANLIS SINIF
    # --------------------------------------------------------

    if report_type == "wrong_class":

        claimed_class = random.choice([
            c
            for c
            in VEHICLE_CLASSES
            if c != true_class
        ])

    # --------------------------------------------------------
    # YANLIS HAREKET
    # --------------------------------------------------------

    elif report_type == "wrong_motion":

        claimed_motion = (
            wrong_motion_text(
                motion
            )
        )

    # --------------------------------------------------------
    # ESKI / BAYAT RAPOR
    # --------------------------------------------------------

    elif report_type == "stale":

        stale_idx = max(
            0,
            idx
            - random.randint(
                6,
                9
            )
        )

        old_lat, old_lon = (
            tracks[
                track_id
            ][stale_idx]
        )

        reported_lat, reported_lon = (
            jitter_geo(
                old_lat,
                old_lon,
                meters=20
            )
        )

    # --------------------------------------------------------
    # YANLIS KONUM
    # --------------------------------------------------------

    elif report_type == "wrong_location":

        reported_lat, reported_lon = (
            offset_point(
                lat,
                lon,

                north_km=
                random.choice([-1, 1])
                *
                random.uniform(
                    1.2,
                    2.2
                ),

                east_km=
                random.choice([-1, 1])
                *
                random.uniform(
                    1.0,
                    2.0
                )
            )
        )

    # --------------------------------------------------------
    # ILGISIZ RAPOR
    # --------------------------------------------------------

    if report_type == "irrelevant":

        templates = [

            (
                "Planli tatbikat nedeniyle "
                "gun icinde bolgede dost "
                "unsurlar bulunacak."
            ),

            (
                "Bolgedeki telsiz "
                "baglantisinda kisa sureli "
                "kesinti bildirildi."
            ),

            (
                "Devriye ekibi yol uzerinde "
                "olagandisi bir durum "
                "bildirmedi."
            ),

            (
                "Bolgedeki bakim ekibi "
                "planli calismasini "
                "surduruyor."
            )
        ]

        text = random.choice(
            templates
        )

    else:

        text = (

            f"{format_coord(reported_lat, reported_lon)} "
            f"civarinda 1 {claimed_class} goruldu; "
            f"{claimed_motion}."
        )

    report = {

        "time":
            tstr(report_dt),

        "source":
            source,

        "text":
            text
    }

    truth = {

        "kind":
            report_type,

        "related_track":
            (
                track_id
                if report_type
                != "irrelevant"
                else None
            ),

        "true_class":
            true_class,

        "true_motion":
            motion,

        "report_time":
            tstr(report_dt),

        "true_position": [
            lat,
            lon
        ],

        "reported_position":
            (
                [
                    reported_lat,
                    reported_lon
                ]
                if report_type
                != "irrelevant"
                else None
            )
    }

    return report, truth


reports = []
report_truth = []

# Her arac icin 3 rapor:
# 12:25
# 13:00
# 13:40

candidate_indices = [
    5,
    12,
    20
]


for track_id in tracks:

    for idx in candidate_indices:

        report_type = (
            weighted_report_type()
        )

        report, truth = (
            make_vehicle_report(
                track_id,
                idx,
                report_type
            )
        )

        reports.append(report)
        report_truth.append(truth)


# Biraz da tamamen baglamsal rapor ekle
extra_reports = [

    {
        "time": "12:15",
        "source": "official",
        "text":
            "Planli tatbikat nedeniyle "
            "gun icinde bolgede dost "
            "unsurlar bulunacak."
    },

    {
        "time": "12:40",
        "source": "third_party",
        "text":
            "Kuzey yolu civarinda "
            "sivil bisiklet trafigi "
            "goruldu."
    },

    {
        "time": "13:20",
        "source": "official",
        "text":
            "Bakim ekibinin planli "
            "saha calismasi devam ediyor."
    },

    {
        "time": "13:50",
        "source": "third_party",
        "text":
            "Bolge genelinde hava "
            "gorusu iyi, yagis yok."
    }
]


for report in extra_reports:

    reports.append(report)

    report_truth.append({

        "kind":
            "irrelevant",

        "related_track":
            None,

        "true_class":
            None,

        "true_motion":
            None,

        "report_time":
            report["time"],

        "true_position":
            None,

        "reported_position":
            None
    })


# Saat sirasina koy
paired = sorted(

    zip(
        reports,
        report_truth
    ),

    key=lambda x:
        x[0]["time"]
)


reports = [
    item[0]
    for item in paired
]

report_truth = [
    item[1]
    for item in paired
]


with open(
    OUT_DIR / "field_reports.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        reports,
        f,
        ensure_ascii=False,
        indent=2
    )


# ============================================================
# 6. GROUND TRUTH
#
# BU DOSYAYI AGENT'A VERMEYIN.
#
# Matcher ve validator'inizi test etmek icin.
# ============================================================

ground_truth = {

    "_warning":
        (
            "Bu dosya sadece test icindir. "
            "Agent/pipeline girdisi olarak "
            "kullanmayin."
        ),

    "seed":
        SEED,

    "base":
        BASE,

    "tracks": {},

    "images":
        image_truth,

    "prediction_truth":
        prediction_truth,

    "reports": {}
}


for track_id, points in tracks.items():

    ground_truth["tracks"][track_id] = {

        **track_meta[track_id],

        "points": [

            {
                "time":
                    tstr(dt),

                "lat":
                    round(lat, 6),

                "lon":
                    round(lon, 6)
            }

            for dt, (lat, lon)
            in zip(
                track_times,
                points
            )
        ]
    }


for i, truth in enumerate(
    report_truth
):

    ground_truth[
        "reports"
    ][str(i)] = truth


with open(
    OUT_DIR / "ground_truth.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        ground_truth,
        f,
        ensure_ascii=False,
        indent=2
    )


# ============================================================
# SUMMARY
# ============================================================

print()
print("Mock data olusturuldu:")

for path in sorted(
    OUT_DIR.iterdir()
):

    print(
        " -",
        path
    )

print()
print(
    "Track sayisi      :",
    len(tracks)
)

print(
    "Goruntu sayisi    :",
    len(image_meta)
)

print(
    "Rapor sayisi      :",
    len(reports)
)

print(
    "Prediction satiri :",
    len(prediction_rows)
)