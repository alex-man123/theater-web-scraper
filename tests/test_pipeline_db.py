"""Crawler complet -> MySQL (baza de test), fără rețea.

Verifică: asocierea reprezentațiilor, absența duplicatelor după două rulări,
actualizarea datelor modificate, reprogramări, reprezentații dispărute,
colectări eșuate, câmpuri lipsă și afișe locale.
"""
import json
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from odeon.crawler.run import crawl

from .conftest import FIXTURES, SNAPSHOT_NOW, snapshot
from .fake_site import FakeSite

PROGRAM = FIXTURES / "program_rendered.html"


def run(conn, site, schedule_file=PROGRAM, now=SNAPSHOT_NOW):
    client = site.client()
    try:
        return crawl(conn, client, schedule_file=schedule_file, now=now)
    finally:
        client.close()


def q(conn, sql, *args):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def test_first_run_stores_shows_performances_and_posters(test_db, poster_dir):
    stats = run(test_db, FakeSite())
    assert stats["performances_inserted"] == 23
    assert stats["shows_inserted"] >= 7

    macbeth = q(test_db, "SELECT * FROM shows WHERE slug='macbeth'")[0]
    assert macbeth["title"] == "Macbeth" and macbeth["director"] == "Silvia Costa"
    assert macbeth["source_url"] == "https://teatrul-odeon.ro/spectacol/macbeth/"
    cast = json.loads(macbeth["cast_json"])
    assert {"name": "Ioana MĂRCOIU", "character": "Lady Macbeth"} in cast  # diacritice păstrate
    # afiș: fișier local + URL original + hash
    assert macbeth["poster_storage"] == "file"
    assert (poster_dir / macbeth["poster_path"].split("/")[-1]).is_file()
    assert macbeth["poster_source_url"].endswith("Macbeth-afis-683x1024.jpg")
    assert len(macbeth["poster_hash"]) == 64

    # asocierea reprezentație -> spectacol
    rows = q(test_db, "SELECT p.source_title, s.slug, p.start_at, p.venue FROM performances p "
                      "JOIN shows s ON s.id = p.show_id WHERE p.external_id = 'perf-1792411148534-9gho'")
    assert rows[0]["slug"] == "macbeth"
    assert rows[0]["start_at"] == datetime(2026, 12, 3, 17, 0)  # 19:00 ora României, stocat în UTC
    clasic = q(test_db, "SELECT s.slug FROM performances p JOIN shows s ON s.id = p.show_id "
                        "WHERE p.source_title LIKE 'Clasic e Fantastic - Copil%%'")
    assert clasic[0]["slug"] == "clasic-e-fantastic"
    # titlu fără pagină de spectacol -> spectacol creat doar din program, marcat ca atare
    tour = q(test_db, "SELECT s.origin, s.source_url FROM performances p JOIN shows s ON s.id = p.show_id "
                      "WHERE p.source_title = 'Tur ghidat'")[0]
    assert tour["origin"] == "schedule"
    assert tour["source_url"].endswith("/programul-teatrului-odeon-pe-zile/")


def test_second_run_creates_no_duplicates_and_no_redownloads(test_db, poster_dir):
    site = FakeSite()
    run(test_db, site)
    shows_before = q(test_db, "SELECT COUNT(*) n FROM shows")[0]["n"]
    updated_before = {r["id"]: r["updated_at"] for r in q(test_db, "SELECT id, updated_at FROM shows")}
    site.requests.clear()

    stats = run(test_db, site)
    assert stats["shows_inserted"] == 0 and stats["shows_updated"] == 0
    assert stats["performances_inserted"] == 0 and stats["performances_updated"] == 0
    assert stats["performances_unchanged"] == 23
    assert q(test_db, "SELECT COUNT(*) n FROM shows")[0]["n"] == shows_before
    assert q(test_db, "SELECT COUNT(*) n FROM performances")[0]["n"] == 23
    assert q(test_db, "SELECT show_id, start_at, venue, COUNT(*) c FROM performances "
                      "GROUP BY show_id, start_at, venue HAVING c > 1") == ()
    assert site.poster_requests() == []  # afișele existente nu se redescarcă
    # updated_at nu se schimbă când datele sunt identice
    assert {r["id"]: r["updated_at"] for r in q(test_db, "SELECT id, updated_at FROM shows")} == updated_before


