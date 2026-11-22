# Cerințe și stadiul verificării

Surse: **P** = `docs/Proiecte_Crawlere_Teatre (1).pdf`, **C** = `docs/Crawlere_si_scrapere_web (1).pdf`,
**E** = cerințele suplimentare ale echipei (enunțul de lucru).
Tip: **O** = obligatoriu, **R** = recomandat, **Op** = opțional.

Stare: ✅ verificat (test automat și/sau verificare practică, indicată) · ⚠️ parțial (vezi observația) · ➖ nu se aplică / neimplementat intenționat.
Verificările au fost rulate pe 22.11.2026 (63 de teste pytest trecute; 9 rulări reale ale crawlerului).

## Arhitectură și date

| # | Cerință | Sursă | Tip | Componentă | Verificare | Stare |
|---|---|---|---|---|---|---|
| A1 | O singură instituție (Teatrul Odeon) | P p.1–2 | O | `config.py` | toate URL-urile sunt pe teatrul-odeon.ro | ✅ |
| A2 | Crawler + bază de date locală + frontend | P p.1 | O | `crawler/`, `db.py`, `web/` | rulări reale + `test_web.py` | ✅ |
| A3 | Frontendul afișează exclusiv date din baza locală | P p.4 | O | `web/__init__.py` | `test_web.py` blochează orice conexiune non-localhost; capturi Playwright: 0 cereri externe | ✅ |
| A4 | Încărcarea paginilor nu declanșează colectarea | E | O | `web/` nu importă crawlerul | inspecție cod + testul de rețea blocată | ✅ |
| A5 | Distincție spectacol / reprezentație, FK | P p.4–7 | O | `db/schema.sql` (`fk_performances_show`) | `test_pipeline_db.py` | ✅ |

## Crawler

