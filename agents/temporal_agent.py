from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re
import unicodedata


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date
    label: str


def resolve_date_range(text: str, today: date | None = None) -> DateRange:
    today = today or date.today()
    normalized = normalize_text(text)

    explicit = _find_iso_date(normalized)
    if explicit:
        return DateRange(explicit, explicit, str(explicit))

    if "semana pasada" in normalized:
        this_monday = today - timedelta(days=today.weekday())
        start = this_monday - timedelta(days=7)
        end = this_monday - timedelta(days=1)
        return DateRange(start, end, "semana pasada")

    if "ayer" in normalized:
        day = today - timedelta(days=1)
        return DateRange(day, day, "ayer")

    if "mes" in normalized:
        return DateRange(today.replace(day=1), today, "mes actual")

    if "ano" in normalized or "year" in normalized:
        return DateRange(date(today.year, 1, 1), today, "ano actual")

    return DateRange(today, today, "hoy")


def _find_iso_date(text: str) -> date | None:
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if not match:
        return None
    return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    without_accents = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return without_accents.lower().strip()
