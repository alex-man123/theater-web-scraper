"""Scraper pentru pagina unui spectacol (https://teatrul-odeon.ro/spectacol/<slug>/).

Selectorii provin din inspectarea paginilor reale (noiembrie 2026). Site-ul e
construit cu WordPress + WPBakery, deci structura este:

  h1 / og:title                         -> titlu
  .the_content_wrapper
    coloana .vc_col-sm-8
      primul .wpb_text_column           -> linia de autor/regie ("de X, regia Y")
      .vc_tta-panel "Distribuția"       -> distribuție + echipă artistică
      .wpb_text_column (după tab-uri)   -> descriere
    coloana .vc_col-sm-4                -> data premierei, durata, vârsta, limba
      img.vc_single_image-img           -> afișul
    "Extrase de presă"                  -> NU face parte din descriere

Orice câmp care nu apare rămâne None. Nu inventăm valori.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from .normalize import clean_text, parse_duration_minutes, parse_ro_date, strip_diacritics


@dataclass
class ShowData:
    source_url: str
    slug: str
    title: str
    subtitle: str | None = None
    author: str | None = None
    director: str | None = None
    description: str | None = None
    genre: str | None = None
    language: str | None = None
    duration_minutes: int | None = None
    duration_text: str | None = None
    age_recommendation: str | None = None
    premiere_date: date | None = None
    cast: list[dict] = field(default_factory=list)
    team: list[dict] = field(default_factory=list)
    poster_source_url: str | None = None
    origin: str = "show_page"  # 'schedule' = spectacol cunoscut doar din program


# Cuvinte care indică un rol din echipa artistică (nu un personaj).
# Lista servește DOAR la a decide dacă un paragraf este echipă sau distribuție;
# denumirea rolului se păstrează exact cum a publicat-o teatrul.
_TEAM_HINT = re.compile(
    r"^(de|text|textul|autor|dupa)$|regi|regiz|dramatiz|dramaturg|adapt|traduc|decor|scenograf|"
    r"costum|muzic|cantece|songuri|light|lumin|sound|sunet|coregraf|miscare|asisten|video|"
    r"visual|make-up|machiaj|concept|pregatire|directi|consultan|produc|orchestr|grafic|"
    r"ilustrat|vocal|instrument|animatie|papusi|editare"
)
# "Label: valoare" sau "Label – valoare" (cratima trebuie să fie între spații,
# ca să nu tăiem nume compuse precum "Ana-Maria").
_LABEL_RE = re.compile(r"^(?P<label>[^:–—]{1,120}?)\s*(?::|\s[–—-]\s?|[–—]$)\s*(?P<value>.*)$")


def _is_team_label(label: str) -> bool:
    return bool(_TEAM_HINT.search(strip_diacritics(label).lower().strip()))


def _lines(el: Tag) -> list[str]:
    """Textul unui element împărțit pe rânduri (<br> și <p> devin rânduri noi)."""
    parts: list[str] = []
    for node in el.descendants:
        if isinstance(node, NavigableString):
            parts.append(str(node))
        elif node.name == "br":
            parts.append("\n")
        elif node.name == "p":
            parts.append("\n")
    text = clean_text("".join(parts)) or ""
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def _block_text(el: Tag) -> str | None:
    """Textul unui bloc, cu paragrafele separate prin linie goală (fără HTML)."""
    parts = el.find_all(["h2", "h3", "h4", "p", "li"])
    paragraphs = [" ".join(_lines(p)) for p in parts] or [" ".join(_lines(el))]
    return clean_text("\n\n".join(p for p in paragraphs if p))


def _split_names(value: str, separators: str = r"\s*[;,]\s*|\s+/\s+") -> list[str]:
    return [n.strip(" .") for n in re.split(separators, value) if n.strip(" .")]


# Antete care înseamnă "joacă:" – numele care urmează sunt actori, fără personaj.
_CAST_HEADERS = {"cu", "distributia", "in distributie", "interpreteaza", "joaca", "cu actorii", "actori", "actorii"}


def _is_cast_header(label: str | None) -> bool:
    return bool(label) and strip_diacritics(label).lower().strip(" :") in _CAST_HEADERS


@dataclass
class _Line:
    """Un rând din panoul de distribuție, cu informații despre marcajul HTML."""
    text: str
    label: str | None = None
    value: str = ""
    label_is_person: bool = False   # eticheta conține o legătură /om/ (profil de actor)
    value_is_person: bool = False
    all_emphasized: bool = False    # tot rândul e <strong>/<em>


def _rich_lines(p: Tag) -> list[list[tuple[str, bool, bool]]]:
    """Împarte un <p> în rânduri (după <br>); fiecare rând = segmente (text, evidențiat, link_persoană)."""
    lines: list[list[tuple[str, bool, bool]]] = [[]]
    for node in p.descendants:
        if isinstance(node, NavigableString):
            if isinstance(node, Comment):
                continue
            emph = person = False
            for parent in node.parents:
                if parent is p:
                    break
                if parent.name in ("strong", "b", "em", "i"):
                    emph = True
                if parent.name == "a" and "/om/" in (parent.get("href") or ""):
                    person = True
            lines[-1].append((str(node).replace("\xa0", " "), emph, person))
        elif node.name in ("br", "div", "p"):  # unele pagini pun fiecare rând într-un <div>
            lines.append([])
    return [segs for segs in lines if "".join(t for t, _, _ in segs).strip()]


def _analyse(segs: list[tuple[str, bool, bool]]) -> _Line:
    raw = "".join(t for t, _, _ in segs)
    emph = [e for t, e, _ in segs for _ in t]
    person = [pz for t, _, pz in segs for _ in t]
    visible = [i for i, ch in enumerate(raw) if not ch.isspace()]
    line = _Line(text=clean_text(raw) or "", all_emphasized=all(emph[i] for i in visible))

    def any_flag(flags, start, end):
        return any(flags[i] for i in range(start, end) if not raw[i].isspace())

    # 1) separator textual: "Etichetă: valoare" / "Etichetă – valoare"
    lead = len(raw) - len(raw.lstrip())
    m = _LABEL_RE.match(raw.strip())
    if m:
        line.label = clean_text(m.group("label"))
        line.value = clean_text(m.group("value")) or ""
        line.label_is_person = any_flag(person, lead + m.start("label"), lead + m.end("label"))
        line.value_is_person = any_flag(person, lead + m.start("value"), lead + m.end("value"))
        return line

    # 2) "PERSONAJ / <a href=/om/...>Actor</a>": " / " separă personajul de actor doar
    #    când stânga NU e un profil de actor, iar dreapta este (altfel "/" = distribuție alternativă)
    idx = raw.find(" / ")
    if idx > 0 and not any_flag(person, 0, idx) and any_flag(person, idx, len(raw)):
        line.label, line.value = clean_text(raw[:idx]), clean_text(raw[idx + 3:]) or ""
        line.value_is_person = True
        return line

    # 3) fără separator, dar o parte e îngroșată și cealaltă nu:
    #    "<strong>Regie și decor</strong> Dragoș Galgoțiu" sau "Regia <strong>Eugen Jebeleanu</strong>"
    runs: list[list] = []  # [evidențiat, text]
    for text, e, _ in segs:
        if not text.strip():
            if runs:
                runs[-1][1] += text
            continue
        if runs and runs[-1][0] == e:
            runs[-1][1] += text
        else:
            runs.append([e, text])
    if len(runs) == 2:
        line.label, line.value = clean_text(runs[0][1]), clean_text(runs[1][1]) or ""
        return line

    # 4) text simplu "Regia Radu Alexandru Nica": dacă primul cuvânt e un rol cunoscut,
    #    eticheta ține până la primul cuvânt scris cu majusculă (începutul numelui).
    words = line.text.split()
    if len(words) >= 2 and _is_team_label(words[0]):
        for i in range(1, len(words)):
            if words[i][:1].isupper():
                line.label, line.value = " ".join(words[:i]), " ".join(words[i:])
                break
    return line


def _looks_like_credits(block: Tag) -> bool:
    """Cel puțin 3 rânduri, din care ≥ 60% de forma "Etichetă scurtă: valoare"."""
    lines = ["".join(t for t, _, _ in segs).strip()
             for p in (block.find_all("p") or [block]) for segs in _rich_lines(p)]
    if len(lines) < 3:
        return False
    labelled = 0
    for ln in lines:
        m = _LABEL_RE.match(ln)
        if m and len(m.group("label").strip()) <= 60 and m.group("value").strip():
            labelled += 1
    return labelled / len(lines) >= 0.6


def parse_people(panel: Tag) -> tuple[list[dict], list[dict]]:
    """Transformă panoul "Distribuția" în (cast, team), ambele liste JSON-serializabile.

    Site-ul folosește mai multe formate, observate pe pagini reale:
      "Personaj: Actor" / "Personaj – Actor"              (majoritatea)
      "Actor – Personaj"  (numele are legătură /om/)       (Tertium non datur)
      "<em>Rol</em><br>Nume<br>Nume"                       (One Man Aproape Show)
      "<strong>Cu:</strong>" urmat de un paragraf cu nume  (Ludwig)
      "<strong>Rol</strong> Nume" / "Rol <strong>Nume</strong>" (Ludwig, Am avut o livadă)
    Fiecare <p> este echipă dacă majoritatea etichetelor arată ca roluri
    (Regia, Decorul, ...); altfel este distribuție. Rolurile se păstrează textual.
    """
    cast: list[dict] = []
    team: list[dict] = []
    paragraphs = [p for p in panel.select(".wpb_text_column p") or panel.find_all("p") if p.get_text(strip=True)]
    if not paragraphs:
        # varianta cu <div> în loc de <p>: fiecare <div> direct din .wpb_wrapper e un grup
        paragraphs = [d for w in panel.select(".wpb_text_column > .wpb_wrapper")
                      for d in w.find_all("div", recursive=False) if d.get_text(strip=True)]
    pending_header = None  # antet rămas dintr-un paragraf anterior (ex. "Cu:")
    for p in paragraphs:
        lines = [_analyse(s) for s in _rich_lines(p)]
        if not lines:
            continue
        # Un rând complet evidențiat, urmat de rânduri neevidențiate, este un antet ("<em>Muzica</em>").
        for i, ln in enumerate(lines):
            if ln.label is None and ln.all_emphasized and i + 1 < len(lines) and not lines[i + 1].all_emphasized:
                ln.label, ln.value = ln.text.rstrip(" :"), ""
        if len(lines) == 1:
            only = lines[0]
            if only.label and not only.value:
                pending_header = only.label  # "Cu:" singur în paragraf
                continue
            if only.label is None and only.all_emphasized:
                continue  # titlu de grup, ex. "Trupa de la Kit Kat Club" – nu e o persoană

        header, pending_header = pending_header, None
        labels = [ln.label for ln in lines if ln.label] or ([header] if header else [])
        is_team = bool(labels) and sum(_is_team_label(lab) for lab in labels) * 2 >= len(labels)
        reversed_order = sum(ln.label_is_person for ln in lines) > sum(ln.value_is_person for ln in lines)

        for ln in lines:
            label, value = ln.label, ln.value
            if label and not value:
                header = label
                continue
            if label is None:
                if is_team and header:
                    for item in _split_names(ln.text, r";"):   # "Nume, instrument; Nume, instrument"
                        name, _, detail = item.partition(",")
                        role = f"{header} – {detail.strip()}" if detail.strip() else header
                        team.append({"role": role, "name": name.strip()})
                elif is_team:
                    team.append({"role": None, "name": ln.text})  # rând fără rol identificabil, păstrat textual
                elif not header and len(ln.text.split()) > 5:
                    continue  # o propoziție (ex. "Poeme de ... în traducerea lui ..."), nu un nume
                else:
                    for name in _split_names(ln.text):
                        entry = {"name": name}
                        if header and not _is_cast_header(header):
                            entry["character"] = header
                        cast.append(entry)
            elif _is_cast_header(label):  # "Actori: X, Y" e distribuție chiar și într-un paragraf de echipă
                cast.extend({"name": name} for name in _split_names(value))
            elif is_team:
                for name in _split_names(value):
                    team.append({"role": label, "name": name})
            elif reversed_order:
                cast.append({"name": label, "character": value})
            else:
                cast.extend({"name": name, "character": label} for name in _split_names(value))
    return cast, team


_AUTHOR_RE = re.compile(
    r"^(?:un\s+spectacol\s+de|de|după|dupa|(?:pe\s+)?texte?\s+de)\s+(?P<author>.+?)"
    r"(?:,?\s+(?:regia|regie|traducerea)\b.*)?$",
    re.IGNORECASE,
)
# "regia X", "regia artistică X", "regia și traducerea X", "regia: X"
_DIRECTOR_RE = re.compile(
    r"\bregi[ae](?:\s+artistică)?(?:\s+și\s+[a-zăâîșşțţ]+)*\s*:?\s+(?P<director>[^,;]+)", re.IGNORECASE
)


def author_from_credit(credit: str | None) -> str | None:
    if not credit:
        return None
    credit = credit.strip()
    m = _AUTHOR_RE.match(credit)
    if not m:
        return None
    author = m.group("author").strip(" ,.")
    if re.match(r"^(după|dupa)\s", credit, re.IGNORECASE):
        # "după Ceasornicăria Taus de Gellu Naum" -> autorul este cel de după ultimul "de"
        if " de " in author:
            author = author.rsplit(" de ", 1)[1]
    else:
        # "de Enda Walsh, după „Frații Karamazov” de F.M. Dostoievski" -> "Enda Walsh"
        author = re.split(r",?\s+(?:după|dupa)\s+", author, maxsplit=1)[0]
    return author.strip(" ,.") or None


def director_from_credit(credit: str | None) -> str | None:
    if not credit:
        return None
    m = _DIRECTOR_RE.search(credit)
    return m.group("director").strip(" ,.") if m else None


def _pick_poster(content: Tag, page_url: str) -> str | None:
    imgs = content.select("img.vc_single_image-img")
    preferred = [i for i in imgs if "attachment-large" in (i.get("class") or [])]
    for img in preferred + imgs:
        src = img.get("src") or ""
        if not src or re.search(r"qr[-_]|150x150", src, re.IGNORECASE):
            continue
        # Alegem varianta cea mai mare din srcset, dacă există.
        best, best_w = src, 0
        for cand in (img.get("srcset") or "").split(","):
            bits = cand.strip().split()
            if len(bits) == 2 and bits[1].endswith("w") and bits[1][:-1].isdigit():
                if int(bits[1][:-1]) > best_w:
                    best, best_w = bits[0], int(bits[1][:-1])
        return urljoin(page_url, best.split("#")[0])
    return None


def _parse_sidebar(cols: list[Tag], show: ShowData) -> None:
    lines = []
    for col in cols:
        # Textele simple + casetele de mesaj (vârsta, traducerea apar în .vc_message_box).
        for block in col.select(".wpb_text_column, .vc_message_box"):
            if block.name and "vc_message_box" in (block.get("class") or []):
                text = " ".join(_lines(block))
                # păstrăm doar prima propoziție (restul sunt instrucțiuni de rezervare)
                lines.append(re.split(r"(?<=[.!])\s", text, maxsplit=1)[0])
            else:
                lines.extend(_lines(block))
    for i, ln in enumerate(lines):
        low = strip_diacritics(ln).lower()
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if low.startswith("data premierei"):
            value = ln.split(":", 1)[1].strip() if ":" in ln else ""
            show.premiere_date = parse_ro_date(value or nxt)
        elif low.startswith("durata"):
            value = ln.split(":", 1)[1].strip() if ":" in ln else ""
            show.duration_text = clean_text(value or nxt)
            show.duration_minutes = parse_duration_minutes(show.duration_text)
        elif show.age_recommendation is None and re.search(
            r"(nerecomandat|recomandat|interzis|varsta).*\d|\b\d{1,2}\s*\+", low
        ):
            show.age_recommendation = ln
        elif show.language is None and re.search(r"\blimba\b|supratitr", low):
            show.language = ln


def parse_show_page(html: str, url: str) -> ShowData | None:
    """Extrage datele unui spectacol. Returnează None dacă pagina nu e un spectacol."""
    soup = BeautifulSoup(html, "lxml")
    body_classes = (soup.body.get("class") or []) if soup.body else []
    if "single-spectacol" not in body_classes:
        return None

    og = soup.select_one('meta[property="og:title"]')
    h1 = soup.find("h1")
    title = clean_text(og.get("content") if og and og.get("content") else (h1.get_text() if h1 else None))
    if not title:
        return None
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    show = ShowData(source_url=url, slug=slug, title=title)

    content = soup.select_one(".the_content_wrapper")
    if content is None:
        return show

    panel = None
    for p in content.select(".vc_tta-panel"):
        heading = p.select_one(".vc_tta-panel-title")
        if heading and "distribu" in strip_diacritics(heading.get_text()).lower():
            panel = p
            break
    if panel is not None:
        show.cast, show.team = parse_people(panel)

    _parse_sidebar(content.select(".vc_col-sm-4"), show)
    show.poster_source_url = _pick_poster(content, url)

    # Blocurile de text în ordinea documentului: primul (scurt, înaintea
    # tab-urilor) e linia de credit; restul, până la "Extrase de presă", e descrierea.
    description: list[str] = []
    tabs = content.select_one(".vc_tta-container")
    stop_heading = None
    for h in content.find_all(["h1", "h2", "h3"]):
        if "extrase de pres" in strip_diacritics(h.get_text()).lower():
            stop_heading = h
            break
    for block in content.select(".wpb_text_column"):
        if block.find_parent(class_="vc_tta-panel") or block.find_parent(class_="vc_col-sm-4"):
            continue
        if stop_heading is not None and _is_after(block, stop_heading):
            break
        text = _block_text(block)
        if not text or re.fullmatch(r"https?://\S+", text):  # ex. linkul de rezervă al unui <video>
            continue
        if re.match(r"^(foto(grafii)?\s+de|link caiet)", strip_diacritics(text).lower()):
            continue
        if panel is None and not show.cast and not show.team and (
                strip_diacritics(text).lower().startswith("distributia") or _looks_like_credits(block)):
            # fără tab "Distribuția": blocul "Distribuția: ..." (Eu sunt Luli) sau un bloc
            # format aproape numai din rânduri "Rol: Nume" (Nijinski)
            show.cast, show.team = parse_people(block)
            continue
        if show.subtitle is None and not description and (tabs is None or not _is_after(block, tabs)):
            first, _, rest = text.partition("\n\n")
            if len(first) <= 300:
                show.subtitle = first.replace("\n", " ")
                if rest:
                    description.append(rest)
                continue
        description.append(text)
    show.description = clean_text("\n\n".join(description))

    team_author = next(
        (t["name"] for t in show.team
         if t["role"] and strip_diacritics(t["role"]).lower().strip() in {"de", "text", "textul", "autor"}),
        None,
    )
    show.author = team_author or author_from_credit(show.subtitle)
    team_director = next(
        (t["name"] for t in show.team
         if t["role"] and re.search(r"\bregi[ae]\b", strip_diacritics(t["role"]).lower())
         and not re.search(r"asisten|tehnic", strip_diacritics(t["role"]).lower())),
        None,
    )
    show.director = team_director or director_from_credit(show.subtitle)
    return show


def _is_after(a: Tag, b: Tag) -> bool:
    """True dacă elementul a apare în document după elementul b."""
    for el in b.next_elements:
        if el is a:
            return True
    return False


def discover_show_urls(season_html: str, base_url: str) -> list[str]:
    """Crawling: din pagina /stagiune/ extragem toate legăturile /spectacol/<slug>/."""
    soup = BeautifulSoup(season_html, "lxml")
    seen: dict[str, None] = {}
    for a in soup.select('a[href*="/spectacol/"]'):
        href = urljoin(base_url, a["href"]).split("#")[0].split("?")[0]
        href = href.replace("://www.", "://")
        m = re.match(r"^https?://teatrul-odeon\.ro/spectacol/([^/]+)/?$", href)
        if m:
            seen[f"https://teatrul-odeon.ro/spectacol/{m.group(1)}/"] = None
    return list(seen)
