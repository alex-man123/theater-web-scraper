"""Accesul la baza de date MySQL (PyMySQL, interogări parametrizate).

Crawlerul scrie prin upsert_show / upsert_performance / mark_missing_performances;
aplicația web doar citește prin funcțiile din secțiunea "Citire".

Rulare:  python -m odeon.db init     -> creează tabelele din db/schema.sql
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime

import pymysql
from pymysql.cursors import DictCursor

from odeon import config

log = logging.getLogger("db")

SCHEMA_FILE = config.PROJECT_ROOT / "db" / "schema.sql"

# Coloanele din shows pe care crawlerul le actualizează din pagina sursă.
SHOW_FIELDS = [
    "origin", "title", "subtitle", "author", "director", "description", "genre", "language",
    "duration_minutes", "duration_text", "age_recommendation", "premiere_date",
    "cast_json", "team_json", "source_url",
]
POSTER_FIELDS = ["poster_storage", "poster_path", "poster_mime_type", "poster_source_url", "poster_hash"]
PERF_FIELDS = ["show_id", "external_id", "source_title", "start_at", "end_at", "venue",
               "performance_type", "status", "notes", "source_url"]


def connect(database: str | None = None):
    conn = pymysql.connect(
        host=config.DB_HOST, port=config.DB_PORT, user=config.DB_USER,
        password=config.DB_PASSWORD, database=database or config.DB_NAME,
        charset="utf8mb4", cursorclass=DictCursor, autocommit=False,
        init_command="SET time_zone = '+00:00'",  # TIMESTAMP-urile sunt stocate/citite în UTC
    )
    return conn


def init_db(conn) -> None:
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    statements = [s.strip() for s in sql.split(";") if s.strip() and not _only_comments(s)]
    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
    conn.commit()


def _only_comments(chunk: str) -> bool:
    return all(not ln.strip() or ln.strip().startswith("--") for ln in chunk.splitlines())


# ---------------------------------------------------------------------------
# Scriere (crawler)
# ---------------------------------------------------------------------------
def _json_or_none(items: list | None) -> str | None:
    return json.dumps(items, ensure_ascii=False) if items else None


def _same(old, new) -> bool:
    """Compară o valoare din DB cu cea nouă (JSON comparat ca structură, nu ca text)."""
    if isinstance(new, str) and isinstance(old, str) and new[:1] in "[{" and old[:1] in "[{":
        try:
            return json.loads(old) == json.loads(new)
        except ValueError:
            pass
    if isinstance(old, datetime) and isinstance(new, datetime):
        return old.replace(microsecond=0) == new.replace(microsecond=0)
    return old == new


def show_row(show) -> dict:
    """ShowData -> dicționar cu coloanele tabelului shows."""
    return {
        "slug": show.slug, "origin": getattr(show, "origin", "show_page"),
        "title": show.title, "subtitle": show.subtitle, "author": show.author,
        "director": show.director, "description": show.description, "genre": show.genre,
        "language": show.language, "duration_minutes": show.duration_minutes,
        "duration_text": show.duration_text, "age_recommendation": show.age_recommendation,
        "premiere_date": show.premiere_date, "cast_json": _json_or_none(show.cast),
        "team_json": _json_or_none(show.team), "source_url": show.source_url,
    }


def get_show_by_slug(conn, slug: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM shows WHERE slug = %s", (slug,))
        return cur.fetchone()


def upsert_show(conn, row: dict, poster: dict | None, seen_at: datetime) -> tuple[str, int]:
    """Inserează sau actualizează un spectacol identificat prin slug.

    Returnează ("inserted" | "updated" | "unchanged", id). updated_at se schimbă
    doar când se modifică efectiv datele, nu la fiecare rulare.
    """
    existing = get_show_by_slug(conn, row["slug"])
    values = {k: row[k] for k in SHOW_FIELDS}
    if poster:  # afișul se actualizează doar dacă avem unul nou descărcat cu succes
        values.update(poster)
    with conn.cursor() as cur:
        if existing is None:
            cols = ["slug", *values.keys(), "last_seen_at"]
            cur.execute(
                f"INSERT INTO shows ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
                [row["slug"], *values.values(), seen_at],
            )
            return "inserted", cur.lastrowid
        changed = {k: v for k, v in values.items() if not _same(existing.get(k), v)}
        if changed:
            sets = ", ".join(f"{k} = %s" for k in changed)
            cur.execute(f"UPDATE shows SET {sets}, last_seen_at = %s WHERE id = %s",
                        [*changed.values(), seen_at, existing["id"]])
            log.info("spectacol actualizat: %s (%s)", row["slug"], ", ".join(changed))
            return "updated", existing["id"]
        # Doar marcăm că l-am văzut. "updated_at = updated_at" împiedică MySQL să
        # schimbe automat updated_at (ON UPDATE) când nu s-a modificat nimic real.
        cur.execute("UPDATE shows SET last_seen_at = %s, updated_at = updated_at WHERE id = %s",
                    (seen_at, existing["id"]))
        return "unchanged", existing["id"]


def find_performance(conn, external_id: str | None, show_id: int, start_at: datetime,
                     venue: str | None) -> dict | None:
    """Deduplicare: întâi după id-ul din sursă, apoi după (spectacol, dată/oră, sală)."""
    with conn.cursor() as cur:
        if external_id:
            cur.execute("SELECT * FROM performances WHERE external_id = %s", (external_id,))
            row = cur.fetchone()
            if row:
                return row
        cur.execute(
            "SELECT * FROM performances WHERE show_id = %s AND start_at = %s AND venue <=> %s "
            "ORDER BY id LIMIT 1",
            (show_id, start_at, venue),
        )
        return cur.fetchone()


def upsert_performance(conn, row: dict, seen_at: datetime) -> str:
    existing = find_performance(conn, row.get("external_id"), row["show_id"], row["start_at"], row.get("venue"))
    values = {k: row.get(k) for k in PERF_FIELDS}
    with conn.cursor() as cur:
        if existing is None:
            cols = [*values.keys(), "last_seen_at"]
            cur.execute(
                f"INSERT INTO performances ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
                [*values.values(), seen_at],
            )
            return "inserted"
        changed = {k: v for k, v in values.items() if not _same(existing.get(k), v)}
        if changed:
            if "start_at" in changed:
                log.info("reprezentație reprogramată: %s %s -> %s",
                         row.get("source_title"), existing["start_at"], row["start_at"])
            sets = ", ".join(f"{k} = %s" for k in changed)
            cur.execute(f"UPDATE performances SET {sets}, last_seen_at = %s WHERE id = %s",
                        [*changed.values(), seen_at, existing["id"]])
            return "updated"
        cur.execute("UPDATE performances SET last_seen_at = %s, updated_at = updated_at WHERE id = %s",
                    (seen_at, existing["id"]))
        return "unchanged"


def mark_missing_performances(conn, run_started: datetime) -> int:
    """Reprezentațiile VIITOARE care nu au mai apărut în programul colectat acum
    sunt marcate 'disparut' (nu se șterg). Se apelează DOAR după o colectare reușită.
    Dacă reapar ulterior, upsert_performance le readuce starea din sursă."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE performances SET status = 'disparut' "
            "WHERE start_at >= %s AND (last_seen_at IS NULL OR last_seen_at < %s) "
            "AND (status IS NULL OR status <> 'disparut')",
            (run_started, run_started),
        )
        return cur.rowcount


