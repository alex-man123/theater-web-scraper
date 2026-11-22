# Teatrul Odeon — crawler, bază de date și interfață web

Proiect pentru disciplina **Tehnologii Web** (proiectul nr. 3 din `docs/Proiecte_Crawlere_Teatre (1).pdf`).

Aplicația colectează automat **repertoriul** (spectacolele) și **programul** (reprezentațiile)
Teatrului Odeon de pe <https://teatrul-odeon.ro/>, le salvează într-o bază de date MySQL locală,
descarcă afișele ca fișiere locale și le afișează într-o interfață web responsive.

- **spectacol** (`shows`) = producția teatrală (ex. *Macbeth*), cu autor, regie, distribuție, echipă, afiș;
- **reprezentație** (`performances`) = o desfășurare a spectacolului la o dată și oră (ex. *Macbeth*, joi 3 decembrie 2026, 19:00, Sala Majestic).

Interfața citește **numai** din baza de date locală. Deschiderea paginilor nu pornește colectarea
și nu face nicio cerere către site-ul teatrului.

---

## Tehnologii

| Rol | Tehnologie | De ce |
|---|---|---|
| Limbaj | Python 3.12 | recomandat în PDF „pentru început”, ușor de citit |
| Descărcare pagini și afișe | **HTTPX** | recomandat în PDF; timeout-uri, redirecționări |
| Parsare HTML | **Beautiful Soup** + lxml | recomandat în PDF; selectori CSS |
| robots.txt | **Protego** | recomandat în PDF; interpretează corect Allow/Disallow |
| Pagina de program (JavaScript) | **Playwright** (Chromium) | PDF: „când informațiile apar numai după JavaScript” |
| Bază de date | **MySQL 8** (Docker) + PyMySQL | schema din PDF, interogări parametrizate |
| Web | **Flask** + Jinja2 | pagini generate pe server, escaping automat, fără build JS |
| Teste | **pytest** | |

Nu folosim Scrapy/Crawlee: site-ul are ~40 de pagini, iar un client propriu de ~150 de rânduri
(`odeon/crawler/http.py`) este mai ușor de explicat decât un framework.

---

## Structura proiectului

```
Odeon/
├── odeon/
│   ├── config.py              # configurare din .env (fără parole în cod)
│   ├── db.py                  # acces MySQL: upsert-uri (crawler) + interogări (web)
│   ├── crawler/
│   │   ├── http.py            # client politicos: robots.txt, pauze, reîncercări, Retry-After
│   │   ├── render.py          # Playwright: randează pagina de program
│   │   ├── parse_show.py      # scraper pagină spectacol + descoperirea URL-urilor
│   │   ├── parse_schedule.py  # scraper program + asocierea cu spectacolele
│   │   ├── normalize.py       # text, date, ore, durate, fus orar (funcții pure)
│   │   ├── posters.py         # descărcarea afișelor ca fișiere locale (SHA-256)
│   │   └── run.py             # orchestrare: python -m odeon.crawler.run
│   └── web/
│       ├── __init__.py        # aplicația Flask și rutele
│       ├── templates/         # base, index, shows, show_detail, schedule, 404
│       └── static/            # CSS responsive + afiș substitut (SVG)
├── db/
│   ├── schema.sql             # schema MySQL (pornită din PDF, adaptată)
│   └── docker-test-db.sql     # creează baza separată pentru teste
├── storage/posters/           # afișele descărcate (create de crawler)
├── tests/                     # 63 de teste pytest
│   └── fixtures/snapshots/    # copii REALE ale paginilor Odeon (22.11.2026)
├── docs/                      # PDF-urile cu cerințele
├── logs/crawler.log           # jurnalul crawlerului (creat la rulare)
├── docker-compose.yml         # MySQL 8 pe portul 3307
├── requirements.txt
├── .env.example
├── REQUIREMENTS.md            # cerințe -> componentă -> verificare
├── CLAUDE.md                  # context pentru asistentul AI
└── PROMPTURI_SPRIJIN_AI.md    # exemple de prompturi de sprijin AI
```

