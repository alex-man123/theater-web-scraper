"""Configurare comună pentru teste.

tests/fixtures/snapshots/  = copii REALE ale paginilor teatrul-odeon.ro, salvate pe
                             22.11.2026, ca testele să ruleze fără rețea.
Datele modificate controlat (pentru a simula schimbări pe site) sunt create în
cod, în testele respective, și sunt marcate explicit "DATE DE TEST".
"""
import os
from datetime import datetime
from pathlib import Path

import pymysql
import pytest

from odeon import config

FIXTURES = Path(__file__).parent / "fixtures" / "snapshots"
# Momentul de referință al snapshot-urilor (UTC): 22.11.2026, 12:00 ora României.
SNAPSHOT_NOW = datetime(2026, 11, 22, 10, 0, 0)
TEST_DB = os.getenv("DB_TEST_NAME", "theater_crawler_test")


def snapshot(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def test_db():
    """Bază de date de test, golită și recreată pentru fiecare test. Sare testul dacă MySQL lipsește."""
    try:
        conn = pymysql.connect(host=config.DB_HOST, port=config.DB_PORT, user=config.DB_USER,
                               password=config.DB_PASSWORD, database=TEST_DB, charset="utf8mb4",
                               connect_timeout=3)
    except pymysql.MySQLError as exc:
        pytest.skip(f"baza de test {TEST_DB} nu este disponibilă: {exc}")
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS performances")
        cur.execute("DROP TABLE IF EXISTS shows")
    conn.commit()
    conn.close()
    from odeon import db
    conn = db.connect(TEST_DB)
    db.init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def poster_dir(tmp_path, monkeypatch):
    d = tmp_path / "posters"
    monkeypatch.setattr(config, "POSTER_DIR", d)
    return d
