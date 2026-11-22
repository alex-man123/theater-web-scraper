"""Configurarea aplicației, citită din variabile de mediu (fișierul .env).

Nicio parolă nu este scrisă în cod: valorile reale stau în .env, care nu se
publică. Vezi .env.example pentru lista completă a variabilelor.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


# --- Baza de date ---------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = _int("DB_PORT", 3307)
DB_USER = os.getenv("DB_USER", "odeon_app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "theater_crawler")

# --- Sursa ----------------------------------------------------------------
BASE_URL = "https://teatrul-odeon.ro"
SEASON_URL = f"{BASE_URL}/stagiune/"
SCHEDULE_URL = f"{BASE_URL}/programul-teatrului-odeon-pe-zile/"
SOURCE_TIMEZONE = "Europe/Bucharest"  # orele din program sunt ora locală a teatrului

# --- Comportamentul crawlerului -------------------------------------------
_contact = os.getenv("CRAWLER_CONTACT", "").strip()
USER_AGENT = "OdeonStudentCrawler/1.0 (proiect educational Tehnologii Web" + (
    f"; contact: {_contact})" if _contact else ")"
)
REQUEST_DELAY = _float("CRAWLER_REQUEST_DELAY", 2.0)  # secunde între cereri
REQUEST_TIMEOUT = _float("CRAWLER_TIMEOUT", 20.0)
MAX_RETRIES = _int("CRAWLER_MAX_RETRIES", 3)
MAX_RETRY_AFTER = _float("CRAWLER_MAX_RETRY_AFTER", 120.0)  # nu așteptăm la nesfârșit
MAX_CONSECUTIVE_FAILURES = _int("CRAWLER_MAX_CONSECUTIVE_FAILURES", 5)
MAX_POSTER_BYTES = 10 * 1024 * 1024

# --- Stocare locală -------------------------------------------------------
POSTER_DIR = Path(os.getenv("POSTER_DIR", PROJECT_ROOT / "storage" / "posters"))
