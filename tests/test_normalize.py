from datetime import date, datetime, time

from odeon.crawler.normalize import (
    clean_text, infer_year, local_to_utc, parse_duration_minutes, parse_ro_date, parse_time,
    title_key, utc_to_local,
)


def test_clean_text_keeps_diacritics_and_collapses_spaces():
    assert clean_text("  Pescărușul\xa0 de  A. P. Cehov ") == "Pescărușul de A. P. Cehov"
    assert clean_text("   ") is None
    assert clean_text(None) is None


def test_title_key_ignores_diacritics_case_and_punctuation():
    assert title_key("Ceasornicarul, tigrul și rechinii") == "ceasornicarul tigrul si rechinii"
    assert title_key("Neliniște") == title_key("NELINIŞTE")  # ș vs ş (sedilă)


def test_parse_ro_date():
    assert parse_ro_date("26 septembrie 2025") == date(2025, 9, 26)
    assert parse_ro_date("05 mai 2017") == date(2017, 5, 5)
    assert parse_ro_date("31 februarie 2020") is None
    assert parse_ro_date("fără dată") is None


def test_parse_duration_minutes():
    assert parse_duration_minutes("2h 10′") == 130
    assert parse_duration_minutes("1h 15″") == 75
    assert parse_duration_minutes("90 de minute") == 90
    assert parse_duration_minutes("1 oră și 20") == 80
    assert parse_duration_minutes("cu pauză") is None


def test_parse_time():
    assert parse_time("19:00") == time(19, 0)
    assert parse_time("ora 19.30") == time(19, 30)
    assert parse_time("25:00") is None


def test_infer_year_uses_published_weekday():
    ref = date(2026, 11, 22)
    assert infer_year(22, 11, "dum", ref) == date(2026, 11, 22)
    assert infer_year(3, 12, "joi", ref) == date(2026, 12, 3)
    # ianuarie în programul publicat în noiembrie -> anul următor (7 ian. 2027 e joi)
    assert infer_year(7, 1, "joi", ref) == date(2027, 1, 7)
    # fără zi a săptămânii: cea mai apropiată dată plauzibilă
    assert infer_year(7, 1, None, ref) == date(2027, 1, 7)


def test_timezone_round_trip_handles_dst():
    # iarna: UTC+2
    assert local_to_utc(date(2026, 12, 3), time(19, 0)) == datetime(2026, 12, 3, 17, 0)
    # vara: UTC+3
    assert local_to_utc(date(2026, 7, 3), time(19, 0)) == datetime(2026, 7, 3, 16, 0)
    assert utc_to_local(datetime(2026, 12, 3, 17, 0)).strftime("%H:%M") == "19:00"
