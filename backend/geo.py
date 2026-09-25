from math import (
    radians,
    sin,
    cos,
    sqrt,
    atan2,
    degrees,
)


def bbox_center(bbox):
    """
    bbox format:
    [x, y, w, h]
    """

    x, y, w, h = bbox

    cx = x + w / 2
    cy = y + h / 2

    return cx, cy


def pixel_to_gps(cx, cy, meta):
    """
    Piksel koordinatını image_meta içindeki
    dört köşe GPS koordinatını kullanarak
    yaklaşık lat/lon'a çevirir.
    """

    width = meta["width_px"]
    height = meta["height_px"]

    corners = meta["corner_coordinates"]

    tl_lat, tl_lon = corners["top_left"]
    tr_lat, tr_lon = corners["top_right"]
    bl_lat, bl_lon = corners["bottom_left"]
    br_lat, br_lon = corners["bottom_right"]

    # Pixel konumunu 0..1 aralığına getir
    u = cx / width
    v = cy / height

    # Üst kenarda interpolation
    top_lat = tl_lat * (1 - u) + tr_lat * u
    top_lon = tl_lon * (1 - u) + tr_lon * u

    # Alt kenarda interpolation
    bottom_lat = bl_lat * (1 - u) + br_lat * u
    bottom_lon = bl_lon * (1 - u) + br_lon * u

    # Dikey interpolation
    lat = top_lat * (1 - v) + bottom_lat * v
    lon = top_lon * (1 - v) + bottom_lon * v

    return lat, lon


def haversine_m(lat1, lon1, lat2, lon2):
    """
    İki GPS koordinatı arasındaki
    kuş uçuşu mesafeyi metre olarak hesaplar.
    """

    earth_radius_m = 6_371_000

    phi1 = radians(lat1)
    phi2 = radians(lat2)

    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)

    a = (
        sin(delta_phi / 2) ** 2
        + cos(phi1)
        * cos(phi2)
        * sin(delta_lambda / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a),
    )

    return earth_radius_m * c


def bearing_deg(lat1, lon1, lat2, lon2):
    """
    Nokta 1'den nokta 2'ye yön açısını hesaplar.

    0   = Kuzey
    90  = Doğu
    180 = Güney
    270 = Batı
    """

    phi1 = radians(lat1)
    phi2 = radians(lat2)

    delta_lambda = radians(
        lon2 - lon1
    )

    y = (
        sin(delta_lambda)
        * cos(phi2)
    )

    x = (
        cos(phi1) * sin(phi2)
        - sin(phi1)
        * cos(phi2)
        * cos(delta_lambda)
    )

    angle = degrees(
        atan2(y, x)
    )

    return (
        angle + 360
    ) % 360


def nearest_zone(lat, lon, zones):
    """
    Verilen koordinata en yakın zone center'ı bulur.
    """

    best_zone = None
    best_distance = float("inf")

    for zone in zones:
        zone_lat, zone_lon = zone["center"]

        distance = haversine_m(
            lat,
            lon,
            zone_lat,
            zone_lon,
        )

        if distance < best_distance:
            best_distance = distance
            best_zone = zone["name"]

    return (
        best_zone,
        best_distance,
    )


def analyze_position(
    lat,
    lon,
    zones_data,
):
    """
    Araç için:
    - en yakın zone
    - zone center mesafesi
    - üs mesafesi
    - üs yönü
    hesaplar.
    """

    base = zones_data["base"]

    base_lat = base["lat"]
    base_lon = base["lon"]

    zone_name, zone_distance_m = nearest_zone(
        lat,
        lon,
        zones_data["zones"],
    )

    distance_to_base_m = haversine_m(
        lat,
        lon,
        base_lat,
        base_lon,
    )

    bearing_to_base = bearing_deg(
        lat,
        lon,
        base_lat,
        base_lon,
    )

    bearing_from_base = bearing_deg(
        base_lat,
        base_lon,
        lat,
        lon,
    )

    return {
        "zone": zone_name,
        "zone_center_distance_m": round(
            zone_distance_m,
            1,
        ),
        "distance_to_base_m": round(
            distance_to_base_m,
            1,
        ),
        "bearing_to_base_deg": round(
            bearing_to_base,
            1,
        ),
        "bearing_from_base_deg": round(
            bearing_from_base,
            1,
        ),
    }