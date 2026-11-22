"""Verifică scraperul pe pagini reale salvate (eșantion comparat manual cu site-ul)."""
from datetime import date

import pytest

from odeon.crawler.parse_show import discover_show_urls, parse_show_page

from .conftest import snapshot


def parse(slug):
    return parse_show_page(snapshot(f"{slug}.html"), f"https://teatrul-odeon.ro/spectacol/{slug}/")


def test_macbeth_matches_source_page():
    s = parse("macbeth")
    assert s.title == "Macbeth"
    assert s.subtitle == "după William Shakespeare"
    assert s.author == "William Shakespeare"
    assert s.director == "Silvia Costa"
    assert s.premiere_date == date(2025, 9, 26)
    assert s.duration_text == "2h 10′" and s.duration_minutes == 130
    assert s.age_recommendation == "Nerecomandat sub 14 ani"
    assert s.language == "Spectacolul beneficiază de traducere în limba franceză, la cerere."
    assert s.poster_source_url == "https://teatrul-odeon.ro/wp-content/uploads/2025/07/Macbeth-afis-683x1024.jpg"
    assert s.cast[0] == {"name": "Mihai SMARANDACHE", "character": "Macbeth"}
    assert {"name": "Ioana MĂRCOIU", "character": "Lady Macbeth"} in s.cast
    assert len(s.cast) == 8
    assert {"role": "Muzica originală", "name": "Nicola Ratti"} in s.team
    assert {"role": "Asistent regie", "name": "Luna Scolari"} in s.team


def test_description_is_plain_text_without_html_or_press_quotes():
    s = parse("macbeth")
    assert s.description.startswith("Spectacol creat inițial de către Comédie-Française")
    assert "<" not in s.description and "&nbsp;" not in s.description
    cab = parse("cabaret")
    assert cab.description is None or "Extrase de presă" not in cab.description


def test_team_roles_are_kept_as_published_and_split_by_dash_separator():
    s = parse("cabaret")
    assert {"role": "Regia, coregrafia, costumele", "name": "RĂZVAN MAZILU"} in s.team
    assert {"role": "Light design", "name": "Costi Baciu"} in s.team
    assert {"role": "Light design", "name": "Ștefan Ioșca"} in s.team
    assert {"role": "Orchestra – pian", "name": "Mihai Murariu"} in s.team
    assert {"name": "Ioana Mărcoiu", "character": "Sally Bowles"} in s.cast
    # titlul de grup "Trupa de la Kit Kat Club" nu este o persoană
    assert all("Kit Kat" not in c["name"] for c in s.cast)
    assert s.director == "RĂZVAN MAZILU"


def test_mixed_cast_and_team_paragraphs_and_author_from_team():
    s = parse("gardenia")
    assert len(s.cast) == 4
    assert s.author == "Elżbieta Chowaniec"
    assert s.director == "Zoltán Balázs (Ungaria)"
    assert s.subtitle == "de Elżbieta Chowaniec, regia Zoltán Balázs (Ungaria)"


def test_alternating_actors_become_separate_entries_with_same_character():
    s = parse("svejk")
    mullerova = [c for c in s.cast if c["character"] == "Doamna Mullerova"]
    assert mullerova == [{"name": "Dorina Lazăr", "character": "Doamna Mullerova"},
                         {"name": "Dana Voicu", "character": "Doamna Mullerova"}]


def test_link_with_line_break_inside_anchor():
    s = parse("pescarusul")
    assert {"name": "Alina Berzunțeanu", "character": "Irina Nikolaevna Arkadina"} in s.cast
    assert s.author == "A. P. Cehov"
    assert s.director == "Andrei și Andreea Grosu"


def test_cast_header_in_separate_paragraph_and_bold_label_without_colon():
    s = parse("ludwig")  # "<strong>Cu:</strong>" + nume; "<strong>Regie și decor</strong> Dragoș Galgoțiu"
    assert {"name": "Eduard Trifa"} in s.cast
    assert all("character" not in c for c in s.cast)
    assert {"role": "Regie și decor", "name": "Dragoș Galgoțiu"} in s.team
    assert s.director == "Dragoș Galgoțiu"


def test_plain_label_followed_by_bold_name():
    s = parse("am-avut-o-livada")  # "Regia <strong>Eugen Jebeleanu</strong>"
    assert {"role": "Regia", "name": "Eugen Jebeleanu"} in s.team
    assert {"name": "Niko Becker", "character": "Matei"} in s.cast
    assert s.director == "Eugen Jebeleanu"


def test_role_on_its_own_line_and_technical_direction_is_not_director():
    s = parse("one-man-aproape-show")  # "<em>Light designers</em><br>Nume<br>Nume"
    assert {"role": "Light designers", "name": "Cosmin Clenciu"} in s.team
    assert {"role": "Light designers", "name": "Ștefan Ioșca"} in s.team
    assert {"role": "Regia tehnică", "name": "Dan Iosif"} in s.team
    assert s.director == "Pavel Bartoș"  # din "Scenariul și Regia", nu din "Regia tehnică"


def test_actor_first_format_is_detected_from_profile_links():
    s = parse("tertium-non-datur")  # "<a href=/om/...>Pavel BARTOȘ</a> – Van de Pioch, ..."
    assert {"name": "Pavel BARTOȘ", "character": "Van de Pioch, Amantul, Domnul Michaud"} in s.cast
    assert s.author == "Sacha GUITRY"


