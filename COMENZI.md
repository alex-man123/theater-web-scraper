# Comenzile proiectului, în ordine

Toate comenzile se rulează în **PowerShell**, din folderul proiectului (`C:\Users\ALEX\OneDrive\Desktop\Odeon`).
În VS Code: **Terminal → New Terminal**.

---

## A. Prima instalare (o singură dată)

Pe acest calculator pașii A1–A4 sunt deja făcuți. Sunt necesari doar pe un calculator nou.

**A1. Mediul virtual Python**
```powershell
py -3.12 -m venv .venv
```

**A2. Dependențele**
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**A3. Browserul folosit pentru pagina de program**
```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

**A4. Fișierul de configurare**
```powershell
Copy-Item .env.example .env
```
Deschideți apoi `.env` și schimbați `DB_PASSWORD` și `MYSQL_ROOT_PASSWORD`.

---

## B. De fiecare dată când lucrați la proiect

**B1. Porniți Docker Desktop** (din meniul Start) și așteptați să scrie că rulează.

**B2. Porniți baza de date MySQL**
```powershell
docker compose up -d
```
Verificare (trebuie să apară `healthy`):
```powershell
docker inspect -f '{{.State.Health.Status}}' odeon-mysql
```

**B3. Colectați datele de pe site** (~2 minute)
```powershell
.\.venv\Scripts\python.exe -m odeon.crawler.run
```
Așteptați rândul care începe cu `REZUMAT:` și revenirea promptului `PS C:\...>`.
Pasul este opțional dacă baza are deja date și nu vreți să le actualizați.

**B4. Porniți aplicația web**
```powershell
.\.venv\Scripts\python.exe -m odeon.web
```
Deschideți în browser: **http://127.0.0.1:5000**

**B5. Oprirea aplicației web:** `Ctrl+C` în terminalul în care rulează.

---

## C. Testele

MySQL trebuie să ruleze (pasul B2).
```powershell
.\.venv\Scripts\python.exe -m pytest
```
Rezultat așteptat: `63 passed`.

---

## D. Comenzi utile (opționale)

| Ce vreți | Comanda |
|---|---|
| Crawler doar pe primele 5 spectacole | `.\.venv\Scripts\python.exe -m odeon.crawler.run --limit 5` |
| Crawler fără program (fără browser) | `.\.venv\Scripts\python.exe -m odeon.crawler.run --skip-schedule` |
| Reverificarea afișelor (hash) | `.\.venv\Scripts\python.exe -m odeon.crawler.run --refresh-posters` |
| Aplicația web pe alt port | `$env:WEB_PORT=5001; .\.venv\Scripts\python.exe -m odeon.web` |
| Jurnalul crawlerului | `Get-Content logs\crawler.log -Tail 30 -Encoding utf8` |
| Oprirea bazei de date | `docker compose stop` |
| Ștergerea completă a bazei (atenție: pierdeți datele) | `docker compose down -v` |

---

## E. Probleme frecvente

- **`failed to connect to the docker API`** → Docker Desktop nu e pornit (pasul B1).
- **`Can't connect to MySQL server`** → containerul nu rulează (pasul B2) sau nu e încă `healthy`.
- **Portul 5000 este ocupat** → mai rulează o instanță a aplicației; închideți-o sau folosiți `WEB_PORT=5001`.
- **Caractere ciudate în loc de diacritice în consolă** → rulați întâi `$env:PYTHONIOENCODING='utf-8'`.
