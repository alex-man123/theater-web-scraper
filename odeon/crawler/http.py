"""Client HTTP politicos: robots.txt, ritm limitat, reîncercări limitate, Retry-After.

Reguli (conform PDF-ului "Crawlere și scrapere web", secțiunea 3):
  * citim robots.txt înainte de prima cerere către un host (parser: Protego);
  * cel puțin REQUEST_DELAY secunde între două cereri către același host;
  * 429 / 5xx / timeout -> reîncercăm de cel mult MAX_RETRIES ori, cu pauză crescătoare;
  * Retry-After este respectat; dacă cere o pauză mai mare decât MAX_RETRY_AFTER, renunțăm;
  * 404 / 410 -> pagina nu există, nu reîncercăm;
  * după MAX_CONSECUTIVE_FAILURES eșecuri la rând oprim colectarea (CrawlAborted).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx
from protego import Protego

from odeon import config

log = logging.getLogger("crawler.http")

RETRYABLE = {429, 500, 502, 503, 504}


class CrawlAborted(RuntimeError):
    """Prea multe erori consecutive: suspendăm colectarea și verificăm cauza."""


@dataclass
class FetchResult:
    url: str
    status: int
    content: bytes
    headers: httpx.Headers

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


def parse_retry_after(value: str | None, now: datetime | None = None) -> float | None:
    """Retry-After poate fi un număr de secunde sau o dată HTTP."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    now = now or datetime.now(timezone.utc)
    return max(0.0, (when - now).total_seconds())


class PoliteClient:
    def __init__(self, client: httpx.Client | None = None, delay: float | None = None,
                 max_retries: int | None = None, sleep=time.sleep, clock=time.monotonic):
        self.client = client or httpx.Client(
            headers={"User-Agent": config.USER_AGENT, "Accept-Language": "ro,en;q=0.5"},
            timeout=config.REQUEST_TIMEOUT,
            follow_redirects=True,
        )
        self.delay = config.REQUEST_DELAY if delay is None else delay
        self.max_retries = config.MAX_RETRIES if max_retries is None else max_retries
        self._sleep = sleep
        self._clock = clock
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, Protego | None] = {}
        self.visited: set[str] = set()  # evidența adreselor deja cerute în această rulare
        self.consecutive_failures = 0
        self.stats = {"requests": 0, "ok": 0, "not_found": 0, "failed": 0, "blocked_by_robots": 0}

    # --- robots.txt ------------------------------------------------------
    def _load_robots(self, host_url: str) -> Protego | None:
        robots_url = f"{host_url}/robots.txt"
        try:
            self._wait_turn(host_url)
            resp = self.client.get(robots_url)
            self.stats["requests"] += 1
        except httpx.HTTPError as exc:
            log.warning("robots.txt indisponibil (%s): %s -> nu colectăm de pe acest host", robots_url, exc)
            return Protego.parse("User-agent: *\nDisallow: /")
        if resp.status_code >= 500:
            # RFC 9309: eroare de server -> considerăm totul interzis
            log.warning("robots.txt a răspuns %s -> nu colectăm de pe acest host", resp.status_code)
            return Protego.parse("User-agent: *\nDisallow: /")
        if resp.status_code >= 400:
            # RFC 9309: robots.txt inexistent (4xx) -> nu există restricții publicate
            log.info("robots.txt lipsește (%s) pentru %s", resp.status_code, host_url)
            return None
        log.info("robots.txt citit de la %s", robots_url)
        return Protego.parse(resp.text)

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host_url = f"{parts.scheme}://{parts.netloc}"
        if host_url not in self._robots:
            self._robots[host_url] = self._load_robots(host_url)
        rules = self._robots[host_url]
        return True if rules is None else rules.can_fetch(url, config.USER_AGENT)

    def crawl_delay(self, url: str) -> float:
        parts = urlsplit(url)
        rules = self._robots.get(f"{parts.scheme}://{parts.netloc}")
        published = rules.crawl_delay(config.USER_AGENT) if rules else None
        return max(self.delay, float(published or 0))

    # --- ritmul cererilor -------------------------------------------------
    def _wait_turn(self, url: str) -> None:
        host = urlsplit(url).netloc
        last = self._last_request.get(host)
        if last is not None:
            wait = self.crawl_delay(url) - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_request[host] = self._clock()

    # --- cererea propriu-zisă ----------------------------------------------
    def get(self, url: str) -> FetchResult | None:
        """Descarcă URL-ul. Returnează None pentru 404/410, robots sau erori persistente."""
        self.visited.add(url)
        if not self.allowed(url):
            log.warning("interzis de robots.txt, sărit: %s", url)
            self.stats["blocked_by_robots"] += 1
            return None

        for attempt in range(1, self.max_retries + 2):  # 1 încercare + max_retries reîncercări
            self._wait_turn(url)
            self.stats["requests"] += 1
            try:
                resp = self.client.get(url)
            except httpx.HTTPError as exc:
                reason, wait = f"{type(exc).__name__}: {exc}", None
            else:
                if resp.status_code < 400:
                    self.consecutive_failures = 0
                    self.stats["ok"] += 1
                    return FetchResult(str(resp.url), resp.status_code, resp.content, resp.headers)
                if resp.status_code in (404, 410):
                    log.warning("pagina nu există (%s): %s", resp.status_code, url)
                    self.stats["not_found"] += 1
                    self.consecutive_failures = 0
                    return None
                if resp.status_code not in RETRYABLE:
                    log.error("HTTP %s, nu reîncercăm: %s", resp.status_code, url)
                    return self._fail(url)
                reason = f"HTTP {resp.status_code}"
                wait = parse_retry_after(resp.headers.get("Retry-After"))
                if wait is not None and wait > config.MAX_RETRY_AFTER:
                    log.error("Retry-After=%ss depășește limita de %ss, renunțăm la %s",
                              int(wait), int(config.MAX_RETRY_AFTER), url)
                    return self._fail(url)

            if attempt > self.max_retries:
                break
            backoff = self.crawl_delay(url) * (2 ** attempt)
            pause = max(backoff, wait or 0)
            log.warning("%s pentru %s; reîncercarea %d/%d peste %.0fs",
                        reason, url, attempt, self.max_retries, pause)
            self._sleep(pause)
        log.error("renunțăm după %d încercări: %s", self.max_retries + 1, url)
        return self._fail(url)

    def _fail(self, url: str) -> None:
        self.stats["failed"] += 1
        self.consecutive_failures += 1
        if self.consecutive_failures >= config.MAX_CONSECUTIVE_FAILURES:
            raise CrawlAborted(
                f"{self.consecutive_failures} erori consecutive (ultima: {url}); colectarea este suspendată"
            )
        return None

    def close(self) -> None:
        self.client.close()