def test_changed_source_updates_existing_record(test_db, poster_dir):
    site = FakeSite()
    run(test_db, site)
    show_id = q(test_db, "SELECT id FROM shows WHERE slug='macbeth'")[0]["id"]

    # DATE DE TEST: simulăm o modificare pe site (durata și un rol din distribuție)
    modified = snapshot("macbeth.html").replace("2h 10&#8242;", "2h 20&#8242;").replace(
        "Adrian TITIENI</a>", "Actor DE TEST</a>")
    site.overrides["/spectacol/macbeth/"] = modified

    stats = run(test_db, site)
    assert stats["shows_updated"] == 1 and stats["shows_inserted"] == 0
    row = q(test_db, "SELECT * FROM shows WHERE slug='macbeth'")[0]
    assert row["id"] == show_id  # același rând, actualizat
    assert row["duration_text"] == "2h 20′" and row["duration_minutes"] == 140
    assert {"name": "Actor DE TEST", "character": "Duncan"} in json.loads(row["cast_json"])


def test_rescheduled_and_vanished_performances(test_db, poster_dir, tmp_path):
    site = FakeSite()
    run(test_db, site)
    macbeth_perf = q(test_db, "SELECT id FROM performances WHERE external_id='perf-1792411148534-9gho'")[0]["id"]

    # DATE DE TEST: Macbeth mutat de joi 3 dec. pe vineri 4 dec.; Delirium scos din program
    soup = BeautifulSoup(PROGRAM.read_text(encoding="utf-8"), "lxml")
    card = soup.select_one('[data-perf-id="perf-1792411148534-9gho"]')
    card.select_one(".tsp-day-num").string = "4"
    card.select_one(".tsp-day-short").string = "vin"
    soup.select_one('[data-perf-id="perf-1792411170210-wkgo"]').decompose()
    changed = tmp_path / "program_test_modificat.html"
    changed.write_text(str(soup), encoding="utf-8")

    stats = run(test_db, site, schedule_file=changed, now=datetime(2026, 11, 22, 11, 0))
    assert stats["performances_updated"] == 1
    assert stats["performances_marked_missing"] == 1
    moved = q(test_db, "SELECT * FROM performances WHERE external_id='perf-1792411148534-9gho'")[0]
    assert moved["id"] == macbeth_perf and moved["start_at"] == datetime(2026, 12, 4, 17, 0)
    gone = q(test_db, "SELECT status FROM performances WHERE external_id='perf-1792411170210-wkgo'")
    assert gone[0]["status"] == "disparut"  # păstrată în baza de date, doar marcată
    assert q(test_db, "SELECT COUNT(*) n FROM performances")[0]["n"] == 23


def test_failed_schedule_collection_changes_nothing(test_db, poster_dir, tmp_path):
    site = FakeSite()
    run(test_db, site)
    before = q(test_db, "SELECT id, status, start_at FROM performances ORDER BY id")
    stats = run(test_db, site, schedule_file=tmp_path / "nu-exista.html", now=datetime(2026, 11, 22, 11, 0))
    assert stats["performances_marked_missing"] == 0
    assert q(test_db, "SELECT id, status, start_at FROM performances ORDER BY id") == before

    # program randat, dar gol -> tot eșec, nu ștergem / marcăm nimic
    empty = tmp_path / "program_gol.html"
    empty.write_text('<div class="tsp-header">0 reprezentații programate</div>', encoding="utf-8")
    run(test_db, site, schedule_file=empty, now=datetime(2026, 11, 22, 11, 0))
    assert q(test_db, "SELECT id, status, start_at FROM performances ORDER BY id") == before


def test_missing_fields_and_failed_poster_download(test_db, poster_dir):
    site = FakeSite()
    site.overrides["/wp-content/uploads/2023/04/svejk-afis-1024x1024.jpg"] = httpx.Response(404)
    stats = run(test_db, site)
    assert stats["posters_failed"] == 1
    svejk = q(test_db, "SELECT * FROM shows WHERE slug='svejk'")[0]
    assert svejk["poster_path"] is None and svejk["title"] == "Svejk"  # spectacolul e salvat oricum
    clasic = q(test_db, "SELECT * FROM shows WHERE slug='clasic-e-fantastic'")[0]
    for col in ("author", "director", "description", "duration_minutes", "poster_path", "cast_json"):
        assert clasic[col] is None, col
