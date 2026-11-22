"""Scraper pentru programul reprezentațiilor.

Pagina https://teatrul-odeon.ro/programul-teatrului-odeon-pe-zile/ conține doar
un container gol (#program-spectacole-container); cardurile sunt create de un
script JavaScript. De aceea HTML-ul pe care îl parsăm aici vine din render.py
(Playwright). Structura unui card, observată pe site:

  .tsp-card[data-perf-id]          -> identificator stabil al reprezentației
    .tsp-day-short / .tsp-day-num / .tsp-month-short  -> "dum" "22" "nov."
    .tsp-cat-pill                  -> sala ("Sala Majestic") sau o categorie ("Tur ghidat")
    h3.tsp-card-title (+ .tsp-age-pill)  -> titlu + vârstă ("14+")
    .tsp-time-row                  -> ora ("19:00")
    .tsp-card-subtitle             -> credit ("de X, regia Y")
    .tsp-surtitle                  -> supratitrare
    div cu border-left             -> mențiuni ("Reprogramat din data de ...")

Prețurile din .tsp-card-bottom sunt ignorate intenționat (nu se cer).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from bs4 import BeautifulSoup

from .normalize import (
    MONTHS, clean_text, infer_year, local_to_utc, parse_time, strip_diacritics, title_key,
)


@dataclass
class PerformanceData:
    external_id: str | None
    source_title: str
    start_at_utc: datetime
    local_date: date
    venue: str | None = None
    performance_type: str | None = None
    status: str = "programat"
    notes: str | None = None
    age_label: str | None = None
    subtitle: str | None = None
    warnings: list[str] = field(default_factory=list)


def _text(card, selector):
    el = card.select_one(selector)
    return clean_text(el.get_text(" ", strip=True)) if el else None


def status_from_notes(notes: list[str]) -> str:
    joined = strip_diacritics(" ".join(notes)).lower()
    if "anulat" in joined:
        return "anulat"
    if "amanat" in joined:
        return "amanat"
    if "reprogramat" in joined:
        return "reprogramat"
    return "programat"


def parse_schedule_html(html: str, reference: date) -> tuple[list[PerformanceData], list[str]]:
    """Returnează (reprezentații, avertismente). `reference` = data colectării (ora RO)."""
    soup = BeautifulSoup(html, "lxml")
    result: list[PerformanceData] = []
    problems: list[str] = []
    for card in soup.select(".tsp-card"):
        title_el = card.select_one(".tsp-card-title")
        if title_el is None:
            problems.append("card fără titlu ignorat")
            continue
        age_el = title_el.select_one(".tsp-age-pill")
        age = clean_text(age_el.get_text()) if age_el else None
        if age_el:
            age_el.extract()
        title = clean_text(title_el.get_text(" ", strip=True))

        day_txt, month_txt = _text(card, ".tsp-day-num"), _text(card, ".tsp-month-short")
        weekday = _text(card, ".tsp-day-short")
        month = MONTHS.get(strip_diacritics(month_txt or "").lower().rstrip("."))
        start_time = parse_time(_text(card, ".tsp-time-row"))
        if not (title and day_txt and day_txt.isdigit() and month and start_time):
            problems.append(f"card incomplet ignorat: {title!r} {day_txt} {month_txt}")
            continue
        perf_date = infer_year(int(day_txt), month, weekday, reference)
        if perf_date is None:
            problems.append(f"nu pot deduce anul pentru {title!r} {day_txt} {month_txt}")
            continue

        pill = _text(card, ".tsp-cat-pill")
        venue = pill if pill and re.search(r"\bsala\b", strip_diacritics(pill).lower()) else None
        perf_type = pill if pill and venue is None else None

        notes = []
        for div in card.find_all("div", recursive=False):
            if "border-left" in (div.get("style") or ""):
                t = clean_text(div.get_text(" ", strip=True))
                if t:
                    notes.append(t)
        surtitle = _text(card, ".tsp-surtitle")
        all_notes = notes + ([surtitle] if surtitle else [])

        result.append(PerformanceData(
            external_id=card.get("data-perf-id") or None,
            source_title=title,
            start_at_utc=local_to_utc(perf_date, start_time),
            local_date=perf_date,
            venue=venue,
            performance_type=perf_type,
            status=status_from_notes(notes),
            notes="\n".join(all_notes) or None,
            age_label=age,
            subtitle=_text(card, ".tsp-card-subtitle"),
        ))
    return result, problems


def announced_count(html: str) -> int | None:
    """Numărul anunțat în antet ("23 reprezentații programate"), pentru verificare."""
    m = re.search(r"(\d+)\s+reprezenta", BeautifulSoup(html, "lxml").get_text(" "))
    return int(m.group(1)) if m else None


def match_show(source_title: str, shows: dict[str, int]) -> int | None:
    """Asociază un titlu din program cu un spectacol (shows: title_key -> id).

    1. potrivire exactă a cheii normalizate ("Lexiconul amar" == "Lexiconul amar");
    2. altfel, un titlu care îl începe pe celălalt la granița de cuvânt
       ("Clasic e Fantastic - Copilăria lui Beethoven" -> "Clasic e fantastic",
        "Soldatul de ciocolată" -> "Soldatul de ciocolată sau Armele și omul");
       la mai multe variante alegem cheia cea mai lungă (cea mai specifică).
    """
    key = title_key(source_title)
    if not key:
        return None
    if key in shows:
        return shows[key]
    candidates = [k for k in shows if k and (key.startswith(k + " ") or k.startswith(key + " "))]
    if not candidates:
        return None
    return shows[max(candidates, key=len)]
