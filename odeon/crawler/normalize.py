"""Funcții pure de normalizare: text, date, ore, durate, titluri.

Nu fac cereri de rețea și nu ating baza de date, deci se testează ușor.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from odeon.config import SOURCE_TIMEZONE

TZ = ZoneInfo(SOURCE_TIMEZONE)

MONTHS = {
    "ian": 1, "ianuarie": 1, "feb": 2, "februarie": 2, "mar": 3, "martie": 3,
    "apr": 4, "aprilie": 4, "mai": 5, "iun": 6, "iunie": 6, "iul": 7, "iulie": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "septembrie": 9,
    "oct": 10, "octombrie": 10, "nov": 11, "noiembrie": 11, "dec": 12, "decembrie": 12,
}
# Python: luni = 0 ... duminică = 6
WEEKDAYS = {"lun": 0, "mar": 1, "mie": 2, "joi": 3, "vin": 4, "sam": 5, "dum": 6}


def clean_text(value: str | None) -> str | None:
    """Elimină spațiile multiple / nbsp; păstrează diacriticele. Gol -> None."""
    if value is None:
        return None
    value = unicodedata.normalize("NFC", value).replace("\xa0", " ").replace("​", "")
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r" *\n *", "\n", value).strip()
    return value or None


def strip_diacritics(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def title_key(title: str) -> str:
    """Cheie de comparare pentru titluri: fără diacritice, litere mici, fără punctuație."""
    t = strip_diacritics(title).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.strip()


def slugify(title: str) -> str:
    return title_key(title).replace(" ", "-")


def parse_ro_date(text: str | None) -> date | None:
    """'26 septembrie 2025' / '05 mai 2017' -> date. Returnează None dacă nu se potrivește."""
    if not text:
        return None
    m = re.search(r"(\d{1,2})\s+([A-Za-zăâîșşțţĂÂÎȘŞȚŢ]+)\.?\s+(\d{4})", text)
    if not m:
        return None
    month = MONTHS.get(strip_diacritics(m.group(2)).lower())
    if not month:
        return None
    try:
        return date(int(m.group(3)), month, int(m.group(1)))
    except ValueError:
        return None


def parse_duration_minutes(text: str | None) -> int | None:
    """'2h 10′' -> 130, '1h 15″' -> 75, '90 de minute' -> 90, '1 oră' -> 60."""
    if not text:
        return None
    t = strip_diacritics(text).lower()
    m = re.search(r"(\d+)\s*(?:h|ore|ora)\b\.?\s*(?:si\s*)?(\d+)?", t)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2) or 0)
    m = re.search(r"(\d+)\s*(?:de\s*)?(?:min|minute)\b", t)
    if m:
        return int(m.group(1))
    return None


def parse_time(text: str | None) -> time | None:
    if not text:
        return None
    m = re.search(r"(\d{1,2})[:.](\d{2})", text)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None
    return time(h, mi)


def infer_year(day: int, month: int, weekday_short: str | None, reference: date) -> date | None:
    """Programul publică doar ziua, luna și ziua săptămânii (ex. 'dum 22 nov.').

    Alegem anul în care ziua săptămânii coincide cu cea publicată; dacă sunt
    mai mulți candidați, îl luăm pe cel mai apropiat de data colectării.
    Fără ziua săptămânii, luăm cea mai apropiată dată (în fereastra -60 / +305 zile).
    """
    wanted = WEEKDAYS.get(strip_diacritics(weekday_short or "").lower()[:3])
    candidates = []
    for year in (reference.year - 1, reference.year, reference.year + 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            continue
    if wanted is not None:
        matching = [c for c in candidates if c.weekday() == wanted]
        if matching:
            return min(matching, key=lambda c: abs((c - reference).days))
    window = [c for c in candidates if -60 <= (c - reference).days <= 305]
    return min(window, key=lambda c: abs((c - reference).days)) if window else None


def local_to_utc(d: date, t: time) -> datetime:
    """Ora publicată de teatru (Europe/Bucharest) -> UTC naiv, pentru coloanele TIMESTAMP."""
    local = datetime.combine(d, t, tzinfo=TZ)
    return local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def utc_to_local(dt: datetime) -> datetime:
    """UTC naiv (din MySQL) -> ora locală a teatrului, pentru afișare."""
    return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(TZ)


def now_utc() -> datetime:
    return datetime.now(ZoneInfo("UTC")).replace(tzinfo=None, microsecond=0)


def today_local() -> date:
    return datetime.now(TZ).date()


__all__ = [
    "clean_text", "strip_diacritics", "title_key", "slugify", "parse_ro_date",
    "parse_duration_minutes", "parse_time", "infer_year", "local_to_utc",
    "utc_to_local", "now_utc", "today_local",
]
