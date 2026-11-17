"""
«Мониторинг» — система контроля противопожарного состояния объектов.

Два типа кабинетов:
  * обслуживающая организация (роли admin и engineer) — видит все объекты;
  * эксплуатант (роль client: собственник, арендатор, УК) — видит свои объекты.

Запуск локально:  python app.py   →  http://127.0.0.1:5000
"""
import json
import os
import secrets
import sqlite3
import uuid
from datetime import date, datetime
from functools import wraps

import click
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import maintenance as mt
import norms
from app_utils import add_months

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me"),
    DATABASE=os.environ.get("DATABASE", os.path.join(DATA_DIR, "firemon.db")),
    UPLOAD_DIR=os.environ.get("UPLOAD_DIR", os.path.join(DATA_DIR, "uploads")),
    MAX_CONTENT_LENGTH=int(os.environ.get("MAX_UPLOAD_MB", "25")) * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
)

ROLE_NAMES = {"admin": "Администратор", "engineer": "Инженер", "client": "Эксплуатант"}
SIDE_NAMES = {"client": "Эксплуатант", "provider": "Обслуживающая организация"}
TASK_STATUS = {
    "overdue": ("Просрочено", "red"),
    "soon": ("Скоро срок", "yellow"),
    "ok": ("В норме", "green"),
    "nodata": ("Нет данных", "gray"),
}
LEVELS = {"red": "Требует внимания", "yellow": "Есть вопросы", "green": "В норме"}
SEVERITY = {"critical": "Критическое", "medium": "Значительное", "low": "Незначительное"}
ISSUE_STATUS = {"open": "Открыто", "in_progress": "В работе", "resolved": "Устранено"}
ISSUE_KIND = {"remark": "Замечание", "request": "Заявка"}
WORK_TYPES = ["Техническое обслуживание", "Проверка работоспособности", "Испытания", "Осмотр",
              "Ремонт", "Перезарядка / замена", "Инструктаж", "Тренировка", "Прочее"]
RESULTS = ["Исправно / выполнено", "Выполнено с замечаниями", "Неисправно"]
FILE_CATEGORIES = ["Договор на ТО", "Исполнительная документация", "Акт", "Протокол", "Приказ",
                   "Сертификат", "Инструкция", "Журнал", "Предписание", "Прочее"]
ANSWERS = {"yes": "Да", "no": "Нет", "na": "Не применимо"}


# ==========================================================================
# База данных
# ==========================================================================
def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(app.config["DATABASE"]) or ".", exist_ok=True)
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with open(os.path.join(BASE_DIR, "schema.sql"), encoding="utf-8") as f:
        db.executescript(f.read())
    db.commit()


_db_ready = False


@app.before_request
def ensure_db():
    global _db_ready
    if not _db_ready:
        init_db()
        db = get_db()
        email, pwd = os.environ.get("ADMIN_EMAIL"), os.environ.get("ADMIN_PASSWORD")
        if email and pwd and not db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            create_user(email, pwd, os.environ.get("ADMIN_NAME", "Администратор"), "admin")
        _db_ready = True


def create_user(email, password, name, role, client_id=None, phone=None):
    db = get_db()
    db.execute("INSERT INTO users (email, password_hash, name, role, client_id, phone) VALUES (?,?,?,?,?,?)",
               (email.strip().lower(), generate_password_hash(password), name.strip(), role, client_id, phone))
    db.commit()


# ==========================================================================
# Авторизация, CSRF
# ==========================================================================
@app.before_request
def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = get_db().execute("SELECT * FROM users WHERE id=? AND active=1", (uid,)).fetchone()
        if g.user is None:
            session.clear()


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


@app.before_request
def check_csrf():
    if request.method == "POST" and not app.config.get("TESTING_NO_CSRF"):
        token = session.get("csrf")
        if not token or not secrets.compare_digest(request.form.get("csrf", ""), token):
            abort(400, "Сессия устарела, обновите страницу и повторите.")


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(*a, **kw)
    return wrapped


def roles(*allowed):
    def deco(view):
        @wraps(view)
        @login_required
        def wrapped(*a, **kw):
            if g.user["role"] not in allowed:
                abort(403)
            return view(*a, **kw)
        return wrapped
    return deco


def is_provider():
    return g.user is not None and g.user["role"] in ("admin", "engineer")


@app.context_processor
def inject():
    return dict(csrf_token=csrf_token, user=g.get("user"), is_provider=is_provider,
                ROLE_NAMES=ROLE_NAMES, SIDE_NAMES=SIDE_NAMES, TASK_STATUS=TASK_STATUS, LEVELS=LEVELS,
                SEVERITY=SEVERITY, ISSUE_STATUS=ISSUE_STATUS, ISSUE_KIND=ISSUE_KIND, ANSWERS=ANSWERS,
                NORMS_NOTE=norms.NORMS_NOTE, today=date.today())


@app.template_filter("ru_date")
def ru_date(value):
    if not value:
        return "—"
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return value


@app.template_filter("period")
def period_label(months):
    m = int(months)
    if m == 1:
        return "ежемесячно"
    if m == 3:
        return "раз в квартал"
    if m == 6:
        return "раз в полгода"
    if m % 12 == 0:
        y = m // 12
        return "раз в год" if y == 1 else f"раз в {y} лет" if y >= 5 else f"раз в {y} года"
    return f"раз в {m} мес."


# ==========================================================================
# Доменная логика
# ==========================================================================
def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def obj_data(obj):
    return json.loads(obj["profile"] or "{}"), json.loads(obj["systems"] or "{}")


def get_object(object_id):
    obj = get_db().execute(
        "SELECT o.*, c.name AS client_name FROM objects o LEFT JOIN clients c ON c.id=o.client_id WHERE o.id=?",
        (object_id,)).fetchone()
    if obj is None:
        abort(404)
    if not is_provider() and obj["client_id"] != g.user["client_id"]:
        abort(403)
    return obj