# ---------------------------------------------------------------------------
# Citire (aplicația web) – doar date din baza locală
# ---------------------------------------------------------------------------
VISIBLE = "p.status IS NULL OR p.status <> 'disparut'"


def _decode_show(row: dict | None) -> dict | None:
    if row is None:
        return None
    for key in ("cast_json", "team_json"):
        row[key] = json.loads(row[key]) if row.get(key) else []
    return row


def list_shows(conn, now: datetime, query: str | None = None) -> list[dict]:
    """Toate spectacolele + următoarea reprezentație. Căutare după titlu (LIKE parametrizat)."""
    sql = f"""
        SELECT s.id, s.title, s.subtitle, s.author, s.director, s.poster_path, s.origin,
               (SELECT MIN(p.start_at) FROM performances p
                 WHERE p.show_id = s.id AND p.start_at >= %s AND ({VISIBLE})) AS next_start_at
        FROM shows s
    """
    params: list = [now]
    if query:
        sql += " WHERE s.title LIKE %s"
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params.append(f"%{escaped}%")
    sql += " ORDER BY next_start_at IS NULL, next_start_at, s.title"
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def get_show(conn, show_id: int) -> dict | None:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM shows WHERE id = %s", (show_id,))
        return _decode_show(cur.fetchone())


def upcoming_performances(conn, now: datetime, show_id: int | None = None,
                          limit: int | None = None, venue: str | None = None) -> list[dict]:
    """Reprezentațiile viitoare, în ordine cronologică (ORDER BY start_at)."""
    sql = f"""
        SELECT p.*, s.title AS show_title, s.poster_path
        FROM performances p JOIN shows s ON s.id = p.show_id
        WHERE p.start_at >= %s AND ({VISIBLE})
    """
    params: list = [now]
    if show_id is not None:
        sql += " AND p.show_id = %s"
        params.append(show_id)
    if venue:
        sql += " AND p.venue = %s"
        params.append(venue)
    sql += " ORDER BY p.start_at, s.title"
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def venues(conn, now: datetime) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(f"SELECT DISTINCT p.venue FROM performances p WHERE p.venue IS NOT NULL "
                    f"AND p.start_at >= %s AND ({VISIBLE}) ORDER BY p.venue", (now,))
        return [r["venue"] for r in cur.fetchall()]


def counts(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT (SELECT COUNT(*) FROM shows) AS shows, "
                    "(SELECT COUNT(*) FROM performances) AS performances, "
                    "(SELECT MAX(last_seen_at) FROM performances) AS last_crawl")
        return cur.fetchone()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if len(sys.argv) >= 2 and sys.argv[1] == "init":
        with connect() as c:
            init_db(c)
        print(f"Tabelele au fost create în baza '{config.DB_NAME}'.")
    else:
        print("Utilizare: python -m odeon.db init")