| # | Cerință | Sursă | Tip | Componentă | Verificare | Stare |
|---|---|---|---|---|---|---|
| K1 | Identificarea automată a paginilor spectacolelor | P p.6 | O | `discover_show_urls` | `test_discovery_finds_unique_show_urls`; real: 39 pagini | ✅ |
| K2 | Identificarea programului și a reprezentațiilor | P p.6 | O | `render.py`, `parse_schedule.py` | 23/23 carduri (snapshot + real) | ✅ |
| K3 | Asocierea reprezentațiilor cu spectacolul corect | P p.6 | O | `match_show`, `save_performances` | `test_match_show_*`, pipeline; real: 23/23 verificate manual | ✅ |
| K4 | Descărcarea și stocarea locală a afișelor | P p.4, p.6 | O | `posters.py` | pipeline + `test_show_detail_page`; real: 37 afișe | ✅ |
| K5 | Normalizarea datelor și orelor | P p.6 | O | `normalize.py` | `test_normalize.py` | ✅ |
| K6 | Fus orar explicit | E | O | `local_to_utc` / `utc_to_local` | test vară/iarnă; `/schedule` afișează `+02:00` | ✅ |
| K7 | Eliminarea marcajelor HTML din texte | P p.6 | O | `clean_text`, `_block_text` | `test_description_is_plain_text…`, `test_no_html…` | ✅ |
| K8 | Păstrarea diacriticelor | E | O | NFC, utf8mb4 | `test_clean_text…`, „Ioana MĂRCOIU” în DB | ✅ |
| K9 | Distribuția și echipa în JSON (`name`/`character`, `role`/`name`) | P p.4–6 | O | `parse_people` | 11 teste pe formate reale + audit pe toate cele 38 de spectacole | ⚠️ 1 pagină (*Puseu de iubire*) are doar text liber → liste goale; 2 rânduri păstrate cu `role: null` |
| K10 | Roluri neplafonate la o listă prestabilită | P p.5 | O | rolul păstrat textual | ex. „Regia, coregrafia, costumele” | ✅ |
| K11 | Câmpuri spectacol: titlu, descriere, durată, vârstă, limbă, distribuție, echipă, afiș, URL | P p.4 | O (dacă există) | `parse_show_page` | teste + statistici reale (36/38 durată, 36/38 vârstă, 37/38 afiș, 34/38 descriere) | ✅ |
| K12 | Autor și regizor | E (P p.5 frontend) | O (dacă există) | `author_from_credit`, echipa | `test_author_from_credit_line_variants`; real: 27/38 autor, 30/38 regizor | ⚠️ NULL când creditul e ambiguu |
| K13 | Limbă | P p.4 | O (dacă există) | `_parse_sidebar` | Macbeth | ⚠️ site-ul publică doar mențiuni de traducere/supratitrare |
| K14 | Reprezentație: spectacol, dată, oră | P p.4 | O | `parse_schedule_html` | teste | ✅ |
| K15 | Sală, tip, stare, alte informații (dacă există) | P p.4 | O (dacă există) | `venue`, `performance_type`, `status`, `notes` | `test_rescheduled_status_and_missing_venue` | ✅ |
| K16 | Ora de final | P p.4 | O (dacă există) | `end_at` | nepublicată pe site → NULL | ➖ |
| K17 | URL sursă spectacol și, când există, reprezentație | P p.6 | O | `source_url` | pipeline | ✅ (reprezentațiile nu au URL propriu: pagina de program + `external_id`) |
| K18 | Fără duplicate la rulări repetate | P p.4, p.6 | O | `upsert_*`, `find_performance`, `dedupe_shows` | `test_second_run…`, `test_dedupe.py`; real: rulări repetate cu 0 inserări | ✅ |
| K19 | Actualizarea datelor modificate pe sursă | P p.4, p.6 | O | `upsert_show` (detectează câmpurile schimbate) | `test_changed_source_updates_existing_record`; real: jurnal „spectacol actualizat … (câmpuri)” | ✅ |
| K20 | Reprogramări și reprezentații dispărute | E | O | `external_id`, `mark_missing_performances` | `test_rescheduled_and_vanished_performances` | ✅ |
| K21 | Nu se șterge nimic la o colectare eșuată | E | O | `run.crawl` | `test_failed_schedule_collection_changes_nothing` | ✅ |
| K22 | Gestionarea erorilor HTTP și a paginilor indisponibile | P p.6 | O | `http.py` | `test_http.py` (404, 429, 5xx, timeout) | ✅ |
| K23 | robots.txt verificat înainte de colectare | P p.6, C p.3 | O | Protego în `http.py` | `test_robots_disallow_is_respected`; real: `Allow: /` | ✅ |
| K24 | Ritm rezonabil, timeout-uri, reîncercări limitate, Retry-After | C p.3, E | O | `http.py` | `test_http.py` | ✅ |
| K25 | Fără ocolirea autentificării/CAPTCHA/restricțiilor | C p.4, E | O | `render.py` (fără falsificarea antetelor) | inspecție cod | ✅ |
| K26 | Câmp lipsă → necompletat, fără valori inventate | C p.2, p.4 | O | toate parserele | `test_missing_fields_*`, `test_unstructured_credits…` | ✅ |
| K27 | Loguri utile (pagini, adăugări/actualizări, erori) | E | O | `run.py`, `logs/crawler.log` | rezumat la fiecare rulare | ✅ |
| K28 | Fără bilete, prețuri, rezervări | P p.6 | — | prețurile din carduri sunt ignorate | inspecție cod | ✅ |
| K29 | Verificarea existenței unui API înainte de crawling | C p.1 | R | — | API-ul widget-ului există, dar e restricționat la domeniu → neutilizat | ✅ (analizat) |

## Bază de date și afișe

| # | Cerință | Sursă | Tip | Componentă | Verificare | Stare |
|---|---|---|---|---|---|---|
| D1 | Tabelele `shows` și `performances`, MySQL 8 | P p.4, p.6–7 | O | `db/schema.sql` | containerul `mysql:8.0` + `init_db` în teste | ✅ |
| D2 | Câmpurile utile din schema PDF păstrate | P p.6–7 | O | `schema.sql` | toate coloanele PDF prezente | ✅ |
| D3 | `cast_json` / `team_json` de tip JSON | P p.4 | O | `schema.sql` | pipeline | ✅ |
| D4 | Script SQL de inițializare | P p.6, E | O | `db/schema.sql`, `python -m odeon.db init`, Docker | testele recreează schema la fiecare test | ✅ |
| D5 | Deduplicare reprezentații după spectacol, dată/oră, locație (+ URL sursă) | P p.7 | O | `find_performance` | pipeline | ✅ (URL-ul per reprezentație nu există; folosim `external_id`) |
| D6 | Afiș ca fișier + cale în DB (varianta recomandată) | P p.4 | R | `posters.py` | pipeline, captură | ✅ |
| D7 | URL original al afișului păstrat | P p.4 | R | `poster_source_url` | pipeline | ✅ |
| D8 | SHA-256 pentru detectarea schimbărilor | P p.4 | Op | `poster_hash`, `--refresh-posters` | pipeline | ✅ |
| D9 | Afiș lipsă → NULL + substitut vizual local | P p.4, E | O | `poster-placeholder.svg` | `test_show_without_upcoming…`, `test_missing_fields_and_failed_poster_download` | ✅ |
| D10 | Fără redescărcări inutile | E | O | `needs_download` | `test_second_run…` (0 cereri pentru afișe) | ✅ |
| D11 | Stocare Base64 | P p.4 | Op (alternativă) | — | neimplementată, se folosește varianta recomandată | ➖ |

