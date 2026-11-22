"""Randarea paginii de program cu un browser automatizat (Playwright).

De ce e nevoie de browser: programul Odeon este afișat de un widget JavaScript
al unui furnizor extern. Cheia API a widget-ului este restricționată la domeniul
teatrului (o cerere directă primește "Cheia API nu este permisă pe acest domeniu").
Nu ocolim restricția falsificând antete; deschidem pagina oficială a teatrului
exact ca un vizitator și citim HTML-ul pe care îl produce widget-ul.

Pentru a încărca serverele cât mai puțin, blocăm imaginile, fonturile și media.
"""
from __future__ import annotations

import logging

from odeon import config

log = logging.getLogger("crawler.render")

CONTAINER = "#program-spectacole-container"


class RenderError(RuntimeError):
    pass


def render_schedule(url: str = config.SCHEDULE_URL, timeout_ms: int = 45000) -> str:
    """Returnează HTML-ul interior al containerului de program după execuția JavaScript."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(user_agent=config.USER_AGENT, locale="ro-RO",
                                        timezone_id=config.SOURCE_TIMEZONE)
                page.route("**/*", lambda route: route.abort()
                           if route.request.resource_type in {"image", "font", "media"}
                           else route.continue_())
                response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                if response is None or response.status >= 400:
                    raise RenderError(f"pagina de program a răspuns {response.status if response else '?'}")
                # Așteptăm fie cardurile, fie antetul widget-ului (care apare și când nu sunt reprezentații).
                page.wait_for_selector(f"{CONTAINER} .tsp-card, {CONTAINER} .tsp-header",
                                       timeout=timeout_ms)
                page.wait_for_timeout(1500)  # lăsăm animațiile/inserările să se termine
                html = page.inner_html(CONTAINER)
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise RenderError(f"randarea programului a eșuat: {exc}") from exc
    log.info("program randat: %d caractere HTML", len(html))
    return html
