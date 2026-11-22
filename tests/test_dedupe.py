from collections import Counter
from datetime import date

from odeon.crawler.parse_show import ShowData
from odeon.crawler.run import dedupe_shows


def show(slug, title, premiere):
    return ShowData(source_url=f"https://teatrul-odeon.ro/spectacol/{slug}/", slug=slug,
                    title=title, premiere_date=premiere)


def test_same_show_published_at_two_urls_is_kept_once():
    # caz real observat pe site: /spectacol/nijinsky/ și /spectacol/nijinski-agonie-si-extaz/
    stats = Counter()
    result = dedupe_shows([
        show("nijinsky", "Nijinski • Agonie și Extaz", date(2025, 4, 11)),
        show("nijinski-agonie-si-extaz", "Nijinski • Agonie și Extaz", date(2025, 4, 11)),
        show("macbeth", "Macbeth", date(2025, 9, 26)),
    ], stats)
    assert [s.slug for s in result] == ["nijinski-agonie-si-extaz", "macbeth"]
    assert stats["show_pages_duplicate"] == 1


def test_same_title_different_premiere_are_different_productions():
    result = dedupe_shows([show("a", "Hamlet", date(2001, 1, 1)), show("b", "Hamlet", date(2020, 1, 1))], Counter())
    assert len(result) == 2