def visible_objects(include_archived=False):
    sql = "SELECT o.*, c.name AS client_name FROM objects o LEFT JOIN clients c ON c.id=o.client_id WHERE 1=1"
    args = []
    if not include_archived:
        sql += " AND o.archived=0"
    if not is_provider():
        sql += " AND o.client_id=?"
        args.append(g.user["client_id"] or -1)
    return get_db().execute(sql + " ORDER BY o.name", args).fetchall()


def sync_tasks(object_id):
    """Приводит список регламентных работ объекта в соответствие с анкетой."""
    db = get_db()
    obj = db.execute("SELECT * FROM objects WHERE id=?", (object_id,)).fetchone()
    p, s = obj_data(obj)
    applicable = {t["code"]: t for t in norms.applicable_tasks(p, s, date.today().year)}
    existing = {r["code"]: r for r in db.execute("SELECT * FROM tasks WHERE object_id=?", (object_id,))}
    for code, t in applicable.items():
        per = norms.task_period(t, p, s)
        if code in existing:
            row = existing[code]
            db.execute("UPDATE tasks SET active=1, period_months=? WHERE id=?",
                       (row["period_months"] if row["period_custom"] else per, row["id"]))
        else:
            db.execute("INSERT INTO tasks (object_id, code, period_months, side) VALUES (?,?,?,?)",
                       (object_id, code, per, t["side"]))
    for code, row in existing.items():
        if code not in applicable or code not in norms.TASKS_BY_CODE:
            db.execute("UPDATE tasks SET active=0 WHERE id=?", (row["id"],))
    db.commit()


def task_rows(object_id, today=None):
    today = today or date.today()
    rows = []
    for r in get_db().execute("SELECT * FROM tasks WHERE object_id=? AND active=1", (object_id,)):
        t = norms.TASKS_BY_CODE.get(r["code"])
        if not t:
            continue
        last = parse_date(r["last_done"])
        due = add_months(last, r["period_months"]) if last else None
        if due is None:
            status = "nodata"
        else:
            days = (due - today).days
            warn = 7 if r["period_months"] <= 1 else 30
            status = "overdue" if days < 0 else "soon" if days <= warn else "ok"
        rows.append(dict(id=r["id"], code=r["code"], title=t["title"], ref=t["ref"], hint=t.get("hint"),
                         system=t.get("system"), side=r["side"], period=r["period_months"],
                         custom=r["period_custom"], last_done=r["last_done"],
                         next_due=due.isoformat() if due else None, status=status,
                         days=(due - today).days if due else None))
    order = {"overdue": 0, "nodata": 1, "soon": 2, "ok": 3}
    rows.sort(key=lambda x: (order[x["status"]], x["next_due"] or ""))
    return rows


def checklist_rows(obj):
    p, s = obj_data(obj)
    db = get_db()
    answers = {r["item_no"]: r for r in db.execute("SELECT * FROM checklist WHERE object_id=?", (obj["id"],))}
    files = {}
    for f in db.execute("SELECT * FROM files WHERE object_id=? AND link_type='checklist'", (obj["id"],)):
        files.setdefault(f["link_id"], []).append(f)
    rows = []
    for item in norms.applicable_checklist(p, s):
        a = answers.get(item["no"])
        item.update(answer=a["answer"] if a else None, comment=a["comment"] if a else "",
                    updated_at=a["updated_at"] if a else None, files=files.get(item["no"], []))
        rows.append(item)
    return rows


def object_summary(obj):
    db = get_db()
    tasks = task_rows(obj["id"])
    cl = checklist_rows(obj)
    counts = {k: sum(1 for t in tasks if t["status"] == k) for k in TASK_STATUS}
    relevant = [c for c in cl if c["answer"] != "na"]
    yes = sum(1 for c in relevant if c["answer"] == "yes")
    no = sum(1 for c in relevant if c["answer"] == "no")
    unanswered = sum(1 for c in relevant if not c["answer"])
    issues = db.execute(
        "SELECT severity, kind, COUNT(*) n FROM issues WHERE object_id=? AND status!='resolved' GROUP BY severity, kind",
        (obj["id"],)).fetchall()
    open_issues = sum(r["n"] for r in issues)
    critical = sum(r["n"] for r in issues if r["severity"] == "critical")
    requests_open = sum(r["n"] for r in issues if r["kind"] == "request")
    if counts["overdue"] or no or critical:
        level = "red"
    elif counts["soon"] or counts["nodata"] or unanswered or open_issues:
        level = "yellow"
    else:
        level = "green"
    last_j = db.execute("SELECT MAX(date) d FROM journal WHERE object_id=?", (obj["id"],)).fetchone()["d"]
    return dict(tasks=counts, total_tasks=len(tasks), cl_total=len(relevant), cl_yes=yes, cl_no=no,
                cl_unanswered=unanswered, cl_pct=round(100 * yes / len(relevant)) if relevant else 0,
                open_issues=open_issues, critical=critical, requests=requests_open, level=level,
                last_journal=last_j)


def save_upload(fs, object_id, category=None, link_type=None, link_id=None):
    if not fs or not fs.filename:
        return None
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    ext = os.path.splitext(fs.filename)[1].lower()[:10]
    stored = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(app.config["UPLOAD_DIR"], stored)
    fs.save(path)
    db = get_db()
    cur = db.execute(
        "INSERT INTO files (object_id, original_name, stored_name, size, category, link_type, link_id, uploaded_by) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (object_id, os.path.basename(fs.filename)[:200], stored, os.path.getsize(path), category,
         link_type, link_id, g.user["id"]))
    return cur.lastrowid


def mark_task_done(object_id, code, done_date):
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE object_id=? AND code=?", (object_id, code)).fetchone()
    if row and (not row["last_done"] or row["last_done"] < done_date):
        db.execute("UPDATE tasks SET last_done=? WHERE id=?", (done_date, row["id"]))


