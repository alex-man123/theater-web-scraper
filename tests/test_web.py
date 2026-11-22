"""Rutele aplicației web, pe date colectate în baza de test.

Orice conexiune de rețea în afara localhost este blocată: interfața trebuie
să funcționeze fără acces la teatrul-odeon.ro.
"""
import re
import socket

import pytest

from odeon.crawler.run import crawl
from odeon.web import create_app

from .conftest import SNAPSHOT_NOW, TEST_DB
from .fake_site import FakeSite


@pytest.fixture
def client(test_db, poster_dir, monkeypatch):
    site = FakeSite()
    c = site.client()
    from .test_pipeline_db import PROGRAM
    crawl(test_db, c, schedule_file=PROGRAM, now=SNAPSHOT_NOW)
    c.close()

    real_connect = socket.socket.connect

    def local_only(sock, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError(f"aplicația web a încercat să acceseze rețeaua: {address}")
        return real_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", local_only)
    app = create_app(database=TEST_DB)
    app.config["NOW_FN"] = lambda: SNAPSHOT_NOW
    app.config["TESTING"] = True
    return app.test_client()


def show_id(test_db, slug):
    with test_db.cursor() as cur:
        cur.execute("SELECT id FROM shows WHERE slug=%s", (slug,))
        return cur.fetchone()["id"]


def html(resp):
    return resp.get_data(as_text=True)


def test_home_lists_shows_and_upcoming(client):
    r = client.get("/")
    assert r.status_code == 200
    body = html(r)
    assert "Reprezentații viitoare" in body and "Macbeth" in body
    assert 'name="viewport"' in body


def test_shows_list_and_search(client):
    body = html(client.get("/shows"))
    assert "Macbeth" in body and "Cabaret" in body and "Următoarea" in body
    found = html(client.get("/shows?q=macb"))
    assert "Macbeth" in found and "Cabaret" not in found
    assert "Pescărușul" in html(client.get("/shows?q=Pescărușul"))
    none = client.get("/shows?q=zzzinexistent")
    assert none.status_code == 200 and "Niciun spectacol" in html(none)
    assert client.get("/shows?q=%25_").status_code == 200  # caractere speciale LIKE


def test_show_detail_page(client, test_db):
    r = client.get(f"/shows/{show_id(test_db, 'macbeth')}")
    body = html(r)
    assert r.status_code == 200
    for text in ("Macbeth", "William Shakespeare", "Silvia Costa", "2h 10′", "Nerecomandat sub 14 ani",
                 "Lady Macbeth", "Ioana MĂRCOIU", "Muzica originală", "Nicola Ratti",
                 "joi, 3 decembrie 2026", "19:00", "Sala Majestic"):
        assert text in body, text
    poster = re.search(r'src="(/posters/[^"]+)"', body).group(1)
    img = client.get(poster)
    assert img.status_code == 200 and img.mimetype == "image/png"


def test_show_without_upcoming_performances_and_missing_fields(client, test_db):
    body = html(client.get(f"/shows/{show_id(test_db, 'gardenia')}"))
    assert "nu există reprezentații programate" in body
    body = html(client.get(f"/shows/{show_id(test_db, 'clasic-e-fantastic')}"))
    assert "poster-placeholder.svg" in body  # afiș lipsă -> substitut local
    assert "Distribuția nu este disponibilă" in body


def test_not_found_pages(client):
    assert client.get("/shows/999999").status_code == 404
    assert client.get("/shows/abc").status_code == 404
    assert client.get("/nu-exista").status_code == 404
    assert "404" in html(client.get("/shows/999999"))


def test_schedule_is_chronological(client):
    body = html(client.get("/schedule"))
    stamps = re.findall(r'<time class="perf-when" datetime="([^"]+)"', body)
    assert len(stamps) == 23
    assert stamps == sorted(stamps)
    assert stamps[0].startswith("2026-11-22T19:00:00+02:00")  # ora României, explicit
    assert "Sala Studio" in body and "Tur ghidat" in body
    studio = html(client.get("/schedule?venue=Sala+Studio"))
    assert "Sala Majestic" not in re.sub(r"<option.*?</option>", "", studio, flags=re.S)


def test_collected_text_is_escaped(client, test_db):
    # DATE DE TEST: un titlu cu HTML nu trebuie executat în pagină
    with test_db.cursor() as cur:
        cur.execute("INSERT INTO shows (slug, title, source_url) VALUES (%s, %s, %s)",
                    ("test-xss", "<script>alert(1)</script>", "https://example.test/"))
        new_id = cur.lastrowid
    test_db.commit()
    body = html(client.get(f"/shows/{new_id}"))
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