## Interfața web

| # | Cerință | Sursă | Tip | Componentă | Verificare | Stare |
|---|---|---|---|---|---|---|
| W1 | Rute în engleză: `/`, `/shows`, `/shows/{id}`, `/schedule` | P p.5 | O | `web/__init__.py` | `test_web.py` | ✅ |
| W2 | `/`: spectacole și reprezentații viitoare | P p.5 | O | `index.html` | `test_home…`, captură | ✅ |
| W3 | `/shows`: afiș, titlu, autor, regizor, următoarea reprezentație | P p.5 | O | `shows.html`, `list_shows` | `test_shows_list_and_search` | ✅ |
| W4 | `/shows/{id}`: toate câmpurile cerute | P p.5 | O | `show_detail.html` | `test_show_detail_page` | ✅ |
| W5 | `/schedule`: dată, oră, spectacol, sală, ordonare cronologică | P p.5 | O | `schedule.html` | `test_schedule_is_chronological` | ✅ |
| W6 | Căutare după titlu | P p.6 | O | `LIKE` parametrizat | `test_shows_list_and_search` | ✅ |
| W7 | Desktop și mobil | P p.6 | O | `style.css` (mobile-first) | capturi la 1280 px și 390 px, fără scroll orizontal | ✅ |
| W8 | Lipsa rezultatelor, spectacole fără reprezentații, câmpuri lipsă, afișe indisponibile, 404 | E | O | template-uri, handler 404 | `test_web.py` | ✅ |
| W9 | Afișarea sigură a textelor colectate | E | O | autoescape Jinja | `test_collected_text_is_escaped` | ✅ |
| W10 | Filtre (lună, sală, autor, …) | P p.6 | Op | filtru după sală în `/schedule` | `test_schedule_is_chronological` | ✅ (doar sală) |

## Calitate și documentație

| # | Cerință | Sursă | Tip | Componentă | Stare |
|---|---|---|---|---|---|
| Q1 | Separarea colectare / parsare / DB / afișare | E | O | structura `odeon/` | ✅ |
| Q2 | `.env.example` fără credențiale, fără parole în cod | E | O | `config.py`, `.env.example`, `.gitignore` | ✅ |
| Q3 | Interogări parametrizate | E | O | `db.py` | ✅ |
| Q4 | README, CLAUDE.md, REQUIREMENTS.md, PROMPTURI_SPRIJIN_AI.md | E | O | rădăcina proiectului | ✅ |

## Diferențe între enunț și PDF-uri

- PDF-ul nu cere explicit **autor** și **regizor** în lista de colectare a spectacolelor (p.4), dar le afișează pe
  `/shows` și `/shows/{id}` (p.5); enunțul le cere. Le colectăm când pot fi identificate fără ambiguitate.
- PDF-ul păstrează **TIMESTAMP** pentru `start_at`; l-am păstrat, cu stocare în UTC și conversie explicită la afișare.
- PDF-ul cere deduplicarea „în logica aplicației”; am făcut-o în cod și am adăugat constrângeri UNIQUE ca plasă de siguranță.
- Enunțul cere URL sursă per reprezentație „când există”; site-ul nu publică unul, deci folosim pagina de program
  ca `source_url` și `external_id` ca identificator stabil.

## Ce nu a fost verificat

- Comportamentul real la un răspuns **429/5xx** de la teatrul-odeon.ro (nu a apărut niciunul); acoperit doar de teste simulate.
- O **schimbare reală** de conținut pe site între rulări: actualizarea a fost verificată cu date de test și prin
  reparsarea paginilor după îmbunătățirea parserului, nu printr-o modificare făcută de teatru.
- Afișarea pe dispozitive fizice și în alte browsere decât Chromium (doar emulare Playwright la 390 px).
- Varianta B de instalare (MySQL existent, fără Docker) — scriptul e furnizat, dar nu a fost rulată pe serverul MySQL80 local (lipsea parola root).