---

## Instalare

Cerințe: **Python 3.12**, **Docker Desktop** (sau un server MySQL 8 existent), Git (opțional).

Comenzile sunt pentru Windows PowerShell; pe Linux/macOS înlocuiți `.\.venv\Scripts\` cu `.venv/bin/`.

```powershell
# 1. mediul virtual și dependențele
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium

# 2. variabilele de mediu
Copy-Item .env.example .env
# editați .env și schimbați DB_PASSWORD și MYSQL_ROOT_PASSWORD
```

### Variabilele de mediu (`.env`)

| Variabilă | Implicit | Rol |
|---|---|---|
| `DB_HOST`, `DB_PORT` | `127.0.0.1`, `3307` | serverul MySQL |
| `DB_NAME` | `theater_crawler` | baza aplicației |
| `DB_USER`, `DB_PASSWORD` | `odeon_app`, — | utilizatorul aplicației |
| `MYSQL_ROOT_PASSWORD` | — | folosit doar de Docker la crearea containerului |
| `DB_TEST_NAME` | `theater_crawler_test` | baza folosită de teste (golită la fiecare test) |
| `CRAWLER_REQUEST_DELAY` | `2.0` | secunde minime între două cereri către același site |
| `CRAWLER_TIMEOUT` | `20` | timeout pe cerere (secunde) |
| `CRAWLER_MAX_RETRIES` | `3` | reîncercări pentru 429 / 5xx / timeout |
| `CRAWLER_MAX_RETRY_AFTER` | `120` | dacă serverul cere o pauză mai lungă, renunțăm la acea pagină |
| `CRAWLER_MAX_CONSECUTIVE_FAILURES` | `5` | după atâtea erori la rând, colectarea se suspendă |
| `CRAWLER_CONTACT` | gol | contact opțional adăugat în User-Agent |
| `WEB_HOST`, `WEB_PORT` | `127.0.0.1`, `5000` | adresa aplicației web |

### Baza de date

**Varianta A — Docker (folosită la dezvoltare):**

```powershell
docker compose up -d
```

La prima pornire, containerul `odeon-mysql` creează baza `theater_crawler`, utilizatorul din `.env`,
rulează `db/schema.sql` și creează baza de test `theater_crawler_test`.

**Varianta B — un MySQL 8 existent:**

```sql
CREATE DATABASE theater_crawler CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE theater_crawler_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'odeon_app'@'localhost' IDENTIFIED BY 'parola-din-env';
GRANT ALL PRIVILEGES ON theater_crawler.* TO 'odeon_app'@'localhost';
GRANT ALL PRIVILEGES ON theater_crawler_test.* TO 'odeon_app'@'localhost';
```

apoi setați `DB_PORT=3306` în `.env` și creați tabelele:

```powershell
.\.venv\Scripts\python.exe -m odeon.db init
```

---

## Rulare

```powershell
# colectarea (durează ~2 minute din cauza pauzei de 2 s între cereri)
.\.venv\Scripts\python.exe -m odeon.crawler.run

# opțiuni utile
.\.venv\Scripts\python.exe -m odeon.crawler.run --limit 5          # doar primele 5 spectacole
.\.venv\Scripts\python.exe -m odeon.crawler.run --skip-schedule    # fără program (fără Playwright)
.\.venv\Scripts\python.exe -m odeon.crawler.run --refresh-posters  # reverifică afișele prin hash
.\.venv\Scripts\python.exe -m odeon.crawler.run --schedule-file tests\fixtures\snapshots\program_rendered.html

# aplicația web -> http://127.0.0.1:5000
.\.venv\Scripts\python.exe -m odeon.web

# testele (MySQL trebuie să ruleze pentru testele de integrare)
.\.venv\Scripts\python.exe -m pytest
```

La final, crawlerul scrie un rezumat, de exemplu:

```
REZUMAT: http_failed=0, http_ok=40, performances_unchanged=23, show_pages_duplicate=1,
         show_pages_requested=39, shows_unchanged=36, shows_updated=2
