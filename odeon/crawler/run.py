"""Punctul de intrare al crawlerului:  python -m odeon.crawler.run

Etape:
  1. crawling: /stagiune/ -> lista URL-urilor /spectacol/<slug>/
  2. scraping: fiecare pagină de spectacol -> ShowData
  3. programul: randare Playwright -> carduri -> PerformanceData
  4. salvare spectacole (+ descărcarea afișelor) în MySQL
  5. asocierea reprezentațiilor cu spectacolele și salvarea lor
  6. dacă programul a fost colectat cu succes: marcăm reprezentațiile viitoare dispărute

O eroare la o pagină nu oprește colectarea; erorile repetate o suspendă (CrawlAborted).
Nimic nu se șterge din baza de date din cauza unei colectări eșuate.
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from odeon import config, db

from .http import CrawlAborted, PoliteClient
from .normalize import now_utc, slugify, title_key, utc_to_local
from .parse_schedule import PerformanceData, announced_count, match_show, parse_schedule_html
from .parse_show import ShowData, author_from_credit, director_from_credit, discover_show_urls, parse_show_page
from .posters import download_poster, needs_download
from .render import RenderError, render_schedule

log = logging.getLogger("crawler")


def scrape_shows(client: PoliteClient, stats: Counter, limit: int | None = None) -> list[ShowData]:
    season = client.get(config.SEASON_URL)
    if season is None:
        log.error("pagina de repertoriu %s nu a putut fi descărcată", config.SEASON_URL)
        stats["errors"] += 1
        return []
    urls = discover_show_urls(season.text, config.BASE_URL)
    log.info("descoperite %d pagini de spectacol în %s", len(urls), config.SEASON_URL)
    shows = []
    for url in urls[:limit] if limit else urls:
        show = scrape_one(client, url, stats)
        if show:
            shows.append(show)
    return shows


def scrape_one(client: PoliteClient, url: str, stats: Counter) -> ShowData | None:
    page = client.get(url)
    stats["show_pages_requested"] += 1
    if page is None:
        stats["show_pages_failed"] += 1
        return None
    try:
        show = parse_show_page(page.text, url)
    except Exception:  # o pagină neobișnuită nu trebuie să oprească tot crawlerul
        log.exception("eroare la parsarea %s", url)
        stats["errors"] += 1
        return None
    if show is None:
        log.warning("pagina nu pare a fi un spectacol: %s", url)
        return None
    log.info("spectacol procesat: %s | distribuție %d | echipă %d | afiș %s",
             show.title, len(show.cast), len(show.team), "da" if show.poster_source_url else "nu")
    return show


def dedupe_shows(shows: list[ShowData], stats: Counter) -> list[ShowData]:
    """Același spectacol poate fi publicat la două adrese (ex. /spectacol/nijinsky/ și
    /spectacol/nijinski-agonie-si-extaz/, cu conținut identic). Le considerăm aceeași
    producție dacă au același titlu și aceeași dată a premierei; păstrăm pagina al cărei
    slug corespunde titlului (altfel prima găsită)."""
    groups: dict[tuple, list[ShowData]] = {}
    for s in shows:
        groups.setdefault((title_key(s.title), s.premiere_date), []).append(s)
    result = []
    for (key, _premiere), group in groups.items():
        if len(group) == 1:
            result.append(group[0])
            continue
        keep = next((s for s in group if s.slug == slugify(s.title)), group[0])
        for s in group:
            if s is not keep:
                log.info("pagină duplicată ignorată: %s (același spectacol ca %s)", s.source_url, keep.source_url)
                stats["show_pages_duplicate"] += 1
        result.append(keep)
    return result


def collect_schedule(schedule_file: Path | None, stats: Counter, reference: date) -> list[PerformanceData] | None:
    """Returnează reprezentațiile sau None dacă programul NU a putut fi colectat."""
    try:
        html = schedule_file.read_text(encoding="utf-8") if schedule_file else render_schedule()
    except (RenderError, OSError) as exc:
        log.error("programul nu a putut fi colectat: %s", exc)
        stats["errors"] += 1
        return None
    perfs, problems = parse_schedule_html(html, reference)
    for p in problems:
        log.warning("program: %s", p)
    expected = announced_count(html)
    log.info("program: %d reprezentații extrase (anunțate: %s)", len(perfs), expected)
    if expected is not None and expected != len(perfs):
        log.warning("numărul extras (%d) diferă de cel anunțat (%d)", len(perfs), expected)
    if not perfs:
        log.error("programul nu conține reprezentații – tratăm colectarea ca eșuată")
        return None
    return perfs


def save_show(conn, client: PoliteClient | None, show: ShowData, seen_at, stats: Counter,
              refresh_posters: bool = False) -> int:
    existing = db.get_show_by_slug(conn, show.slug)
    poster = None
    if client and (refresh_posters or needs_download(show.poster_source_url, existing)):
        pf = download_poster(client, show.poster_source_url, show.slug)
        if pf:
            stats["posters_downloaded"] += 1
            poster = {"poster_storage": "file", "poster_path": pf.path, "poster_mime_type": pf.mime_type,
                      "poster_source_url": pf.source_url, "poster_hash": pf.sha256}
        else:
            stats["posters_failed"] += 1
    result, show_id = db.upsert_show(conn, db.show_row(show), poster, seen_at)
    conn.commit()
    stats[f"shows_{result}"] += 1
    return show_id


def schedule_only_show(perf: PerformanceData) -> ShowData:
    """Titlu din program fără pagină de spectacol: păstrăm doar ce publică programul."""
    return ShowData(
        source_url=config.SCHEDULE_URL, slug="program-" + slugify(perf.source_title),
        title=perf.source_title, subtitle=perf.subtitle,
        author=author_from_credit(perf.subtitle), director=director_from_credit(perf.subtitle),
        age_recommendation=perf.age_label, origin="schedule",
    )


def crawl(conn, client: PoliteClient | None, *, limit: int | None = None, skip_schedule: bool = False,
          schedule_file: Path | None = None, refresh_posters: bool = False,
          now: datetime | None = None) -> Counter:
    """`now` (UTC) se poate fixa în teste; implicit este momentul curent."""
    stats: Counter = Counter()
    run_started = now or now_utc()

    shows = dedupe_shows(scrape_shows(client, stats, limit) if client else [], stats)
    perfs = None if skip_schedule else collect_schedule(schedule_file, stats, utc_to_local(run_started).date())

    # Vârsta lipsește din unele pagini de spectacol, dar apare în program ("14+").
    by_key = {title_key(s.title): i for i, s in enumerate(shows)}
    for perf in perfs or []:
        idx = match_show(perf.source_title, by_key)
        if idx is not None and shows[idx].age_recommendation is None and perf.age_label:
            shows[idx].age_recommendation = perf.age_label

    for show in shows:
        save_show(conn, client, show, run_started, stats, refresh_posters)

    if perfs is not None:
        save_performances(conn, client, perfs, run_started, stats)
        missing = db.mark_missing_performances(conn, run_started)
        conn.commit()
        stats["performances_marked_missing"] += missing
        if missing:
            log.info("%d reprezentații viitoare nu mai apar în program (marcate 'disparut')", missing)
    else:
        log.warning("programul nu a fost actualizat; reprezentațiile existente rămân neschimbate")
    return stats


def save_performances(conn, client, perfs: list[PerformanceData], seen_at, stats: Counter) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT id, title, origin FROM shows")
        rows = cur.fetchall()
    page_shows = {title_key(r["title"]): r["id"] for r in rows if r["origin"] == "show_page"}
    sched_shows = {title_key(r["title"]): r["id"] for r in rows if r["origin"] == "schedule"}

    for perf in perfs:
        show_id = match_show(perf.source_title, page_shows)
        known_schedule_only = title_key(perf.source_title) in sched_shows
        if show_id is None and client is not None and not known_schedule_only:
            # Poate există o pagină de spectacol care nu apare în /stagiune/.
            guess = f"{config.BASE_URL}/spectacol/{slugify(perf.source_title)}/"
            if guess not in client.visited:
                show = scrape_one(client, guess, stats)
                if show:
                    show_id = save_show(conn, client, show, seen_at, stats)
                    page_shows[title_key(show.title)] = show_id
                    show_id = match_show(perf.source_title, page_shows)
        if show_id is None:
            show_id = sched_shows.get(title_key(perf.source_title))
        if show_id is None:
            log.warning("titlu din program fără pagină de spectacol: %r -> salvat doar din program",
                        perf.source_title)
            show_id = save_show(conn, None, schedule_only_show(perf), seen_at, stats)
            sched_shows[title_key(perf.source_title)] = show_id
        result = db.upsert_performance(conn, {
            "show_id": show_id, "external_id": perf.external_id, "source_title": perf.source_title,
            "start_at": perf.start_at_utc, "end_at": None, "venue": perf.venue,
            "performance_type": perf.performance_type, "status": perf.status,
            "notes": perf.notes, "source_url": config.SCHEDULE_URL,
        }, seen_at)
        conn.commit()
        stats[f"performances_{result}"] += 1


def setup_logging(verbose: bool) -> None:
    log_dir = config.PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    handlers = [logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_dir / "crawler.log", encoding="utf-8")]
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", handlers=handlers)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Crawler pentru repertoriul și programul Teatrului Odeon")
    ap.add_argument("--limit", type=int, help="procesează doar primele N spectacole (pentru probe)")
    ap.add_argument("--skip-schedule", action="store_true", help="nu colecta programul")
    ap.add_argument("--schedule-file", type=Path,
                    help="parsează un HTML de program salvat anterior în loc să randezi pagina")
    ap.add_argument("--refresh-posters", action="store_true",
                    help="redescarcă afișele și compară hash-ul chiar dacă URL-ul nu s-a schimbat")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    setup_logging(args.verbose)

    client = PoliteClient()
    log.info("pornire colectare (User-Agent: %s, pauză %.1fs)", config.USER_AGENT, client.delay)
    try:
        with db.connect() as conn:
            stats = crawl(conn, client, limit=args.limit, skip_schedule=args.skip_schedule,
                          schedule_file=args.schedule_file, refresh_posters=args.refresh_posters)
    except CrawlAborted as exc:
        log.error("COLECTARE SUSPENDATĂ: %s", exc)
        return 2
    finally:
        client.close()
    stats.update({f"http_{k}": v for k, v in client.stats.items()})
    log.info("REZUMAT: %s", ", ".join(f"{k}={v}" for k, v in sorted(stats.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
