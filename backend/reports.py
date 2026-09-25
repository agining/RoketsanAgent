import re


VEHICLE_WORDS = {
    "car": [
        "car",
        "otomobil",
        "araba",
    ],
    "van": [
        "van",
        "panelvan",
        "minivan",
    ],
    "truck": [
        "truck",
        "kamyon",
        "tır",
        "tir",
    ],
    "bus": [
        "bus",
        "otobüs",
        "otobus",
    ],
}


def parse_coordinate(text):
    """
    Örnek:
    39.94653N 32.85409E
    """

    pattern = (
        r"([0-9]{1,2}\.[0-9]+)\s*[Nn]\s+"
        r"([0-9]{1,3}\.[0-9]+)\s*[Ee]"
    )

    match = re.search(
        pattern,
        text,
    )

    if not match:
        return None

    return {
        "lat": float(match.group(1)),
        "lon": float(match.group(2)),
    }


def parse_vehicle_type(text):
    text_lower = text.lower()

    for vehicle_type, words in VEHICLE_WORDS.items():

        for word in words:

            if word in text_lower:
                return vehicle_type

    return None


def parse_count(text):
    """
    Basit araç sayısı parser.
    """

    patterns = [
        r"\b(\d+)\s+(?:car|van|truck|bus)\b",
        r"\b(\d+)\s+(?:otomobil|araba|kamyon|otobüs|otobus|panelvan)\b",
    ]

    text_lower = text.lower()

    for pattern in patterns:

        match = re.search(
            pattern,
            text_lower,
        )

        if match:
            return int(
                match.group(1)
            )

    return None


def parse_zone(text, zones):
    """
    Raporda zone ismi açıkça geçiyorsa yakala.
    """

    text_lower = text.lower()

    for zone in zones:

        zone_name = zone["name"]

        if zone_name.lower() in text_lower:
            return zone_name

    return None


def detect_claims(text):
    text_lower = text.lower()

    stationary_words = [
        "bekliyor",
        "sabit",
        "duruyor",
        "hareketsiz",
    ]

    moving_words = [
        "hareket ediyor",
        "ilerliyor",
        "gidiyor",
    ]

    fast_words = [
        "hızla",
        "hizla",
        "yüksek hız",
        "yuksek hiz",
    ]

    leaving_words = [
        "uzaklaşıyor",
        "uzaklasiyor",
        "bölgeden ayrılıyor",
        "bolgeden ayriliyor",
    ]

    approaching_words = [
        "yaklaşıyor",
        "yaklasiyor",
        "üsse doğru",
        "usse dogru",
    ]

    normal_words = [
        "normal",
        "olağandışı bir durum yok",
        "olagandisi bir durum yok",
    ]

    friendly_words = [
        "dost unsur",
        "dost unsurlar",
        "friendly",
    ]

    exercise_words = [
        "tatbikat",
        "planlı çalışma",
        "planli calisma",
        "bakım ekibi",
        "bakim ekibi",
    ]

    claims_stationary = any(
        word in text_lower
        for word in stationary_words
    )

    claims_moving = any(
        word in text_lower
        for word in moving_words
    )

    claims_fast = any(
        word in text_lower
        for word in fast_words
    )

    claims_leaving = any(
        word in text_lower
        for word in leaving_words
    )

    claims_approaching = any(
        word in text_lower
        for word in approaching_words
    )

    claims_normal = any(
        word in text_lower
        for word in normal_words
    )

    friendly_claim = any(
        word in text_lower
        for word in friendly_words
    )

    exercise_claim = any(
        word in text_lower
        for word in exercise_words
    )

    # Yaklaşan / uzaklaşan / hızlı hareket eden araç
    # doğal olarak hareket ediyor kabul edilir.
    if (
        claims_leaving
        or claims_approaching
        or claims_fast
    ):
        claims_moving = True

    return {
        "claims_stationary": claims_stationary,
        "claims_moving": claims_moving,
        "claims_fast": claims_fast,
        "claims_leaving": claims_leaving,
        "claims_approaching": claims_approaching,
        "claims_normal": claims_normal,
        "friendly_claim": friendly_claim,
        "exercise_claim": exercise_claim,
    }

def classify_report_type(parsed):
    """
    Rapora kaba bir tip verir.
    """

    if parsed["friendly_claim"]:
        return "FRIENDLY"

    if parsed["exercise_claim"]:
        return "EXERCISE"

    if parsed["claims_normal"]:
        return "NORMAL"

    if parsed["coord"] is not None:
        return "VEHICLE_OBSERVATION"

    return "GENERAL"


def parse_report(
    report,
    zones_data,
):
    text = report["text"]

    coord = parse_coordinate(
        text
    )

    vehicle_type = parse_vehicle_type(
        text
    )

    count = parse_count(
        text
    )

    zone = parse_zone(
        text,
        zones_data["zones"],
    )

    claims = detect_claims(
        text
    )

    parsed = {
        "time": report["time"],
        "source": report["source"],
        "text": text,

        "coord": coord,

        "vehicle_type":
            vehicle_type,

        "count":
            count,

        "zone":
            zone,

        **claims,
    }

    parsed["report_type"] = (
        classify_report_type(
            parsed
        )
    )

    return parsed


def parse_reports(
    reports,
    zones_data,
):
    return [
        parse_report(
            report,
            zones_data,
        )
        for report in reports
    ]