```

### Rutele aplicației

| Rută | Conținut |
|---|---|
| `/` | spectacole + următoarele reprezentații + căutare |
| `/shows` | toate spectacolele: afiș local, titlu, autor, regizor, următoarea reprezentație |
| `/shows?q=mac` | căutare după titlu |
| `/shows/{id}` | afiș, titlu, autor/regie, descriere, durată, vârstă, distribuție, echipă, reprezentații viitoare |
| `/schedule` | program cronologic, grupat pe zile: dată, oră, spectacol, sală (filtru opțional după sală) |
| `/posters/{fișier}` | afișele din `storage/posters/` |

ID-urile inexistente (`/shows/999999`, `/shows/abc`) și orice altă adresă primesc pagina 404.

---

## Arhitectura și fluxul datelor

```
           teatrul-odeon.ro                                    (doar crawlerul accesează site-ul)
   ┌──────────────┬──────────────────────┬───────────────────────────────┐
   │ robots.txt   │ /stagiune/           │ /programul-teatrului-odeon-pe-zile/
   │              │ /spectacol/<slug>/   │ (program generat de JavaScript)
   │              │ /wp-content/...jpg   │
   ▼              ▼                      ▼
 http.py ──► parse_show.py         render.py (Playwright) ──► parse_schedule.py
 (Protego,    discover_show_urls       │                          │
  pauze,      parse_show_page          │                          │ match_show (titlu normalizat)
  reîncercări)       │                 │                          │
   │          posters.py (fișiere + SHA-256)                      │
   ▼                 ▼                                            ▼
                         run.py  ──►  db.py (upsert, deduplicare)  ──►  MySQL: shows, performances
                                                                         storage/posters/*.jpg
                                                                              │
                                                     odeon/web (Flask) ◄──────┘  (numai citire)
                                                              │
                                                         browser (desktop / mobil)
```

1. **Crawling** — `/stagiune/` → toate legăturile `/spectacol/<slug>/` (39 de pagini la 22.11.2026).
2. **Scraping spectacole** — titlu, linia de credit, autor, regizor, descriere, durată, vârstă, limbă/traducere,
   data premierei, distribuție (`cast_json`), echipă (`team_json`), URL-ul afișului.
3. **Programul** — pagina de program conține doar un container gol; cardurile sunt create de un widget
   JavaScript al unui furnizor extern. Cheia API a widget-ului este restricționată la domeniul teatrului
   (o cerere directă primește „Cheia API nu este permisă pe acest domeniu”). **Nu ocolim restricția**
   falsificând antete; deschidem pagina oficială cu Playwright, ca un vizitator, și citim HTML-ul rezultat.
   Imaginile și fonturile sunt blocate în browser ca să nu încărcăm inutil serverele.
4. **Asocierea** reprezentație → spectacol: cardurile nu au link către spectacol, deci comparăm titlurile
   normalizate (fără diacritice/punctuație): exact sau prefix la graniță de cuvânt
   („Soldatul de ciocolată” → „Soldatul de ciocolată (sau Armele și omul)”,
   „Clasic e Fantastic - Copilăria lui Beethoven” → „Clasic e fantastic”).
   Un titlu fără pagină de spectacol (ex. „Tur ghidat”) devine un spectacol cu `origin='schedule'`,
   care conține doar ce publică programul.
5. **Salvarea** în MySQL și descărcarea afișelor.

### Date, ore și fus orar

- Programul publică „dum 22 nov.” — **fără an**. Anul se deduce astfel încât ziua săptămânii publicată
  să se potrivească (`infer_year`), alegând data cea mai apropiată de momentul colectării.
- Orele publicate sunt ora României (`Europe/Bucharest`). Le convertim în **UTC** înainte de salvare
  (coloanele `TIMESTAMP`, conexiunea setează `time_zone='+00:00'`) și înapoi în ora României la afișare.
  Astfel orele rămân corecte și la trecerea la ora de vară/iarnă (testat în `test_normalize.py`).
- Data premierei („26 septembrie 2025”) → `DATE`; durata „2h 10′” → `duration_text` (textual) + `duration_minutes = 130`.

### Distribuția și echipa ca JSON

```json
cast_json: [{"name": "Ioana MĂRCOIU", "character": "Lady Macbeth"}, {"name": "Eduard Trifa"}]
team_json: [{"role": "Muzica originală", "name": "Nicola Ratti"}, {"role": "Light design", "name": "Marco Giusti"}]
```

Rolurile sunt păstrate exact cum le publică teatrul (nu există listă prestabilită). Site-ul folosește
cel puțin nouă formate diferite (`Personaj: Actor`, `Personaj – Actor`, `Actor – Personaj`, `PERSONAJ / Actor`,
`<em>Rol</em><br>Nume`, `<strong>Rol</strong> Nume`, `Rol <strong>Nume</strong>`, rânduri în `<div>`, blocuri fără tab).
Parserul le distinge folosind marcajul HTML (îngroșare, legăturile `/om/` către profilurile actorilor),
nu doar textul. Fiecare format este acoperit de un test pe pagina reală corespunzătoare.

---

## Deduplicare și actualizare

| Situație | Ce face crawlerul |
|---|---|
| Spectacol nou | `INSERT`; identificat prin `slug` (UNIQUE) |
| Spectacol existent, date identice | doar `last_seen_at`; **`updated_at` nu se schimbă** |
| Spectacol existent, date modificate pe site | `UPDATE` numai dacă un câmp diferă; jurnalul arată ce câmpuri s-au schimbat |
| Același spectacol la două URL-uri (`/nijinsky/` și `/nijinski-agonie-si-extaz/`) | păstrat o singură dată (același titlu + aceeași premieră) |
| Reprezentație | căutată întâi după `external_id` (id-ul stabil al cardului, `data-perf-id`), apoi după **(spectacol, dată/oră, sală)** |
| Reprezentație reprogramată (același `external_id`, altă oră) | `UPDATE start_at` pe același rând |
| Reprezentație viitoare care nu mai apare în program | **nu se șterge**: `status='disparut'`; nu mai este afișată; dacă reapare, își recapătă starea |
| Colectarea programului eșuează sau întoarce 0 carduri | nu se modifică/marchează nicio reprezentație |
| Pagina unui spectacol nu poate fi descărcată | spectacolul rămâne neschimbat în baza de date |
| Afiș | descărcat doar dacă URL-ul s-a schimbat sau fișierul lipsește; dacă descărcarea eșuează, se păstrează afișul vechi |

Rularea repetată nu creează duplicate (verificat prin teste și prin rulări repetate pe site-ul real:
la a doua rulare `shows_inserted=0`, `performances_inserted=0`, 0 afișe redescărcate).
Constrângerile `UNIQUE` (`shows.slug`, `performances.external_id`) sunt o plasă de siguranță în plus;
deduplicarea propriu-zisă este în logica aplicației, cum cere PDF-ul.

### Adaptări ale schemei din PDF

Toate câmpurile din PDF sunt păstrate. Am adăugat:

- `shows.slug` (UNIQUE) — identificatorul din URL; `source_url` (2048 caractere) este prea lung pentru un index UNIQUE în utf8mb4;
- `shows.subtitle` — linia de credit exact cum e publicată („de A. P. Cehov, regia Andrei și Andreea Grosu”);
- `shows.origin` — `show_page` sau `schedule` (titlu care apare doar în program);
- `performances.external_id` — id-ul cardului din program, pentru deduplicare și reprogramări;
- `performances.source_title` — titlul exact din program (poate diferi de titlul spectacolului).

Varianta de stocare a afișului este **fișier** (`poster_storage='file'`), cea recomandată în PDF;
coloana `poster_base64` rămâne în schemă, nefolosită.

---

## Comportament „politicos” față de site

- `robots.txt` citit înainte de prima cerere (Odeon: `Allow: /`); adresele interzise sunt sărite;
  dacă robots.txt răspunde 5xx, nu colectăm nimic (RFC 9309);
- User-Agent clar: `OdeonStudentCrawler/1.0 (proiect educational Tehnologii Web)` (+ contact opțional);
- cel puțin 2 secunde între cereri; o singură cerere simultană;
- 429/5xx/timeout: maximum 3 reîncercări cu pauză crescătoare; `Retry-After` respectat, dar plafonat la 120 s;
- 404/410: pagină indisponibilă, fără reîncercări;
- 5 erori consecutive → colectarea se oprește (`CrawlAborted`);
- nu se colectează prețuri, bilete sau disponibilitatea locurilor.

---

## Teste și verificări

```powershell
.\.venv\Scripts\python.exe -m pytest
```

| Fișier | Ce verifică |
|---|---|
| `test_normalize.py` | date românești, durate, ore, deducerea anului, UTC ↔ Europe/Bucharest (vară/iarnă), diacritice |
| `test_parse_show.py` | valori extrase din 20 de pagini reale salvate, toate formatele de distribuție/echipă, câmpuri lipsă |
| `test_parse_schedule.py` | 23/23 carduri, câmpuri, fus orar, „Reprogramat”, sală lipsă, asocierea titlurilor |
| `test_http.py` | 404, 429 + Retry-After, Retry-After prea mare, 5xx limitat, timeout, robots.txt, suspendare, pauze |
| `test_dedupe.py` | același spectacol publicat la două URL-uri |
| `test_pipeline_db.py` | crawler complet → MySQL: două rulări fără duplicate, actualizare, reprogramare, reprezentație dispărută, colectare eșuată, afiș eșuat, câmpuri NULL |
| `test_web.py` | toate rutele, căutare, 404, ordine cronologică, afișe servite local, escaping HTML, **fără acces la rețea** |

Testele de integrare folosesc un „site simulat” (`tests/fake_site.py`) care servește snapshot-urile reale;
modificările controlate (durată schimbată, reprezentație mutată/ștearsă, afiș indisponibil) sunt create în
cod și marcate `DATE DE TEST`. Dacă MySQL nu rulează, testele de bază de date sunt sărite (`skipped`), nu picate.

Verificări practice făcute pe site-ul real (22.11.2026):

- 9 rulări complete ale crawlerului: 0 erori HTTP, 39 de pagini descoperite, 38 de spectacole + „Tur ghidat”,
  37 de afișe, 23 de reprezentații (cât anunță și pagina de program);
- rulările repetate fără modificări de cod: 0 inserări, 0 actualizări, 0 afișe redescărcate;
- toate cele 23 de reprezentații asociate cu spectacolul corect (verificat manual, rând cu rând);
- eșantion comparat cu sursa: *Macbeth*, *Cabaret*, *Gardenia*, *Pescărușul*, *Svejk*, *Ludwig* etc. (valorile din teste);
- capturi de ecran Playwright la 1280 px și 390 px pentru `/`, `/shows`, `/shows/{id}`, `/schedule`, căutare fără rezultat și 404:
  fără scroll orizontal și fără nicio cerere către alt domeniu decât aplicația locală.

---

## Limitări cunoscute

- **Selectorii depind de structura actuală a site-ului** (WordPress + WPBakery și widget-ul de program).
  O reproiectare a site-ului va cere actualizarea lor.
- **Programul depinde de un browser** (Playwright/Chromium) și de widget-ul extern. Dacă widget-ul nu se încarcă,
  colectarea programului eșuează explicit, iar datele existente rămân neschimbate.
- **Anul reprezentațiilor** este dedus din ziua săptămânii; site-ul nu îl publică.
- **Nu există URL per reprezentație** pe site: `performances.source_url` este pagina de program, iar identitatea
  stabilă vine din `external_id`.
- **Ora de final** nu este publicată → `end_at` rămâne NULL (nu o calculăm din durată).
- **Autor / regizor** se deduc din linia de credit sau din echipă; când formularea e ambiguă
  (ex. *Cabaret*: „libretul de JOE MASTEROFF după piesa lui …”), câmpul rămâne gol, iar textul complet apare ca `subtitle`.
- **Distribuția/echipa**: o pagină publică doar text liber (*Puseu de iubire*) → listele rămân goale;
  două rânduri fără rol identificabil sunt păstrate textual cu `role: null`.
- **Limba**: site-ul nu precizează limba spectacolului; câmpul `language` conține doar mențiunile de
  traducere/supratitrare publicate. **Genul** nu este publicat → NULL.
- **Vârsta**: când pagina spectacolului nu o publică, se folosește eticheta din program („14+”).
- **Afiș schimbat la același URL**: detectat numai cu `--refresh-posters` (comparație SHA-256).
- Spectacolele care dispar din `/stagiune/` rămân în baza de date (vizibile prin `last_seen_at`), nu sunt ascunse.
- Textele și afișele aparțin Teatrului Odeon; aplicația are scop educațional și nu este publicată.

---

## Pe scurt, pentru prezentare

1. **Separarea responsabilităților**: descărcare (`http.py`, `render.py`) → parsare (`parse_*.py`, funcții pure,
   testate pe pagini reale) → bază de date (`db.py`) → afișare (`web/`). Web-ul nu cunoaște crawlerul.
2. **Am inspectat site-ul înainte de cod**: paginile de spectacol sunt HTML static (httpx + Beautiful Soup ajung),
   dar programul e generat de JavaScript → Playwright, doar acolo unde e necesar.
3. **Am respectat restricțiile de acces**: robots.txt, ritm de 2 s, Retry-After, și nu am ocolit cheia API restricționată pe domeniu.
4. **Identitate stabilă**: `slug` pentru spectacole, `external_id` + (spectacol, dată, sală) pentru reprezentații
   → fără duplicate, cu actualizări și reprogramări corecte; nimic nu se șterge din cauza unei colectări eșuate.
5. **Fus orar explicit**: UTC în baza de date, Europe/Bucharest la afișare.

---

## Utilizarea AI în acest proiect

Pe parcursul proiectului am utilizat Claude Code (modelul Claude Opus 5.5), în VS Code, pentru:

- **analiza cerințelor** — i-am cerut să citească cele două PDF-uri și să separe cerințele obligatorii de recomandări
  și opțiuni (rezultatul este `REQUIREMENTS.md`);
- **inspectarea site-ului** — a verificat `robots.txt` și sitemap-ul, a analizat HTML-ul paginilor de spectacol și a
  constatat că programul este generat de JavaScript, printr-un widget cu cheie API restricționată la domeniul teatrului;
  de aici a rezultat folosirea Playwright doar pentru pagina de program;
- **organizarea structurii aplicației** — a propus împărțirea în crawler, acces la baza de date și interfață web;
- **definirea schemei bazei de date** — a pornit de la schema MySQL din PDF și a adăugat câmpurile `slug`, `subtitle`,
  `origin`, `external_id` și `source_title`, cu justificarea din `db/schema.sql`;
- **implementare** — codul crawlerului, al accesului la baza de date și al interfeței web (Flask, template-uri, CSS)
  a fost generat de Claude Code, pe baza cerințelor noastre;
- **identificarea erorilor** — prin rulări pe site-ul real a găsit formate de distribuție netratate, aceeași producție
  publicată la două adrese (*Nijinski*) și autori extrași greșit, apoi a corectat parserul;
- **teste** — a propus și a scris testele pytest și a rulat suita, crawlerul pe site-ul real și capturile de ecran
  pentru desktop și mobil, descrise în secțiunea „Teste și verificări”.

Am decis noi să folosim MySQL în Docker, după ce serverul MySQL local a cerut o parolă de root pe care asistentul nu o avea.
Am solicitat și explicații pentru înțelegerea soluțiilor tehnice: la fiecare etapă, ce s-a realizat, de ce și cum se verifică.

Fișierul `PROMPTURI_SPRIJIN_AI.md` conține **exemple** de prompturi pentru învățare, nu istoricul acestei colaborări.
