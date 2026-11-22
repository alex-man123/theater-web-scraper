"""Gestionarea erorilor HTTP, fără rețea: httpx.MockTransport simulează serverul."""
import httpx
import pytest

from odeon import config
from odeon.crawler.http import CrawlAborted, PoliteClient, parse_retry_after


def make_client(handler, sleeps, max_retries=2):
    transport = httpx.MockTransport(handler)
    return PoliteClient(client=httpx.Client(transport=transport), delay=0.0,
                        max_retries=max_retries, sleep=sleeps.append)


def robots_ok(request):
    return httpx.Response(200, text="User-agent: *\nAllow: /\n")


def test_404_returns_none_without_retry():
    calls = []

    def handler(req):
        if req.url.path == "/robots.txt":
            return robots_ok(req)
        calls.append(req.url.path)
        return httpx.Response(404)

    c = make_client(handler, [])
    assert c.get("https://example.test/lipsa/") is None
    assert calls == ["/lipsa/"]
    assert c.stats["not_found"] == 1


def test_429_respects_retry_after_then_succeeds():
    sleeps, responses = [], iter([httpx.Response(429, headers={"Retry-After": "7"}),
                                  httpx.Response(200, text="ok")])

    def handler(req):
        return robots_ok(req) if req.url.path == "/robots.txt" else next(responses)

    c = make_client(handler, sleeps)
    result = c.get("https://example.test/pagina/")
    assert result is not None and result.text == "ok"
    assert max(sleeps) >= 7  # a așteptat cel puțin cât a cerut serverul


def test_too_long_retry_after_gives_up(monkeypatch):
    monkeypatch.setattr(config, "MAX_RETRY_AFTER", 60)

    def handler(req):
        return robots_ok(req) if req.url.path == "/robots.txt" else httpx.Response(503, headers={"Retry-After": "3600"})

    sleeps = []
    c = make_client(handler, sleeps)
    assert c.get("https://example.test/x/") is None
    assert all(s < 3600 for s in sleeps)


def test_5xx_retries_are_limited():
    calls = []

    def handler(req):
        if req.url.path == "/robots.txt":
            return robots_ok(req)
        calls.append(1)
        return httpx.Response(500)

    c = make_client(handler, [], max_retries=2)
    assert c.get("https://example.test/x/") is None
    assert len(calls) == 3  # 1 încercare + 2 reîncercări, apoi renunță


def test_timeout_is_retried_then_reported():
    def handler(req):
        if req.url.path == "/robots.txt":
            return robots_ok(req)
        raise httpx.ReadTimeout("timeout", request=req)

    c = make_client(handler, [], max_retries=1)
    assert c.get("https://example.test/x/") is None
    assert c.stats["failed"] == 1


def test_robots_disallow_is_respected():
    calls = []

    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /privat/\n")
        calls.append(req.url.path)
        return httpx.Response(200, text="ok")

    c = make_client(handler, [])
    assert c.get("https://example.test/privat/pagina") is None
    assert c.get("https://example.test/public") is not None
    assert calls == ["/public"]


def test_repeated_failures_abort_crawl(monkeypatch):
    monkeypatch.setattr(config, "MAX_CONSECUTIVE_FAILURES", 3)

    def handler(req):
        return robots_ok(req) if req.url.path == "/robots.txt" else httpx.Response(500)

    c = make_client(handler, [], max_retries=0)
    c.get("https://example.test/1")
    c.get("https://example.test/2")
    with pytest.raises(CrawlAborted):
        c.get("https://example.test/3")


def test_delay_between_requests():
    sleeps = []
    clock = iter(range(0, 1000)).__next__  # fiecare apel avansează ceasul cu 1s

    def handler(req):
        return httpx.Response(200, text="User-agent: *\nAllow: /\n")

    c = PoliteClient(client=httpx.Client(transport=httpx.MockTransport(handler)), delay=5.0,
                     sleep=sleeps.append, clock=clock)
    c.get("https://example.test/a")
    c.get("https://example.test/b")
    assert sleeps and all(s > 0 for s in sleeps)


def test_parse_retry_after_formats():
    assert parse_retry_after("120") == 120
    assert parse_retry_after(None) is None
    assert parse_retry_after("Wed, 21 Oct 2099 07:28:00 GMT") > 0
