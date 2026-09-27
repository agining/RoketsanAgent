"""Evidence-bound extraction helpers for game scenario reports."""
from __future__ import annotations

import re
import unicodedata
from ..geo import hhmm_to_min


def report_minute(value) -> int | None:
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?", value):
        return None
    return hhmm_to_min(value)


def normalized_text(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold().replace("ı", "i"))
                   if not unicodedata.combining(c))


def explicit_coordinates(text: str) -> tuple[float, float] | None:
    match = re.search(r"(-?\d{1,3}(?:\.\d+)?)\s*([NS])\s*[,; ]+\s*(-?\d{1,3}(?:\.\d+)?)\s*([EW])", text, re.I)
    if match:
        lat, lon = abs(float(match[1])), abs(float(match[3]))
        lat *= -1 if match[2].upper() == "S" else 1
        lon *= -1 if match[4].upper() == "W" else 1
    else:
        match = re.search(r"(?:lat|enlem)\s*[:=]\s*(-?\d{1,3}(?:\.\d+)?)\s*[,; ]+\s*(?:lon|boylam)\s*[:=]\s*(-?\d{1,3}(?:\.\d+)?)", text, re.I)
        if not match:
            return None
        lat, lon = float(match[1]), float(match[2])
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


def stated_confidence(text: str) -> str | None:
    normalized = normalized_text(text)
    if any(term in normalized for term in ("belirsiz", "iddia", "ihbar", "olabilir")):
        return "low"
    if any(term in normalized for term in ("teyit edildi", "teyidi yapilmistir", "kesin olarak")):
        return "high"
    return None
