"""Small formatting helpers for analyst-facing agent answers.

The LLM is still free to choose the best shape for the question. This module
only normalizes the final Markdown so incomplete data does not leak as broken
UI text.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Any

RISK_DISPLAY = {
    "DUSUK": "DÜŞÜK",
    "ORTA": "ORTA",
    "YUKSEK": "YÜKSEK",
    "KRITIK": "KRİTİK",
}

EMPTY_TOKENS = {"", "none", "null", "undefined", "nan", "[]"}


def is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    text = str(value).strip()
    return bool(text) and text.lower() not in EMPTY_TOKENS


def join_nonempty(values: Iterable[Any], separator: str = " · ") -> str:
    return separator.join(str(v).strip() for v in values if is_present(v))


def format_optional(value: Any, fallback: str = "") -> str:
    return str(value).strip() if is_present(value) else fallback


def format_risk(level: str | None) -> str:
    if not is_present(level):
        return ""
    return RISK_DISPLAY.get(str(level).strip().upper(), str(level).strip())


def _tr_number(value: float, digits: int = 1) -> str:
    rounded = round(value, digits)
    if rounded.is_integer():
        return f"{int(rounded):,}".replace(",", ".")
    whole, frac = f"{rounded:,.{digits}f}".split(".")
    return f"{whole.replace(',', '.')},{frac.rstrip('0')}"


def format_distance(value: float | int | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return ""
    return f"{_tr_number(float(value), 0)} m"


def format_duration(value: float | int | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return ""
    return f"{_tr_number(float(value), 1)} dk"


def format_degrees(value: float | int | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return ""
    return f"{_tr_number(float(value), 1)}°"


def format_percent(value: float | int | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return ""
    pct = float(value) * 100 if abs(float(value)) <= 1 else float(value)
    return f"%{_tr_number(pct, 1)}"


def render_table_if_needed(headers: list[str], rows: list[list[Any]]) -> str:
    clean_headers = [str(h).strip() for h in headers if is_present(h)]
    clean_rows = []
    for row in rows:
        cells = [format_optional(cell) for cell in row[:len(clean_headers)]]
        if any(cells):
            clean_rows.append(cells + [""] * (len(clean_headers) - len(cells)))
    if len(clean_headers) < 2 or len(clean_rows) < 2:
        return ""
    table = [
        "| " + " | ".join(clean_headers) + " |",
        "| " + " | ".join("---" for _ in clean_headers) + " |",
    ]
    table.extend("| " + " | ".join(row) + " |" for row in clean_rows)
    return "\n".join(table)


def clean_markdown(markdown: str | None) -> str:
    text = "" if markdown is None else str(markdown)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Hide raw empty/null tokens that often appear when optional fields are interpolated.
    text = re.sub(r"\b(None|null|undefined|NaN)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[\s*\]", "", text)

    # Empty emphasis, parentheses, headings and table rows.
    text = re.sub(r"\*\*\s*\*\*", "", text)
    text = re.sub(r"__\s*__", "", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"(?m)^#{1,6}\s*$\n?", "", text)
    text = re.sub(r"(?m)^\|\s*(?:\|\s*)+$\n?", "", text)

    # Normalize display-only risk labels without touching backend enum values.
    for raw, display in RISK_DISPLAY.items():
        text = re.sub(rf"\b{raw}\b", display, text)

    # Turkish-friendly numeric display for common units.
    def unit_repl(match: re.Match[str]) -> str:
        number = float(match.group("num"))
        unit = match.group("unit")
        digits = 0 if unit == "m" else 1
        return f"{_tr_number(number, digits)} {unit}"

    text = re.sub(r"(?P<num>\d+\.\d{2,})\s*(?P<unit>m|dk)\b", unit_repl, text)
    text = re.sub(r"(?P<num>\d+\.\d{2,})\s*°", lambda m: f"{_tr_number(float(m.group('num')), 1)}°", text)
    text = re.sub(r"(?<!\d)0\.(\d{2,})", lambda m: format_percent(float(f"0.{m.group(1)}")), text)

    # Remove separators left behind by missing optional fields.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r"(?:\s*[·/]\s*){2,}", " · ", text)
    text = re.sub(r"(?m)(^|\s)[·/]\s*", r"\1", text)
    text = re.sub(r"\s*[·/]\s*($|\n)", r"\1", text)
    text = re.sub(r"\(\s*([·/,;-])", "(", text)
    text = re.sub(r"([·/,;-])\s*\)", ")", text)

    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if re.fullmatch(r"[-*]\s*", stripped):
            continue
        if re.fullmatch(r"\d+[.)]\s*", stripped):
            continue
        lines.append(stripped.rstrip())
    text = "\n".join(lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text
