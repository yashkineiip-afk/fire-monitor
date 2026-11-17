"""Сквозная проверка: python -m pytest -q  (или python tests/test_app.py)"""
import io
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = tempfile.mkdtemp()
os.environ["DATABASE"] = os.path.join(TMP, "t.db")
os.environ["UPLOAD_DIR"] = os.path.join(TMP, "up")

import app as appmod  # noqa: E402

app = appmod.app
app.config["TESTING"] = True


def csrf(c, url):
    html = c.get(url).get_data(as_text=True)
    m = re.search(r'name="csrf" value="([^"]+)"', html)
    return m.group(1) if m else ""


def login(c, email, pwd):
    t = csrf(c, "/login")
    r = c.post("/login", data={"email": email, "password": pwd, "csrf": t})
    assert r.status_code == 302, r.get_data(as_text=True)[:500]


def test_full_flow():
    c = app.test_client()
    # первый запуск
    assert c.get("/").status_code == 302
    t = csrf(c, "/setup")
    r = c.post("/setup", data={"email": "boss@firm.ru", "name": "Босс", "password": "secret123", "csrf": t})
    assert r.status_code == 302
    login(c, "boss@firm.ru", "secret123")
    # без CSRF — отказ
    assert c.post("/admin/clients", data={"name": "X"}).status_code == 400

    # объект с анкетой
    t = csrf(c, "/objects/new")
    form = {"csrf": t, "name": "ТЦ Тест", "address": "ул. Ленина, 1", "new_client": "ООО Арендатор",
            "p_fclass": "Ф1.1 — Детские сады, больницы, дома престарелых, спальные корпуса интернатов",
            "p_max_people": "120", "p_night_stay": "on", "p_declaration": "Да",
            "sys_aps": "on", "s_aps_year": "2010", "s_aps_life": "10",
            "sys_vpv": "on", "sys_extinguishers": "on", "s_extinguishers_count": "10",
            "sys_ladders": "on", "sys_ventilation": "on", "s_ventilation_ozk": "on"}
    r = c.post("/objects/new", data=form)
    assert r.status_code == 302, r.get_data(as_text=True)[:800]
    oid = int(r.headers["Location"].rstrip("/").split("/")[-1])

    page = c.get(f"/objects/{oid}").get_data(as_text=True)
    assert "дублирование сигнала" in page          # Ф1.1 без вывода на пульт
    assert "Срок службы истёк" in page              # АПС 2010 + 10 лет

    sched = c.get(f"/objects/{oid}/schedule").get_data(as_text=True)
    for title in ["Регламентное ТО АПС", "Проверка работоспособности ВПВ", "Практическая тренировка",
                  "Эксплуатационные испытания пожарных лестниц", "Ежегодные испытания систем",
                  "Проверка огнезадерживающих"]:
        assert title in sched, title
    assert "Регламентное ТО АУПТ" not in sched

    with app.app_context():
        db = appmod.get_db()
        task = db.execute("SELECT id FROM tasks WHERE object_id=? AND code='vpv_check'", (oid,)).fetchone()
    t = csrf(c, f"/objects/{oid}/schedule")
    r = c.post(f"/objects/{oid}/tasks/{task['id']}/done",
               data={"csrf": t, "date": "2026-10-01", "result": "Неисправно", "note": "нет давления",
                     "file": (io.BytesIO(b"act"), "akt.pdf")}, content_type="multipart/form-data")
    assert r.status_code == 302
    assert "Неисправность" in c.get(f"/objects/{oid}/issues").get_data(as_text=True)
    assert "akt.pdf" in c.get(f"/objects/{oid}/journal").get_data(as_text=True)

    # чек-лист: «нет» создаёт замечание, «да» закрывает
    t = csrf(c, f"/objects/{oid}/checklist")
    c.post(f"/objects/{oid}/checklist", data={"csrf": t, "a_1": "yes", "a_16": "no", "c_16": "кабели 3 эт."})
    assert "Чек-лист п. 16" in c.get(f"/objects/{oid}/issues").get_data(as_text=True)
    t = csrf(c, f"/objects/{oid}/checklist")
    c.post(f"/objects/{oid}/checklist", data={"csrf": t, "a_1": "yes", "a_16": "yes"})
    with app.app_context():
        st = appmod.get_db().execute("SELECT status FROM issues WHERE checklist_no=16").fetchone()["status"]
    assert st == "resolved"

    # кабинет эксплуатанта
    with app.app_context():
        cid = appmod.get_db().execute("SELECT id FROM clients WHERE name='ООО Арендатор'").fetchone()["id"]
    t = csrf(c, "/admin/users")
    r = c.post("/admin/users", data={"csrf": t, "name": "Арендатор", "email": "rent@x.ru", "role": "client",
                                    "client_id": str(cid), "password": "rentpass1"})
    assert r.status_code == 302
    # второй объект другого эксплуатанта
    t = csrf(c, "/objects/new")
    r = c.post("/objects/new", data={"csrf": t, "name": "Чужой склад", "new_client": "ООО Другое"})
    other = int(r.headers["Location"].rstrip("/").split("/")[-1])

    for url in ["/", "/plan", "/issues", "/admin/users", "/admin/clients", f"/objects/{oid}/edit",
                f"/objects/{oid}/files", f"/objects/{oid}/report", "/account"]:
        assert c.get(url).status_code == 200, url

    c2 = app.test_client()
    login(c2, "rent@x.ru", "rentpass1")
    home = c2.get("/").get_data(as_text=True)
    assert "ТЦ Тест" in home and "Чужой склад" not in home
    assert c2.get(f"/objects/{other}").status_code == 403
    assert c2.get("/admin/users").status_code == 403
    assert c2.get("/objects/new").status_code == 403
    t = csrf(c2, f"/objects/{oid}/issues")
    c2.post(f"/objects/{oid}/issues", data={"csrf": t, "title": "Сработала АПС ночью", "severity": "critical"})
    assert "Заявка" in c.get("/issues").get_data(as_text=True)
    for url in ["/plan", "/issues", f"/objects/{oid}/checklist", f"/objects/{oid}/schedule",
                f"/objects/{oid}/journal", f"/objects/{oid}/report"]:
        assert c2.get(url).status_code == 200, url


if __name__ == "__main__":
    test_full_flow()
    print("OK")
