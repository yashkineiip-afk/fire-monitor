"""Демо-данные, чтобы посмотреть систему «в деле». Запуск: flask --app app seed-demo"""
import json
from datetime import date, timedelta

from werkzeug.security import generate_password_hash


def run(db):
    if db.execute("SELECT 1 FROM users WHERE email='admin@demo.ru'").fetchone():
        return
    pw = generate_password_hash("demo12345")
    cid = db.execute("INSERT INTO clients (name, inn, contact_name, phone) VALUES (?,?,?,?)",
                     ("ООО «Бизнес-Парк Север»", "7700000000", "Иванов И. И.", "+7 900 000-00-00")).lastrowid
    db.execute("INSERT INTO users (email, password_hash, name, role) VALUES (?,?,?,?)",
               ("admin@demo.ru", pw, "Руководитель (демо)", "admin"))
    db.execute("INSERT INTO users (email, password_hash, name, role) VALUES (?,?,?,?)",
               ("engineer@demo.ru", pw, "Инженер Петров (демо)", "engineer"))
    db.execute("INSERT INTO users (email, password_hash, name, role, client_id) VALUES (?,?,?,?,?)",
               ("client@demo.ru", pw, "Иванов И. И. (эксплуатант)", "client", cid))

    office_p = {"purpose": "Офисный центр", "usage_right": "Собственник", "responsible_name": "Иванов И. И.",
                "responsible_position": "Главный инженер", "responsible_phone": "+7 900 000-00-00",
                "fclass": "Ф4.3 — Органы управления, офисы, банки, НИИ, редакции", "floors": "9", "underground": "1",
                "height_m": "28", "area_m2": "12500", "fire_resistance": "II", "constr_class": "С0",
                "year_built": "2012", "max_people": "600", "workplaces10": True, "night_stay": True, "mgn": True,
                "has_prod_storage": False, "categories": "", "categories_ab": False, "declaration": "Да",
                "risk_calc": False, "stu": False, "facade_banners": True, "smoking_place": True, "notes": ""}
    office_s = {"aps": {"kind": "Адресная", "brand": "Рубеж-2ОП", "detectors": "840", "year": "2012", "life": "10"},
                "soue": {"type": "3", "brand": "Соната", "units": "160", "year": "2012", "life": "10"},
                "smoke": {"kind": "дымоудаление, подпор", "units": "26", "year": "2012", "life": "15"},
                "vpv": {"cranes": "36"}, "pumps": {"units": "2"},
                "outer_water": {"kind": "Пожарные гидранты", "count": "2", "distance": "80"},
                "extinguishers": {"count": "120", "types": "ОП-4, ОУ-3"}, "fire_doors": {"count": "48"},
                "emergency_light": {"count": "210"}, "ventilation": {"ozk": True, "ozk_count": "14"}}
    whs_p = {"purpose": "Склад непродовольственных товаров", "usage_right": "Арендатор",
             "responsible_name": "Сидоров П. П.", "fclass": "Ф5.2 — Складские здания, стоянки, архивы, книгохранилища",
             "floors": "1", "height_m": "12", "area_m2": "4800", "fire_resistance": "IV", "constr_class": "С0",
             "year_built": "2018", "max_people": "25", "has_prod_storage": True, "categories": "В2, В3",
             "declaration": "Не знаю", "smoking_place": True}
    whs_s = {"aps": {"kind": "Адресно-аналоговая", "year": "2018", "life": "10"},
             "aupt": {"kind": "Водяное спринклерное", "rooms": "складской зал", "area": "4200", "year": "2018", "life": "10"},
             "soue": {"type": "2", "year": "2018", "life": "10"},
             "extinguishers": {"count": "30", "types": "ОП-5"}, "fireproof": {"what": "металлоконструкции", "area": "2600", "year": "2018", "life": "10"},
             "ladders": {"count": "2"}}
    oid1 = db.execute("INSERT INTO objects (client_id, name, address, profile, systems) VALUES (?,?,?,?,?)",
                      (cid, "БЦ «Север», корпус А", "г. Москва, ул. Примерная, д. 1",
                       json.dumps(office_p, ensure_ascii=False), json.dumps(office_s, ensure_ascii=False))).lastrowid
    oid2 = db.execute("INSERT INTO objects (client_id, name, address, profile, systems) VALUES (?,?,?,?,?)",
                      (cid, "Склад №2", "Московская обл., г. Химки, Промзона, стр. 5",
                       json.dumps(whs_p, ensure_ascii=False), json.dumps(whs_s, ensure_ascii=False))).lastrowid
    db.commit()

    # генерация работ и немного истории
    from app import sync_tasks
    for oid in (oid1, oid2):
        sync_tasks(oid)
    t = date.today()
    history = {oid1: {"aps_to": 20, "soue_to": 20, "smoke_to": 45, "vpv_check": 170, "vpv_hoses": 300,
                      "pumps_check": 25, "ext_inspect": 80, "ext_annual": 340, "evac_drill": 200,
                      "instr_repeat": 150, "spz_plan": 320},
               oid2: {"aps_to": 10, "aupt_to": 10, "soue_to": 10, "fireproof_check": 400, "ladders_test": 900}}
    for oid, items in history.items():
        for code, days_ago in items.items():
            d = (t - timedelta(days=days_ago)).isoformat()
            db.execute("UPDATE tasks SET last_done=? WHERE object_id=? AND code=?", (d, oid, code))
            db.execute("INSERT INTO journal (object_id, date, task_code, work_type, description, result, performer) "
                       "VALUES (?,?,?,?,?,?,?)", (oid, d, code, "Плановая работа", "Выполнено по графику",
                                                  "Исправно / выполнено", "Инженер Петров"))
    for no, ans in [(1, "yes"), (2, "yes"), (3, "yes"), (4, "yes"), (9, "yes"), (14, "yes"), (16, "no"),
                    (20, "yes"), (29, "yes"), (13, "no")]:
        db.execute("INSERT INTO checklist (object_id, item_no, answer, updated_at) VALUES (?,?,?,datetime('now'))",
                   (oid1, no, ans))
    # акт ТО АПС с операциями по ГОСТ
    d = (t - timedelta(days=20)).isoformat()
    jid = db.execute("INSERT INTO journal (object_id, date, task_code, system_code, work_type, description, result, performer) "
                     "VALUES (?,?,?,?,?,?,?,?)", (oid1, d, "aps_to", "aps", "Техническое обслуживание",
                     "Регламентное ТО АПС: выполнено операций — 4, неисправностей — 1", "Выполнено с замечаниями",
                     "Инженер Петров")).lastrowid
    for code, st, note in [("aps_ppkp_insp", "ok", ""), ("aps_ibe_insp", "ok", ""), ("aps_ppkp_func", "ok", ""),
                           ("aps_ibe_func", "defect", "АКБ 12 В: 12,4 В — требуется замена")]:
        db.execute("INSERT INTO journal_ops (journal_id, op_code, status, note) VALUES (?,?,?,?)", (jid, code, st, note))
    db.execute("INSERT INTO issues (object_id, title, description, severity, journal_id) VALUES (?,?,?,?,?)",
               (oid1, "АПС: замена АКБ в ИБЭ", "АКБ 12 В: 12,4 В", "medium", jid))
    db.execute("INSERT INTO issues (object_id, title, description, severity, checklist_no) VALUES (?,?,?,?,?)",
               (oid1, "Чек-лист п. 16: не заделаны кабельные проходки на 3 этаже", "Кабельный лоток у лифтового холла",
                "medium", 16))
    db.execute("INSERT INTO issues (object_id, title, description, severity, checklist_no) VALUES (?,?,?,?,?)",
               (oid1, "Чек-лист п. 13: нет документов на баннер фасада", "", "low", 13))
    db.execute("INSERT INTO issues (object_id, title, description, severity, kind) VALUES (?,?,?,?,?)",
               (oid2, "Не закрывается противопожарная дверь в рампе", "Сломан доводчик", "critical", "request"))
    db.commit()