def add_issue(object_id, title, description="", severity="medium", kind="remark", due_date=None,
              checklist_no=None, journal_id=None):
    get_db().execute(
        "INSERT INTO issues (object_id, title, description, severity, kind, due_date, checklist_no, journal_id, created_by) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (object_id, title[:300], description, severity, kind, due_date or None, checklist_no, journal_id,
         g.user["id"]))


def parse_object_form(form):
    profile, systems = {}, {}
    for section in norms.QUESTIONNAIRE:
        for f in section["fields"]:
            name = "p_" + f["key"]
            if f["type"] == "bool":
                profile[f["key"]] = name in form
            else:
                profile[f["key"]] = form.get(name, "").strip()
    for code, sysdef in norms.SYSTEMS.items():
        if f"sys_{code}" in form:
            params = {}
            for f in sysdef["fields"]:
                name = f"s_{code}_{f['key']}"
                params[f["key"]] = (name in form) if f["type"] == "bool" else form.get(name, "").strip()
            systems[code] = params
    return profile, systems


def client_id_from_form(form):
    """Выбор эксплуатанта из списка или создание нового прямо из анкеты."""
    new_name = form.get("new_client", "").strip()
    if new_name:
        cur = get_db().execute("INSERT INTO clients (name) VALUES (?)", (new_name,))
        return cur.lastrowid
    cid = form.get("client_id")
    return int(cid) if cid and cid.isdigit() else None


