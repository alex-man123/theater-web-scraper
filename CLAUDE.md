# CLAUDE.md — context pentru asistentul AI

## Proiectul
Crawler + bază de date + interfață web pentru repertoriul și programul **Teatrului Odeon** (https://teatrul-odeon.ro/),
proiect de Tehnologii Web. Cerințele oficiale sunt în `docs/*.pdf`; corespondența cerință → componentă → verificare
este în `REQUIREMENTS.md`. Documentația pentru utilizatori este în `README.md`.

## Arhitectura
- `odeon/crawler/http.py` — client HTTP politicos (Protego/robots.txt, pauză de 2 s, reîncercări limitate, Retry-After, suspendare după erori repetate).
- `odeon/crawler/parse_show.py` — descoperă `/spectacol/<slug>/` din `/stagiune/` și extrage datele spectacolului. Funcții pure.
- `odeon/crawler/render.py` — Playwright, **doar** pentru `/programul-teatrului-odeon-pe-zile/` (widget JavaScript).
- `odeon/crawler/parse_schedule.py` — cardurile `.tsp-card` → reprezentații; `match_show` după titlu normalizat.
- `odeon/crawler/normalize.py` — text, date românești, durate, deducerea anului, UTC ↔ Europe/Bucharest.
- `odeon/crawler/posters.py` — afișe ca fișiere în `storage/posters/` + SHA-256.
- `odeon/crawler/run.py` — orchestrare și jurnal (`logs/crawler.log`).
- `odeon/db.py` — PyMySQL; upsert-uri cu detectarea modificărilor, interogări pentru web.
- `odeon/web/` — Flask + Jinja2; rutele `/`, `/shows`, `/shows/<id>`, `/schedule`, `/posters/<f>`.
- `db/schema.sql` — schema MySQL din PDF + `slug`, `subtitle`, `origin`, `external_id`, `source_title`.

## Comenzi (Windows PowerShell, din rădăcina proiectului)
```powershell
docker compose up -d                                  # MySQL 8 pe portul 3307 (odeon-mysql)
.\.venv\Scripts\python.exe -m odeon.db init           # creează tabelele (MySQL existent)
.\.venv\Scripts\python.exe -m odeon.crawler.run       # colectare (~2 min)
.\.venv\Scripts\python.exe -m odeon.web               # http://127.0.0.1:5000
.\.venv\Scripts\python.exe -m pytest                  # 63 de teste; cele de DB folosesc theater_crawler_test
```
Setați `PYTHONIOENCODING=utf-8` dacă apar erori de codare în consolă.

## Reguli importante
- **Nu inventa date.** Un câmp nepublicat rămâne NULL. Nu folosi date demonstrative în locul colectării reale.
- **Nu ocoli restricțiile de acces.** API-ul widget-ului de program (projects.doimih.net) refuză cererile din afara
  domeniului teatrului; nu falsifica `Referer`/`Origin`. Programul se citește randând pagina oficială cu Playwright.
- Respectă `robots.txt` și pauza dintre cereri; nu porni cereri paralele către site.
- **Aplicația web citește numai din baza de date** și nu importă / nu apelează crawlerul.
- Orele se stochează în UTC (`TIMESTAMP`, sesiune `time_zone='+00:00'`) și se afișează în Europe/Bucharest.
- Nu șterge înregistrări din cauza unei colectări eșuate; reprezentațiile viitoare dispărute primesc `status='disparut'`.
- Interogări SQL doar parametrizate (`%s`); textul colectat se afișează prin escaping-ul automat Jinja (fără `|safe`).
- Înainte de a schimba selectorii, inspectează pagina reală și adaugă snapshot-ul în `tests/fixtures/snapshots/`
  împreună cu un test. Datele modificate controlat în teste se marchează `DATE DE TEST`.
- La rescrierea fișierelor cu diacritice din PowerShell 5.1 folosește `-Encoding utf8`
  (`Get-Content`/`Set-Content` implicit strică diacriticele).
- După modificarea template-urilor, repornește serverul Flask (fără debug, template-urile sunt păstrate în cache).
