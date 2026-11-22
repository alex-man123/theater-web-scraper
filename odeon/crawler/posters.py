"""Descărcarea afișelor ca fișiere locale (varianta recomandată în PDF).

* calea relativă (ex. "posters/macbeth-1a2b3c4d5e6f.jpg") se salvează în shows.poster_path;
* URL-ul original rămâne în shows.poster_source_url;
* hash-ul SHA-256 (opțional în PDF) ne spune dacă imaginea s-a schimbat.

Evităm redescărcările: dacă URL-ul afișului nu s-a schimbat și fișierul local
există, nu mai facem nicio cerere. Dacă descărcarea eșuează, păstrăm afișul vechi.
"""
from __future__ import annotations

import hashlib
import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from odeon import config

from .http import PoliteClient

log = logging.getLogger("crawler.posters")

ALLOWED_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}


@dataclass
class PosterFile:
    path: str          # relativ la storage/, ex. "posters/x.jpg"
    mime_type: str
    sha256: str
    source_url: str


def local_file(relative_path: str | None) -> Path | None:
    if not relative_path:
        return None
    return config.POSTER_DIR.parent / relative_path


def needs_download(source_url: str | None, existing: dict | None) -> bool:
    if not source_url:
        return False
    if not existing or existing.get("poster_source_url") != source_url:
        return True
    f = local_file(existing.get("poster_path"))
    return f is None or not f.exists()


def download_poster(client: PoliteClient, source_url: str, slug: str) -> PosterFile | None:
    result = client.get(source_url)
    if result is None:
        log.warning("afiș indisponibil: %s", source_url)
        return None
    mime = (result.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_TYPES:
        guessed = mimetypes.guess_type(source_url)[0]
        if guessed in ALLOWED_TYPES and mime in ("", "application/octet-stream"):
            mime = guessed
        else:
            log.warning("afișul nu este o imagine (%s): %s", mime, source_url)
            return None
    if not result.content or len(result.content) > config.MAX_POSTER_BYTES:
        log.warning("afiș gol sau prea mare (%d octeți): %s", len(result.content), source_url)
        return None

    digest = hashlib.sha256(result.content).hexdigest()
    filename = f"{slug}-{digest[:12]}{ALLOWED_TYPES[mime]}"
    config.POSTER_DIR.mkdir(parents=True, exist_ok=True)
    target = config.POSTER_DIR / filename
    if not target.exists():
        tmp = target.with_suffix(target.suffix + ".part")
        tmp.write_bytes(result.content)
        tmp.replace(target)  # scriere atomică: nu rămân fișiere pe jumătate
    return PosterFile(f"posters/{filename}", mime, digest, source_url)
