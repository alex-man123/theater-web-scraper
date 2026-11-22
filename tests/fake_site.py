"""Un "site Odeon" simulat pentru teste, construit din snapshot-urile reale.

Servește robots.txt, /stagiune/, paginile /spectacol/<slug>/ pentru care avem
snapshot și afișe FALSE (octeți generați – DATE DE TEST, nu imaginile reale).
Orice altă adresă răspunde 404. Testele pot suprascrie răspunsuri prin `overrides`.
"""
from __future__ import annotations

import httpx

from odeon.crawler.http import PoliteClient

from .conftest import FIXTURES


class FakeSite:
    def __init__(self):
        self.overrides: dict[str, httpx.Response | str] = {}
        self.requests: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.requests.append(path)
        if path in self.overrides:
            o = self.overrides[path]
            return o if isinstance(o, httpx.Response) else httpx.Response(200, text=o)
        if path == "/robots.txt":
            return httpx.Response(200, text="user-agent: *\nAllow: /\n")
        if path == "/stagiune/":
            return httpx.Response(200, text=(FIXTURES / "stagiune.html").read_text(encoding="utf-8"))
        if path.startswith("/spectacol/"):
            f = FIXTURES / (path.strip("/").split("/")[-1] + ".html")
            if f.exists():
                return httpx.Response(200, text=f.read_text(encoding="utf-8"))
        if path.startswith("/wp-content/uploads/"):
            # DATE DE TEST: "imagine" falsă, diferită pentru fiecare URL
            return httpx.Response(200, content=b"\x89PNG\r\n\x1a\n" + path.encode(),
                                  headers={"Content-Type": "image/png"})
        return httpx.Response(404)

    def client(self) -> PoliteClient:
        return PoliteClient(client=httpx.Client(transport=httpx.MockTransport(self.handler)),
                            delay=0.0, max_retries=1, sleep=lambda s: None)

    def poster_requests(self) -> list[str]:
        return [p for p in self.requests if p.startswith("/wp-content/uploads/")]