def test_cast_without_tabs_and_cu_header():
    luli = parse("eu-sunt-luli")
    assert luli.cast == [{"name": "Anda Saltelechi"}, {"name": "Alina Berzunțeanu"}, {"name": "Ioana Mărcoiu"}]
    assert luli.subtitle is None or not luli.subtitle.startswith("http")
    luna = parse("luna-verde")  # "Cu: Alina Berzunțeanu, Cezar Antal (vioară electrică)"
    assert {"name": "Alina Berzunțeanu"} in luna.cast


def test_missing_fields_stay_empty():
    s = parse("clasic-e-fantastic")
    assert s.title == "Clasic e fantastic"
    for field in ("author", "director", "description", "duration_minutes", "age_recommendation",
                  "premiere_date", "poster_source_url", "language", "genre"):
        assert getattr(s, field) is None, field
    assert s.cast == [] and s.team == []
    # autor necunoscut când creditul nu are forma "de X" / "după X"
    assert parse("jurnalul-lui-robinson-crusoe").author is None


def test_author_from_credit_line_variants():
    from odeon.crawler.parse_show import author_from_credit, director_from_credit
    assert author_from_credit("după Ceasornicăria Taus de Gellu Naum, regia Dragoș Galgoțiu") == "Gellu Naum"
    assert author_from_credit("de Enda Walsh, după „Frații Karamazov” de F.M. Dostoievski") == "Enda Walsh"
    assert author_from_credit("de Yann Verburgh după Livada de vișini de A. P. Cehov") == "Yann Verburgh"
    assert author_from_credit("după William Shakespeare") == "William Shakespeare"
    assert author_from_credit("Un spectacol de Gianina Cărbunariu") == "Gianina Cărbunariu"
    assert author_from_credit("Spectacol de poezie pe versuri de Federico Garcia Lorca") is None
    assert director_from_credit("de Will Eno, regia și traducerea Teodora Petre") == "Teodora Petre"
    assert director_from_credit("de A. P. Cehov, regia Andrei și Andreea Grosu") == "Andrei și Andreea Grosu"
    assert director_from_credit("de Bernard Shaw, regia Andrei Șerban") == "Andrei Șerban"


def test_non_show_page_is_rejected():
    assert parse_show_page("<html><body class='page'><h1>Contact</h1></body></html>",
                           "https://teatrul-odeon.ro/contact/") is None


def test_discovery_finds_unique_show_urls():
    urls = discover_show_urls(snapshot("stagiune.html"), "https://teatrul-odeon.ro/")
    assert "https://teatrul-odeon.ro/spectacol/macbeth/" in urls
    assert len(urls) == len(set(urls)) >= 30
    assert all(u.startswith("https://teatrul-odeon.ro/spectacol/") and u.endswith("/") for u in urls)


@pytest.mark.parametrize("slug", ["macbeth", "cabaret", "gardenia", "pescarusul",
                                  "jurnalul-lui-robinson-crusoe", "svejk"])
def test_cast_and_team_have_required_keys(slug):
    s = parse(slug)
    assert s.cast and s.team
    assert all(set(c) <= {"name", "character"} and c["name"] for c in s.cast)
    assert all(set(t) == {"role", "name"} and t["name"] for t in s.team)


def test_one_div_per_line_variant():
    s = parse("delirium")  # fiecare rând este un <div>, nu <p>/<br>
    assert {"name": "Marius Damian", "character": "Feodor"} in s.cast
    assert {"name": "Meda Victor", "character": "Katerina"} in s.cast
    assert {"role": "Regie", "name": "Vlad Massaci"} in s.team
    assert {"role": "Muzică și sound design", "name": "Vlaicu Golcea"} in s.team
    assert s.director == "Vlad Massaci"


def test_plain_role_without_separator():
    s = parse("persona")  # "Regia Radu Alexandru Nica"
    assert {"role": "Regia", "name": "Radu Alexandru Nica"} in s.team
    assert {"role": "Light design", "name": "Andrei Délczeg"} in s.team
    assert {"name": "Crina Mureșan", "character": "Elisabet Vogler"} in s.cast
    assert s.director == "Radu Alexandru Nica"
    j = parse("julieta-fara-romeo")
    assert {"role": "Asistent dramaturgie", "name": "Mădălina Stoica"} in j.team
    assert parse("cui-i-e-frica-de-virginia-woolf").director == "Alexandru Mâzgăreanu"


def test_credits_block_outside_tabs():
    s = parse("nijinski-agonie-si-extaz")  # fără tab "Distribuția"; bloc "Rol: Nume"
    assert {"role": "Coregrafie, concept, light design", "name": "Arcadie Rusu"} in s.team
    assert {"name": "Meda Victor"} in s.cast and {"name": "Cristian Hariga"} in s.cast
    assert all(len(c["name"].split()) <= 5 for c in s.cast)
    assert s.description.startswith("Un spectacol coregrafic semnat de Arcadie Rusu")


def test_unstructured_credits_are_not_invented():
    s = parse("puseu-de-iubire")  # doar text liber: nu fabricăm distribuție/echipă
    assert s.cast == [] and s.team == []
    assert s.subtitle == "Un performance de poezie cu Simona Popescu"


def test_character_slash_actor_format():
    s = parse("ceasornicaria-taus")  # "TAUS / <a href=/om/...>Ionel Mihăilescu</a>"
    assert {"name": "Ionel Mihăilescu", "character": "TAUS"} in s.cast
    assert {"name": "Marian Ghenea", "character": "PAPUS"} in s.cast
    assert {"name": "Mircea Constantinescu", "character": "PAPUS"} in s.cast
    assert all(c["name"] != "TAUS" for c in s.cast)
    assert {"role": "Regie și decor", "name": "Dragoș Galgoțiu"} in s.team
