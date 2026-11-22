"""Aplicația web (Flask). Citește EXCLUSIV din baza de date locală.

Nicio rută nu apelează crawlerul și nu face cereri către teatrul-odeon.ro;
afișele sunt servite din storage/posters.

Pornire:  python -m odeon.web       (http://127.0.0.1:5000)
"""
from __future__ import annotations

from datetime import datetime

from flask import Flask, abort, g, render_template, request, send_from_directory, url_for

from odeon import config, db
from odeon.crawler.normalize import now_utc, utc_to_local

DAYS = ["luni", "marți", "miercuri", "joi", "vineri", "sâmbătă", "duminică"]
MONTHS = ["ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie",
          "august", "septembrie", "octombrie", "noiembrie", "decembrie"]
STATUS_LABELS = {"reprogramat": "Reprogramat", "anulat": "Anulat", "amanat": "Amânat"}


def create_app(database: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["DB_NAME"] = database or config.DB_NAME
    app.config["NOW_FN"] = now_utc  # testele pot fixa "acum" pentru rezultate deterministe

    def get_conn():
        if "conn" not in g:
            g.conn = db.connect(app.config["DB_NAME"])
        return g.conn

    @app.teardown_appcontext
    def close_conn(_exc):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    # --- filtre pentru template-uri (ora afișată = ora României) ------------
    @app.template_filter("local")
    def to_local(dt: datetime | None):
        return utc_to_local(dt) if dt else None

    @app.template_filter("ro_date")
    def ro_date(dt: datetime | None, with_weekday: bool = True):
        if not dt:
            return ""
        loc = utc_to_local(dt)
        text = f"{loc.day} {MONTHS[loc.month - 1]} {loc.year}"
        return f"{DAYS[loc.weekday()]}, {text}" if with_weekday else text

    @app.template_filter("ro_time")
    def ro_time(dt: datetime | None):
        return utc_to_local(dt).strftime("%H:%M") if dt else ""

    @app.template_filter("ro_plain_date")
    def ro_plain_date(d):
        return f"{d.day} {MONTHS[d.month - 1]} {d.year}" if d else ""

    @app.context_processor
    def helpers():
        def poster_url(path: str | None) -> str:
            # Afiș lipsă sau fișier șters -> imagine substitut locală.
            if path:
                f = config.POSTER_DIR.parent / path
                if f.is_file():
                    return url_for("poster", filename=f.name)
            return url_for("static", filename="img/poster-placeholder.svg")
        return {"poster_url": poster_url, "status_labels": STATUS_LABELS}

    # --- rute ------------------------------------------------------------
    @app.route("/")
    def index():
        conn, now = get_conn(), app.config["NOW_FN"]()
        shows = db.list_shows(conn, now)
        return render_template(
            "index.html",
            upcoming=db.upcoming_performances(conn, now, limit=8),
            shows=[s for s in shows if s["next_start_at"]][:12] or shows[:12],
            total_shows=len(shows),
            info=db.counts(conn),
        )

    @app.route("/shows")
    def shows():
        q = (request.args.get("q") or "").strip()[:100]
        return render_template("shows.html", shows=db.list_shows(get_conn(), app.config["NOW_FN"](), q or None), q=q)

    @app.route("/shows/<int:show_id>")
    def show_detail(show_id: int):
        conn = get_conn()
        show = db.get_show(conn, show_id)
        if show is None:
            abort(404)
        perfs = db.upcoming_performances(conn, app.config["NOW_FN"](), show_id=show_id)
        return render_template("show_detail.html", show=show, performances=perfs)

    @app.route("/schedule")
    def schedule():
        conn, now = get_conn(), app.config["NOW_FN"]()
        venue = (request.args.get("venue") or "").strip() or None
        perfs = db.upcoming_performances(conn, now, venue=venue)
        days: list[tuple[str, list]] = []  # grupare pe zile, păstrând ordinea cronologică
        for p in perfs:
            label = ro_date(p["start_at"])
            if not days or days[-1][0] != label:
                days.append((label, []))
            days[-1][1].append(p)
        return render_template("schedule.html", days=days, count=len(perfs),
                               venues=db.venues(conn, now), venue=venue)

    @app.route("/posters/<path:filename>")
    def poster(filename: str):
        return send_from_directory(config.POSTER_DIR, filename, max_age=86400)

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("404.html"), 404

    return app