# ==========================================================================
# Вход, первичная настройка
# ==========================================================================
@app.route("/setup", methods=["GET", "POST"])
def setup():
    db = get_db()
    if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        return redirect(url_for("login"))
    if request.method == "POST":
        email, name, pwd = request.form["email"], request.form["name"], request.form["password"]
        if len(pwd) < 8:
            flash("Пароль — не короче 8 символов", "error")
        else:
            create_user(email, pwd, name, "admin")
            flash("Администратор создан, войдите", "ok")
            return redirect(url_for("login"))
    return render_template("setup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if not get_db().execute("SELECT 1 FROM users LIMIT 1").fetchone():
        return redirect(url_for("setup"))
    if request.method == "POST":
        u = get_db().execute("SELECT * FROM users WHERE email=? AND active=1",
                             (request.form["email"].strip().lower(),)).fetchone()
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session.clear()
            session["uid"] = u["id"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("dashboard"))
        flash("Неверный email или пароль", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        if not check_password_hash(g.user["password_hash"], request.form["old"]):
            flash("Текущий пароль указан неверно", "error")
        elif len(request.form["new"]) < 8:
            flash("Новый пароль — не короче 8 символов", "error")
        else:
            db = get_db()
            db.execute("UPDATE users SET password_hash=? WHERE id=?",
                       (generate_password_hash(request.form["new"]), g.user["id"]))
            db.commit()
            flash("Пароль изменён", "ok")
            return redirect(url_for("dashboard"))
    return render_template("account.html")


# ==========================================================================
# Панель
# ==========================================================================
@app.route("/")
@login_required
def dashboard():
    q = request.args.get("q", "").strip().lower()
    level_f = request.args.get("level", "")
    rows = []
    for o in visible_objects():
        if q and q not in f"{o['name']} {o['address']} {o['client_name']}".lower():
            continue
        sm = object_summary(o)
        if level_f and sm["level"] != level_f:
            continue
        rows.append((o, sm))
    order = {"red": 0, "yellow": 1, "green": 2}
    rows.sort(key=lambda r: (order[r[1]["level"]], r[0]["name"]))
    totals = dict(
        objects=len(rows),
        red=sum(1 for _, s in rows if s["level"] == "red"),
        yellow=sum(1 for _, s in rows if s["level"] == "yellow"),
        green=sum(1 for _, s in rows if s["level"] == "green"),
        overdue=sum(s["tasks"]["overdue"] for _, s in rows),
        issues=sum(s["open_issues"] for _, s in rows),
        requests=sum(s["requests"] for _, s in rows),
    )
    return render_template("dashboard.html", rows=rows, totals=totals, q=q, level_f=level_f)


@app.route("/plan")
@login_required
def plan():
    """Сводный план-график работ по всем доступным объектам."""
    horizon = int(request.args.get("days", 60))
    side_f = request.args.get("side", "")
    items = []
    for o in visible_objects():
        for t in task_rows(o["id"]):
            if side_f and t["side"] != side_f:
                continue
            if t["status"] in ("overdue", "nodata") or (t["days"] is not None and t["days"] <= horizon):
                items.append((o, t))
    order = {"overdue": 0, "soon": 1, "ok": 2, "nodata": 3}
    items.sort(key=lambda x: (order[x[1]["status"]], x[1]["next_due"] or "9999"))
    return render_template("plan.html", items=items, horizon=horizon, side_f=side_f)


@app.route("/issues")
@login_required
def all_issues():
    status_f = request.args.get("status", "active")
    ids = [o["id"] for o in visible_objects()]
    if not ids:
        rows = []
    else:
        sql = ("SELECT i.*, o.name AS object_name, u.name AS author FROM issues i JOIN objects o ON o.id=i.object_id "
               "LEFT JOIN users u ON u.id=i.created_by WHERE i.object_id IN (%s)" % ",".join("?" * len(ids)))
        if status_f == "active":
            sql += " AND i.status!='resolved'"
        elif status_f in ISSUE_STATUS:
            sql += f" AND i.status='{status_f}'"
        sql += " ORDER BY CASE i.severity WHEN 'critical' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, i.created_at DESC"
        rows = get_db().execute(sql, ids).fetchall()
    return render_template("issues_all.html", rows=rows, status_f=status_f)


# ==========================================================================
# Объекты: создание и анкета
# ==========================================================================
@app.route("/objects/new", methods=["GET", "POST"])
@roles("admin", "engineer")
def object_new():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Укажите название объекта", "error")
        else:
            profile, systems = parse_object_form(request.form)
            cid = client_id_from_form(request.form)
            cur = db.execute(
                "INSERT INTO objects (client_id, name, address, profile, systems, created_by) VALUES (?,?,?,?,?,?)",
                (cid, name, request.form.get("address", "").strip(), json.dumps(profile, ensure_ascii=False),
                 json.dumps(systems, ensure_ascii=False), g.user["id"]))
            db.commit()
            sync_tasks(cur.lastrowid)
            flash("Объект создан. Сформированы чек-лист и график регламентных работ.", "ok")
            return redirect(url_for("object_view", object_id=cur.lastrowid))
    clients = db.execute("SELECT * FROM clients ORDER BY name").fetchall()
    return render_template("object_form.html", obj=None, profile={}, systems={}, clients=clients,
                           Q=norms.QUESTIONNAIRE, SYSTEMS=norms.SYSTEMS)


@app.route("/objects/<int:object_id>/edit", methods=["GET", "POST"])
@login_required
def object_edit(object_id):
    obj = get_object(object_id)
    db = get_db()
    if request.method == "POST":
        profile, systems = parse_object_form(request.form)
        cid = client_id_from_form(request.form) if is_provider() else obj["client_id"]
        db.execute("UPDATE objects SET name=?, address=?, client_id=?, profile=?, systems=?, updated_at=datetime('now') "
                   "WHERE id=?",
                   (request.form.get("name", obj["name"]).strip() or obj["name"],
                    request.form.get("address", "").strip(), cid, json.dumps(profile, ensure_ascii=False),
                    json.dumps(systems, ensure_ascii=False), object_id))
        db.commit()
        sync_tasks(object_id)
        flash("Анкета сохранена, график работ и чек-лист пересчитаны", "ok")
        return redirect(url_for("object_view", object_id=object_id))
    p, s = obj_data(obj)
    clients = db.execute("SELECT * FROM clients ORDER BY name").fetchall()
    return render_template("object_form.html", obj=obj, profile=p, systems=s, clients=clients,
                           Q=norms.QUESTIONNAIRE, SYSTEMS=norms.SYSTEMS)


@app.route("/objects/<int:object_id>/archive", methods=["POST"])
@roles("admin")
def object_archive(object_id):
    obj = get_object(object_id)
    db = get_db()
    db.execute("UPDATE objects SET archived=? WHERE id=?", (0 if obj["archived"] else 1, object_id))
    db.commit()
    flash("Объект перенесён в архив" if not obj["archived"] else "Объект возвращён из архива", "ok")
    return redirect(url_for("dashboard"))


@app.route("/objects/<int:object_id>")
@login_required
def object_view(object_id):
    obj = get_object(object_id)
    p, s = obj_data(obj)
    db = get_db()
    tasks = task_rows(object_id)
    issues = db.execute("SELECT * FROM issues WHERE object_id=? AND status!='resolved' "
                        "ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END LIMIT 8",
                        (object_id,)).fetchall()
    journal = db.execute("SELECT * FROM journal WHERE object_id=? ORDER BY date DESC, id DESC LIMIT 6",
                         (object_id,)).fetchall()
    return render_template("object_view.html", obj=obj, p=p, s=s, sm=object_summary(obj), tasks=tasks,
                           issues=issues, journal=journal, SYSTEMS=norms.SYSTEMS, TASKS=norms.TASKS_BY_CODE,
                           warnings=norms.warnings(p, s, date.today().year), tab="overview",
                           b=object_budget(obj), regs=regulations(obj))


# ==========================================================================
# Чек-лист
# ==========================================================================
@app.route("/objects/<int:object_id>/checklist", methods=["GET", "POST"])
@login_required
def object_checklist(object_id):
    obj = get_object(object_id)
    db = get_db()
    if request.method == "POST":
        now = datetime.now().isoformat(timespec="seconds")
        for item in checklist_rows(obj):
            no = item["no"]
            ans = request.form.get(f"a_{no}") or None
            comment = request.form.get(f"c_{no}", "").strip()
            if ans not in (None, "yes", "no", "na"):
                ans = None
            changed = ans != item["answer"] or comment != (item["comment"] or "")
            if changed:
                db.execute("INSERT INTO checklist (object_id, item_no, answer, comment, updated_by, updated_at) "
                           "VALUES (?,?,?,?,?,?) ON CONFLICT(object_id, item_no) DO UPDATE SET "
                           "answer=excluded.answer, comment=excluded.comment, updated_by=excluded.updated_by, "
                           "updated_at=excluded.updated_at", (object_id, no, ans, comment, g.user["id"], now))
            open_issue = db.execute("SELECT id FROM issues WHERE object_id=? AND checklist_no=? AND status!='resolved'",
                                    (object_id, no)).fetchone()
            if ans == "no" and not open_issue:
                add_issue(object_id, f"Чек-лист п. {no}: {item['text'][:150]}", comment, checklist_no=no)
            elif ans in ("yes", "na") and open_issue:
                db.execute("UPDATE issues SET status='resolved', resolved_at=datetime('now'), "
                           "resolution='Отмечено выполненным в чек-листе' WHERE id=?", (open_issue["id"],))
            save_upload(request.files.get(f"f_{no}"), object_id, "Чек-лист", "checklist", no)
        db.commit()
        flash("Чек-лист сохранён", "ok")
        return redirect(url_for("object_checklist", object_id=object_id))
    return render_template("object_checklist.html", obj=obj, rows=checklist_rows(obj), sm=object_summary(obj),
                           tab="checklist")


# ==========================================================================
# График работ
# ==========================================================================
@app.route("/objects/<int:object_id>/schedule")
@login_required
def object_schedule(object_id):
    obj = get_object(object_id)
    p, s = obj_data(obj)
    has_ops = {t["code"] for t in task_rows(object_id) if mt.ops_for_task(t["code"], s)[1]}
    return render_template("object_schedule.html", obj=obj, tasks=task_rows(object_id), SYSTEMS=norms.SYSTEMS, has_ops=has_ops,
                           RESULTS=RESULTS, sm=object_summary(obj), tab="schedule")


@app.route("/objects/<int:object_id>/tasks/<int:task_id>/done", methods=["POST"])
@login_required
def task_done(object_id, task_id):
    obj = get_object(object_id)
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE id=? AND object_id=?", (task_id, object_id)).fetchone() or abort(404)
    t = norms.TASKS_BY_CODE[row["code"]]
    d = request.form.get("date") or date.today().isoformat()
    if not parse_date(d) or parse_date(d) > date.today():
        flash("Дата выполнения не может быть в будущем", "error")
        return redirect(url_for("object_schedule", object_id=object_id))
    result = request.form.get("result") if request.form.get("result") in RESULTS else RESULTS[0]
    cur = db.execute(
        "INSERT INTO journal (object_id, date, task_code, system_code, work_type, description, result, performer, "
        "created_by) VALUES (?,?,?,?,?,?,?,?,?)",
        (object_id, d, row["code"], t.get("system"), "Плановая работа",
         t["title"] + (f". {request.form['note'].strip()}" if request.form.get("note", "").strip() else ""),
         result, request.form.get("performer", "").strip() or g.user["name"], g.user["id"]))
    jid = cur.lastrowid
    mark_task_done(object_id, row["code"], d)
    save_upload(request.files.get("file"), object_id, "Акт", "journal", jid)
    if result == "Неисправно":
        add_issue(object_id, f"Неисправность: {t['title']}", request.form.get("note", ""), "critical", journal_id=jid)
    db.commit()
    flash(f"Отмечено: {t['title']} — {ru_date(d)}", "ok")
    return redirect(url_for("object_schedule", object_id=object_id))


@app.route("/objects/<int:object_id>/tasks/<int:task_id>/edit", methods=["POST"])
@roles("admin", "engineer")
def task_edit(object_id, task_id):
    get_object(object_id)
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE id=? AND object_id=?", (task_id, object_id)).fetchone() or abort(404)
    per = request.form.get("period", "")
    side = request.form.get("side") if request.form.get("side") in SIDE_NAMES else row["side"]
    if per.isdigit() and 1 <= int(per) <= 120:
        db.execute("UPDATE tasks SET period_months=?, period_custom=1, side=? WHERE id=?", (int(per), side, task_id))
    else:
        db.execute("UPDATE tasks SET side=? WHERE id=?", (side, task_id))
    if request.form.get("reset"):
        db.execute("UPDATE tasks SET period_custom=0 WHERE id=?", (task_id,))
        db.commit()
        sync_tasks(object_id)
    db.commit()
    flash("Параметры работы обновлены", "ok")
    return redirect(url_for("object_schedule", object_id=object_id))


# ==========================================================================
# Журнал
# ==========================================================================
@app.route("/objects/<int:object_id>/journal", methods=["GET", "POST"])
@login_required
def object_journal(object_id):
    obj = get_object(object_id)
    db = get_db()
    p, s = obj_data(obj)
    if request.method == "POST":
        d = request.form.get("date") or date.today().isoformat()
        if not parse_date(d) or parse_date(d) > date.today():
            flash("Дата не может быть в будущем", "error")
            return redirect(url_for("object_journal", object_id=object_id))
        task_code = request.form.get("task_code") or None
        if task_code and task_code not in norms.TASKS_BY_CODE:
            task_code = None
        system_code = request.form.get("system_code") or (
            norms.TASKS_BY_CODE[task_code].get("system") if task_code else None)
        result = request.form.get("result") if request.form.get("result") in RESULTS else RESULTS[0]
        cur = db.execute(
            "INSERT INTO journal (object_id, date, task_code, system_code, work_type, description, result, performer, "
            "created_by) VALUES (?,?,?,?,?,?,?,?,?)",
            (object_id, d, task_code, system_code, request.form.get("work_type") or "Прочее",
             request.form.get("description", "").strip(), result,
             request.form.get("performer", "").strip() or g.user["name"], g.user["id"]))
        jid = cur.lastrowid
        if task_code:
            mark_task_done(object_id, task_code, d)
        save_upload(request.files.get("file"), object_id, "Акт", "journal", jid)
        if result == "Неисправно":
            sysname = norms.SYSTEMS.get(system_code, {}).get("name", "")
            add_issue(object_id, f"Неисправность: {sysname or request.form.get('work_type')}",
                      request.form.get("description", ""), "critical", journal_id=jid)
        db.commit()
        flash("Запись добавлена в журнал", "ok")
        return redirect(url_for("object_journal", object_id=object_id))
    sys_f = request.args.get("system", "")
    sql = "SELECT j.*, u.name AS author FROM journal j LEFT JOIN users u ON u.id=j.created_by WHERE j.object_id=?"
    args = [object_id]
    if sys_f:
        sql += " AND j.system_code=?"
        args.append(sys_f)
    entries = db.execute(sql + " ORDER BY j.date DESC, j.id DESC", args).fetchall()
    files = {}
    for f in db.execute("SELECT * FROM files WHERE object_id=? AND link_type='journal'", (object_id,)):
        files.setdefault(f["link_id"], []).append(f)
    tasks = task_rows(object_id)
    ops_by_j = {}
    texts = {c: t for ops in mt.OPS.values() for c, t, _, _ in ops}
    for r in db.execute("SELECT jo.* FROM journal_ops jo JOIN journal j ON j.id=jo.journal_id WHERE j.object_id=?",
                        (object_id,)):
        ops_by_j.setdefault(r["journal_id"], []).append(dict(text=texts.get(r["op_code"], r["op_code"]),
                                                             status=r["status"], note=r["note"]))
    return render_template("object_journal.html", ops_by_j=ops_by_j, OP_STATUS=OP_STATUS, obj=obj, entries=entries, files=files, s=s, tasks=tasks,
                           SYSTEMS=norms.SYSTEMS, TASKS=norms.TASKS_BY_CODE, WORK_TYPES=WORK_TYPES,
                           RESULTS=RESULTS, sys_f=sys_f, sm=object_summary(obj), tab="journal")


# ==========================================================================
# Замечания и заявки
# ==========================================================================
@app.route("/objects/<int:object_id>/issues", methods=["GET", "POST"])
@login_required
def object_issues(object_id):
    obj = get_object(object_id)
    db = get_db()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Опишите замечание кратко в поле «Суть»", "error")
        else:
            sev = request.form.get("severity") if request.form.get("severity") in SEVERITY else "medium"
            kind = "remark" if is_provider() else "request"
            add_issue(object_id, title, request.form.get("description", "").strip(), sev, kind,
                      request.form.get("due_date") or None)
            iid = db.execute("SELECT last_insert_rowid() id").fetchone()["id"]
            save_upload(request.files.get("file"), object_id, "Фото / документ", "issue", iid)
            db.commit()
            flash("Заявка отправлена обслуживающей организации" if kind == "request" else "Замечание добавлено", "ok")
        return redirect(url_for("object_issues", object_id=object_id))
    rows = db.execute("SELECT i.*, u.name AS author FROM issues i LEFT JOIN users u ON u.id=i.created_by "
                      "WHERE i.object_id=? ORDER BY i.status='resolved', "
                      "CASE i.severity WHEN 'critical' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, i.created_at DESC",
                      (object_id,)).fetchall()
    files = {}
    for f in db.execute("SELECT * FROM files WHERE object_id=? AND link_type='issue'", (object_id,)):
        files.setdefault(f["link_id"], []).append(f)
    return render_template("object_issues.html", obj=obj, rows=rows, files=files, sm=object_summary(obj),
                           tab="issues")


@app.route("/issues/<int:issue_id>/update", methods=["POST"])
@login_required
def issue_update(issue_id):
    db = get_db()
    iss = db.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone() or abort(404)
    get_object(iss["object_id"])
    status = request.form.get("status")
    if status not in ISSUE_STATUS:
        abort(400)
    if not is_provider() and not (iss["created_by"] == g.user["id"] or iss["kind"] == "remark"):
        abort(403)
    db.execute("UPDATE issues SET status=?, resolution=?, resolved_at=CASE WHEN ?='resolved' THEN datetime('now') "
               "ELSE NULL END WHERE id=?",
               (status, request.form.get("resolution", "").strip() or iss["resolution"], status, issue_id))
    save_upload(request.files.get("file"), iss["object_id"], "Фото / документ", "issue", issue_id)
    db.commit()
    flash("Статус обновлён", "ok")
    return redirect(request.form.get("back") or url_for("object_issues", object_id=iss["object_id"]))


# ==========================================================================
# Документы
# ==========================================================================
@app.route("/objects/<int:object_id>/files", methods=["GET", "POST"])
@login_required
def object_files(object_id):
    obj = get_object(object_id)
    db = get_db()
    if request.method == "POST":
        cat = request.form.get("category") if request.form.get("category") in FILE_CATEGORIES else "Прочее"
        n = 0
        for fs in request.files.getlist("files"):
            if save_upload(fs, object_id, cat):
                n += 1
        db.commit()
        flash(f"Загружено файлов: {n}" if n else "Файл не выбран", "ok" if n else "error")
        return redirect(url_for("object_files", object_id=object_id))
    rows = db.execute("SELECT f.*, u.name AS author FROM files f LEFT JOIN users u ON u.id=f.uploaded_by "
                      "WHERE f.object_id=? ORDER BY f.uploaded_at DESC", (object_id,)).fetchall()
    return render_template("object_files.html", obj=obj, rows=rows, CATS=FILE_CATEGORIES, sm=object_summary(obj),
                           tab="files")


@app.route("/files/<int:file_id>")
@login_required
def file_download(file_id):
    f = get_db().execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone() or abort(404)
    get_object(f["object_id"])
    return send_from_directory(app.config["UPLOAD_DIR"], f["stored_name"], as_attachment=True,
                               download_name=f["original_name"])


@app.route("/files/<int:file_id>/delete", methods=["POST"])
@login_required
def file_delete(file_id):
    db = get_db()
    f = db.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone() or abort(404)
    get_object(f["object_id"])
    if g.user["role"] != "admin" and f["uploaded_by"] != g.user["id"]:
        abort(403)
    db.execute("DELETE FROM files WHERE id=?", (file_id,))
    db.commit()
    try:
        os.remove(os.path.join(app.config["UPLOAD_DIR"], f["stored_name"]))
    except OSError:
        pass
    flash("Файл удалён", "ok")
    return redirect(request.form.get("back") or url_for("object_files", object_id=f["object_id"]))


# ==========================================================================
# Отчёт для печати
# ==========================================================================
@app.route("/objects/<int:object_id>/report")
@login_required
def object_report(object_id):
    obj = get_object(object_id)
    p, s = obj_data(obj)
    issues = get_db().execute("SELECT * FROM issues WHERE object_id=? AND status!='resolved' ORDER BY severity",
                              (object_id,)).fetchall()
    return render_template("report.html", obj=obj, p=p, s=s, sm=object_summary(obj), tasks=task_rows(object_id),
                           cl=checklist_rows(obj), issues=issues, SYSTEMS=norms.SYSTEMS, Q=norms.QUESTIONNAIRE,
                           warnings=norms.warnings(p, s, date.today().year), now=datetime.now(),
                           b=object_budget(obj), regs=regulations(obj))



# ==========================================================================
# Регламент ТО по ГОСТ: акты с перечнем операций
# ==========================================================================
OP_STATUS = {"ok": "Выполнено, норма", "defect": "Выявлена неисправность", "skip": "Не выполнялось"}


def ops_last_done(object_id):
    rows = get_db().execute(
        "SELECT jo.op_code, MAX(j.date) d FROM journal_ops jo JOIN journal j ON j.id=jo.journal_id "
        "WHERE j.object_id=? AND jo.status IN ('ok','defect') GROUP BY jo.op_code", (object_id,))
    return {r["op_code"]: r["d"] for r in rows}


def regulations(obj):
    """Все перечни операций по системам объекта со статусами."""
    p, s = obj_data(obj)
    last = ops_last_done(obj["id"])
    out = []
    seen = set()
    for code in s:
        if code not in norms.SYSTEMS:
            continue
        key = mt.ops_key(code, s)
        if key in seen or key not in mt.OPS:
            continue
        seen.add(key)
        rows = mt.ops_status(mt.OPS[key], last)
        out.append(dict(system=code, key=key, name=norms.SYSTEMS[code]["name"], ops=rows,
                        overdue=sum(1 for r in rows if r["status"] == "overdue"),
                        nodata=sum(1 for r in rows if r["status"] == "nodata")))
    return out


def price_settings():
    row = get_db().execute("SELECT value FROM settings WHERE key='prices'").fetchone()
    return json.loads(row["value"]) if row else {"coef": 1.0, "items": {}}


def object_budget(obj):
    p, s = obj_data(obj)
    ps = price_settings()
    old = len(norms.over_service_life(s, date.today().year))
    return mt.budget(p, s, task_rows(obj["id"]), ps.get("items"), ps.get("coef", 1.0), old)


@app.template_filter("rub")
def rub(v):
    return f"{round(v):,}".replace(",", " ") + " ₽"


@app.route("/objects/<int:object_id>/tasks/<int:task_id>/act", methods=["GET", "POST"])
@login_required
def task_act(object_id, task_id):
    obj = get_object(object_id)
    db = get_db()
    p, s = obj_data(obj)
    row = db.execute("SELECT * FROM tasks WHERE id=? AND object_id=?", (task_id, object_id)).fetchone() or abort(404)
    t = norms.TASKS_BY_CODE[row["code"]]
    key, ops = mt.ops_for_task(row["code"], s)
    if not ops:
        return redirect(url_for("object_schedule", object_id=object_id))
    statuses = mt.ops_status(ops, ops_last_done(object_id))
    if request.method == "POST":
        d = request.form.get("date") or date.today().isoformat()
        if not parse_date(d) or parse_date(d) > date.today():
            flash("Дата не может быть в будущем", "error")
            return redirect(request.path)
        marks = {}
        for code, text, per, ref in ops:
            st = request.form.get("st_" + code)
            if st in OP_STATUS:
                marks[code] = (st, request.form.get("n_" + code, "").strip(), text)
        done = [c for c, v in marks.items() if v[0] != "skip"]
        if not done:
            flash("Отметьте хотя бы одну выполненную операцию", "error")
            return redirect(request.path)
        defects = [c for c, v in marks.items() if v[0] == "defect"]
        result = RESULTS[1] if defects else RESULTS[0]
        summary = f"{t['title']}: выполнено операций — {len(done)}" + (f", неисправностей — {len(defects)}" if defects else "")
        if request.form.get("note", "").strip():
            summary += ". " + request.form["note"].strip()
        cur = db.execute(
            "INSERT INTO journal (object_id, date, task_code, system_code, work_type, description, result, performer, "
            "created_by) VALUES (?,?,?,?,?,?,?,?,?)",
            (object_id, d, row["code"], t.get("system"), "Техническое обслуживание", summary, result,
             request.form.get("performer", "").strip() or g.user["name"], g.user["id"]))
        jid = cur.lastrowid
        for code, (st, note, text) in marks.items():
            db.execute("INSERT INTO journal_ops (journal_id, op_code, status, note) VALUES (?,?,?,?)",
                       (jid, code, st, note))
            if st == "defect":
                sysname = norms.SYSTEMS.get(t.get("system"), {}).get("name", "")
                add_issue(object_id, f"{sysname}: {text[:150]}", note, "medium", journal_id=jid)
            if st != "skip" and mt.OP_TASK.get(code):
                mark_task_done(object_id, mt.OP_TASK[code], d)
        mark_task_done(object_id, row["code"], d)
        save_upload(request.files.get("file"), object_id, "Акт", "journal", jid)
        db.commit()
        flash(f"Акт ТО сохранён: {len(done)} операций" + (f", замечаний: {len(defects)}" if defects else ""), "ok")
        return redirect(url_for("journal_act", journal_id=jid))
    return render_template("task_act.html", obj=obj, task=t, row=row, ops=statuses, OP_STATUS=OP_STATUS,
                           sm=object_summary(obj), tab="schedule")


@app.route("/journal/<int:journal_id>/act")
@login_required
def journal_act(journal_id):
    db = get_db()
    j = db.execute("SELECT j.*, u.name AS author FROM journal j LEFT JOIN users u ON u.id=j.created_by WHERE j.id=?",
                   (journal_id,)).fetchone() or abort(404)
    obj = get_object(j["object_id"])
    p, s = obj_data(obj)
    texts = {}
    for key, ops in mt.OPS.items():
        for code, text, per, ref in ops:
            texts[code] = (text, ref)
    ops = [dict(code=r["op_code"], status=r["status"], note=r["note"], text=texts.get(r["op_code"], (r["op_code"], ""))[0],
                ref=texts.get(r["op_code"], ("", ""))[1])
           for r in db.execute("SELECT * FROM journal_ops WHERE journal_id=? ORDER BY id", (journal_id,))]
    files = db.execute("SELECT * FROM files WHERE link_type='journal' AND link_id=?", (journal_id,)).fetchall()
    return render_template("act_print.html", obj=obj, j=j, ops=ops, files=files, OP_STATUS=OP_STATUS,
                           TASKS=norms.TASKS_BY_CODE, SYSTEMS=norms.SYSTEMS, now=datetime.now())


@app.route("/objects/<int:object_id>/regulations")
@login_required
def object_regulations(object_id):
    obj = get_object(object_id)
    task_by_system = {}
    for t in task_rows(object_id):
        sc = mt.TASK_OPS.get(t["code"])
        if sc:
            task_by_system.setdefault(sc, []).append(t)
    return render_template("object_regulations.html", obj=obj, regs=regulations(obj), task_by_system=task_by_system,
                           sm=object_summary(obj), tab="regulations")


@app.route("/objects/<int:object_id>/budget")
@login_required
def object_budget_view(object_id):
    obj = get_object(object_id)
    return render_template("object_budget.html", obj=obj, b=object_budget(obj), NOTE=mt.PRICES_NOTE,
                           sm=object_summary(obj), tab="budget")


@app.route("/prices", methods=["GET", "POST"])
@roles("admin", "engineer")
def prices():
    ps = price_settings()
    if request.method == "POST":
        if g.user["role"] != "admin":
            abort(403)
        items = {}
        for it in mt.PRICES:
            c = it["code"]
            ov = {}
            for f in ("min", "max", "mult"):
                v = request.form.get(f"{f}_{c}", "").replace(",", ".").strip()
                try:
                    ov[f] = float(v)
                except ValueError:
                    pass
            if ov:
                items[c] = ov
        try:
            coef = float(request.form.get("coef", "1").replace(",", "."))
        except ValueError:
            coef = 1.0
        db = get_db()
        db.execute("INSERT INTO settings (key, value) VALUES ('prices', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                   (json.dumps({"coef": coef, "items": items}),))
        db.commit()
        flash("Цены сохранены — бюджеты объектов пересчитаны", "ok")
        return redirect(url_for("prices"))
    return render_template("prices.html", items=mt.apply_overrides(ps.get("items")), coef=ps.get("coef", 1.0),
                           NOTE=mt.PRICES_NOTE)

# ==========================================================================
# Администрирование
# ==========================================================================
@app.route("/admin/users", methods=["GET", "POST"])
@roles("admin")
def admin_users():
    db = get_db()
    if request.method == "POST":
        email, name, role = request.form.get("email", "").strip().lower(), request.form.get("name", "").strip(), \
            request.form.get("role")
        pwd = request.form.get("password") or secrets.token_urlsafe(9)
        cid = request.form.get("client_id")
        if role not in ROLE_NAMES or not email or not name:
            flash("Заполните email, имя и роль", "error")
        elif role == "client" and not cid:
            flash("Для эксплуатанта выберите организацию", "error")
        elif db.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            flash("Пользователь с таким email уже есть", "error")
        else:
            create_user(email, pwd, name, role, int(cid) if role == "client" else None,
                        request.form.get("phone", "").strip())
            flash(f"Пользователь создан. Логин: {email}  Пароль: {pwd} — передайте его пользователю.", "ok")
        return redirect(url_for("admin_users"))
    users = db.execute("SELECT u.*, c.name AS client_name FROM users u LEFT JOIN clients c ON c.id=u.client_id "
                       "ORDER BY u.role, u.name").fetchall()
    clients = db.execute("SELECT * FROM clients ORDER BY name").fetchall()
    return render_template("admin_users.html", users=users, clients=clients)


@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@roles("admin")
def admin_user_toggle(user_id):
    if user_id == g.user["id"]:
        flash("Нельзя отключить самого себя", "error")
    else:
        db = get_db()
        db.execute("UPDATE users SET active=1-active WHERE id=?", (user_id,))
        db.commit()
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/reset", methods=["POST"])
@roles("admin")
def admin_user_reset(user_id):
    pwd = secrets.token_urlsafe(9)
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone() or abort(404)
    db.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(pwd), user_id))
    db.commit()
    flash(f"Новый пароль для {u['email']}: {pwd}", "ok")
    return redirect(url_for("admin_users"))


@app.route("/admin/clients", methods=["GET", "POST"])
@roles("admin", "engineer")
def admin_clients():
    db = get_db()
    if request.method == "POST":
        f = request.form
        if not f.get("name", "").strip():
            flash("Укажите название организации", "error")
        elif f.get("id"):
            db.execute("UPDATE clients SET name=?, inn=?, contact_name=?, phone=?, email=? WHERE id=?",
                       (f["name"].strip(), f.get("inn"), f.get("contact_name"), f.get("phone"), f.get("email"),
                        f["id"]))
        else:
            db.execute("INSERT INTO clients (name, inn, contact_name, phone, email) VALUES (?,?,?,?,?)",
                       (f["name"].strip(), f.get("inn"), f.get("contact_name"), f.get("phone"), f.get("email")))
        db.commit()
        return redirect(url_for("admin_clients"))
    clients = db.execute("SELECT c.*, (SELECT COUNT(*) FROM objects o WHERE o.client_id=c.id AND o.archived=0) n_obj, "
                         "(SELECT COUNT(*) FROM users u WHERE u.client_id=c.id) n_users FROM clients c ORDER BY name"
                         ).fetchall()
    return render_template("admin_clients.html", clients=clients)


@app.errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403, msg="Нет доступа к этой странице"), 403


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, msg="Страница не найдена"), 404


@app.errorhandler(413)
def too_large(_e):
    return render_template("error.html", code=413,
                           msg=f"Файл слишком большой (максимум {app.config['MAX_CONTENT_LENGTH'] // 1048576} МБ)"), 413


# ==========================================================================
# Команды:  flask --app app init-db | create-admin | seed-demo
# ==========================================================================
@app.cli.command("init-db")
def cmd_init_db():
    init_db()
    click.echo("База данных готова: " + app.config["DATABASE"])


@app.cli.command("create-admin")
@click.option("--email", prompt=True)
@click.option("--name", prompt="Имя")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
def cmd_create_admin(email, name, password):
    init_db()
    create_user(email, password, name, "admin")
    click.echo("Администратор создан")


@app.cli.command("seed-demo")
def cmd_seed_demo():
    """Демо-данные: эксплуатант, два объекта, пользователи."""
    import seed
    init_db()
    seed.run(get_db())
    click.echo("Демо-данные загружены. Вход: admin@demo.ru / demo12345, client@demo.ru / demo12345")


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", 5000)))
