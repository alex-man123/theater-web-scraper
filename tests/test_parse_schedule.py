from datetime import date, datetime

from odeon.crawler.normalize import title_key
from odeon.crawler.parse_schedule import announced_count, match_show, parse_schedule_html

from .conftest import snapshot

REF = date(2026, 11, 22)


def perfs():
    result, problems = parse_schedule_html(snapshot("program_rendered.html"), REF)
    assert problems == []
    return result


def test_all_announced_cards_are_extracted():
    html = snapshot("program_rendered.html")
    assert announced_count(html) == 23
    assert len(perfs()) == 23


def test_card_fields_and_timezone():
    by_id = {p.external_id: p for p in perfs()}
    macbeth = by_id["perf-1792411148534-9gho"]
    assert macbeth.source_title == "Macbeth"
    assert macbeth.local_date == date(2026, 12, 3)
    assert macbeth.start_at_utc == datetime(2026, 12, 3, 17, 0)  # 19:00 ora României
    assert macbeth.venue == "Sala Majestic"
    assert macbeth.age_label == "18+"
    assert macbeth.notes == "Supratitrare în limba franceză, la cerere"
    assert macbeth.status == "programat"


def test_rescheduled_status_and_missing_venue():
    by_id = {p.external_id: p for p in perfs()}
    cabaret = by_id["perf-1789305742938-co5h"]
    assert cabaret.status == "reprogramat"
    assert cabaret.notes.startswith("Reprogramat din data de 24 sept. 2026")
    lexicon = by_id["perf-1792411239788-pmi2"]
    assert lexicon.venue is None  # sala nu e publicată pe card -> rămâne necompletată
    tour = by_id["perf-1795166298617-94p0"]
    assert tour.venue is None and tour.performance_type == "Tur ghidat"


def test_chronological_order_of_source():
    starts = [p.start_at_utc for p in perfs()]
    assert starts == sorted(starts)


def test_no_html_in_extracted_text():
    for p in perfs():
        for value in (p.source_title, p.venue, p.notes, p.subtitle):
            assert value is None or "<" not in value


def test_match_show_exact_and_prefix():
    shows = {title_key(t): i for i, t in enumerate(
        ["Macbeth", "Clasic e fantastic", "Soldatul de ciocolată sau Armele și omul", "Cabaret"])}
    assert match_show("Macbeth", shows) == 0
    assert match_show("Clasic e Fantastic - Copilăria lui Beethoven", shows) == 1
    assert match_show("Soldatul de ciocolată", shows) == 2
    assert match_show("Tur ghidat", shows) is None
    assert match_show("Cab", shows) is None  # nu potrivim fragmente de cuvânt
