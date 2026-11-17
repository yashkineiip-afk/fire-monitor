"""
Регламенты ТО по ГОСТ (что конкретно делается с каждой системой) и ценовая модель бюджета.

Только данные + две функции расчёта. Этот же файл выгружается в JSON для демо-версии
(скрипт build_demo.py), поэтому функции qty/цены описаны строковыми ключами.

Периодичность операций: месяцы. 0 — «по ТД изготовителя / при необходимости»,
-1 — ежедневно, -2 — еженедельно (контроль дежурным персоналом).
"""
from datetime import date

PERIOD_LABELS = {-1: "ежедневно", -2: "еженедельно", 0: "по ТД / при необходимости"}

G_SPS = "ГОСТ Р 59638-2021, табл. 1"
G_SOUE = "ГОСТ Р 59639-2021, табл. 1"
G_AUP_W = "ГОСТ Р 59636-2021, прил. В"
G_AUP_G = "ГОСТ Р 59636-2021, прил. Г"
G_AUP_P = "ГОСТ Р 59636-2021, прил. Д"
G_AUP_A = "ГОСТ Р 59636-2021, прил. Е"
G_VPV = "ГОСТ Р 59643-2021, прил. А"
G_EXT = "ГОСТ Р 59641-2021, п. 5.1"

# Операции ТО по системам: (код, что сделать, период мес., основание)
OPS = {
    "aps": [
        ("aps_ppkp_insp", "Осмотр ППКП: индикация дежурного режима, журнал событий прибора, неисправности и отключения, повреждения корпусов", 1, G_SPS + ", прил. Г.4"),
        ("aps_ibe_insp", "Осмотр источников бесперебойного электропитания: индикация дежурного режима", 1, G_SPS + ", прил. Г.3"),
        ("aps_ppkp_func", "Контроль функционирования ППКП и функциональных модулей", 3, G_SPS),
        ("aps_ibe_func", "Контроль функционирования ИБЭ: переход на резервное питание, состояние АКБ (клеммы, коррозия, электролит, корпус)", 6, G_SPS),
        ("aps_ip_insp", "Осмотр извещателей и выносных индикаторов: маркировка, нет окраски и повреждений, нет перепланировок, свободно 0,5 м вокруг ИП; ручные ИП не загромождены", 6, G_SPS + ", прил. Г.1–Г.2"),
        ("aps_ip_func", "Контроль функционирования извещателей (проверка срабатывания)", 12, G_SPS),
        ("aps_io", "Осмотр и контроль функционирования модулей ввода/вывода", 12, G_SPS + ", прил. Г.5"),
        ("aps_complex", "Комплексные испытания на работоспособность СПС с актом (не более 15 мес. между испытаниями)", 12, G_SPS + ", прил. Б, В"),
        ("aps_akb", "Замена АКБ (ёмкость < 80 % номинальной или срок до 10 лет)", 0, "ГОСТ Р 59638-2021, п. 6.6"),
        ("aps_faults", "Устранение неисправностей и ложных срабатываний, восстановление дежурного режима", 0, G_SPS),
    ],
    "soue": [
        ("soue_clean", "Обслуживание световых, звуковых и речевых оповещателей: очистка, протирка", 3, G_SOUE),
        ("soue_power", "Проверка основного и резервного питания, автоматического переключения с основного ввода на резервный и обратно", 3, G_SOUE),
        ("soue_comp", "Проверка работоспособности отдельных компонентов (не менее 25 % за квартал, каждый квартал — разные)", 3, "ГОСТ Р 59639-2021, п. 6.6.1"),
        ("soue_func", "Проверка работоспособности СОУЭ: запуск, алгоритм и очерёдность, уровень звука, контроль линий (не более 7 мес. между проверками)", 6, "ГОСТ Р 59639-2021, табл. 1, прил. Б"),
        ("soue_replace", "Замена технических средств и ресурсных элементов (срок службы не более 10 лет)", 0, "ГОСТ Р 59639-2021, п. 6.7.4"),
    ],
    "aupt_water": [
        ("aw_daily", "Внешний осмотр трубопроводов и узлов, показания приборов, положение запорных устройств (дежурный персонал)", -1, G_AUP_W),
        ("aw_weekly", "Питание основное/резервное и автопереключение, узлы управления, насосная установка, компрессор", -2, G_AUP_W),
        ("aw_cmd", "Проверка выдачи команд при срабатывании: сигнализация, оповещение, вентиляция и дымоудаление, технологическое оборудование", 1, G_AUP_W),
        ("aw_fault", "Проверка сигнализации о неисправности АУП и её технических средств", 1, G_AUP_W),
        ("aw_tank", "Проверка работоспособности гидропневматического бака", 1, G_AUP_W),
        ("aw_docs", "Наличие документации, схем, табличек и шильдиков на посту, в насосной, на запорных устройствах", 1, G_AUP_W),
        ("aw_fix", "Проверка прочности крепления технических средств и трубопроводов", 1, G_AUP_W),
        ("aw_manual", "Проверка работоспособности при ручном (местном, дистанционном) пуске без подачи воды через ороситель", 3, G_AUP_W),
        ("aw_valves", "Проверка всех запорных устройств (открытие — закрытие), в т.ч. с электроприводом", 3, G_AUP_W),
        ("aw_auto", "Проверка работоспособности в автоматическом режиме без подачи воды через ороситель", 3, G_AUP_W),
        ("aw_sprinklers", "Внешний осмотр оросителей и пеногенераторов, очистка от пыли и грязи", 3, G_AUP_W),
        ("aw_ground", "Проверка сопротивления защитного заземления", 12, G_AUP_W),
        ("aw_flush", "Промывка трубопроводов дренчерных АУП; смена воды в гидробаке и резервуаре", 12, G_AUP_W),
        ("aw_ekm", "Проверка настройки ЭКМ, сигнализаторов давления и расхода; поверка КИП", 12, G_AUP_W),
        ("aw_revision", "Ревизия узлов управления и затворов, сопротивление изоляции, проверка расхода и давления у диктующего оросителя", 36, G_AUP_W),
        ("aw_hydro", "Гидравлические и пневматические испытания трубопроводов (2 года — в агрессивной среде)", 36, G_AUP_W),
    ],
    "aupt_gas": [
        ("ag_insp", "Внешний осмотр: повреждения, загрязнения, крепление, сохранность пломб", 1, G_AUP_G),
        ("ag_press", "Положение запорной арматуры, давление в побудительной сети и пусковых баллонах", 1, G_AUP_G),
        ("ag_mass", "Контроль массы ГОТВ и/или давления газа-вытеснителя", 1, G_AUP_G),
        ("ag_prof", "Профилактические работы", 1, G_AUP_G),
        ("ag_func", "Проверка работоспособности в ручном и автоматическом режимах без выпуска ОТВ (пиропатроны отключены или имитаторы)", 6, G_AUP_G),
        ("ag_metro", "Метрологическая проверка контрольно-измерительных приборов", 12, G_AUP_G),
        ("ag_room", "Соответствие пожарной нагрузки, объёма и герметичности помещений проекту", 12, G_AUP_G),
        ("ag_hydro", "Гидравлические (пневматические) испытания трубопроводов", 60, G_AUP_G),
        ("ag_cert", "Техническое освидетельствование АУП", 60, G_AUP_G),
    ],
    "aupt_powder": [
        ("ap_insp", "Внешний осмотр модулей: повреждения, крепление, пломбы, ориентация модулей и насадков", 1, G_AUP_P),
        ("ap_press", "Контроль давления газа-вытеснителя (масса — по ТД модуля)", 1, G_AUP_P),
        ("ap_prof", "Профилактические работы", 1, G_AUP_P),
        ("ap_powder", "Контроль качества огнетушащего порошка", 0, G_AUP_P),
        ("ap_func", "Проверка работоспособности в ручном и автоматическом режимах без выпуска ОТВ", 6, G_AUP_P),
        ("ap_metro", "Метрологическая проверка КИП", 12, G_AUP_P),
        ("ap_room", "Отсутствие изменений пожарной нагрузки и её затенения", 12, G_AUP_P),
        ("ap_cert", "Техническое освидетельствование АУП", 60, G_AUP_P),
    ],
    "aupt_aerosol": [
        ("aa_insp", "Внешний осмотр генераторов, узлов пуска и проводки: целостность, коррозия, крепление, пломбы", 1, G_AUP_A),
        ("aa_prof", "Профилактические работы", 1, G_AUP_A),
        ("aa_func", "Проверка работоспособности в ручном и автоматическом режимах без пуска генераторов", 6, G_AUP_A),
        ("aa_metro", "Метрологическая проверка КИП", 12, G_AUP_A),
        ("aa_room", "Отсутствие изменений пожарной нагрузки, объёма и герметичности помещений", 12, G_AUP_A),
        ("aa_cert", "Техническое освидетельствование АУП", 60, G_AUP_A),
    ],
    "smoke": [
        ("sm_insp", "Внешний осмотр вентиляторов, клапанов, приводов и шкафов управления; индикация положения клапанов", 1, "ТД изготовителя (рекомендуемая)"),
        ("sm_dampers", "Проверка срабатывания клапанов дымоудаления и огнезадерживающих клапанов по команде", 3, "ППР п. 42, ТД изготовителя"),
        ("sm_fans", "Пуск вентиляторов дымоудаления и подпора в ручном и автоматическом режимах", 3, "ТД изготовителя (рекомендуемая)"),
        ("sm_complex", "Совместная проверка с АПС (комплексные испытания) и периодические испытания с замером параметров", 12, "ГОСТ Р 53300-2009"),
    ],
    "monitoring": [
        ("mon_insp", "Внешний осмотр объектовой станции, антенны, кабелей", 1, "ТД изготовителя"),
        ("mon_test", "Передача тестового извещения на пульт пожарной охраны, проверка прохождения", 1, "ч. 7 ст. 83 123-ФЗ, ТД изготовителя"),
        ("mon_power", "Проверка резервного питания и канала связи", 1, "ТД изготовителя"),
    ],
    "vpv": [
        ("vpv_month", "Внешний осмотр и очистка, показания приборов, проверка запорных устройств, резервного питания", 1, G_VPV),
        ("vpv_water", "Проверка работоспособности пожарных кранов на водоотдачу с актом (весна и осень)", 6, "ППР п. 50, " + G_VPV),
        ("vpv_cabinets", "Комплектность пожарных шкафов: рукав, ствол, головки, пломбы, обозначения", 6, G_VPV),
        ("vpv_roll", "Перекатка пожарных рукавов на новую скатку", 12, "ППР п. 50, " + G_VPV),
        ("vpv_year", "Сопротивление заземления, промывка трубопроводов, поверка КИП", 12, G_VPV),
        ("vpv_3y", "Замена воды в ёмкостях, сопротивление изоляции, гидро- и пневмоиспытания трубопроводов", 36, G_VPV),
    ],
    "pumps": [
        ("pump_start", "Пробный пуск пожарных насосных агрегатов", 1, "ППР п. 52"),
        ("pump_switch", "Проверка автоматического, дистанционного и ручного пуска; переход на резервный насос и резервный ввод", 1, G_VPV),
        ("pump_room", "Осмотр насосной: схема, инструкции, таблички, освещение, телефон", 1, G_VPV),
        ("pump_valves", "Проверка задвижек с электроприводом", 6, "ППР п. 52"),
    ],
    "outer_water": [
        ("ow_test", "Проверка работоспособности гидрантов (водоёма) с пуском воды, акт", 6, "ППР п. 48"),
        ("ow_wells", "Осмотр колодцев: крышки, отсутствие воды и льда, доступ и подъезд", 6, "ППР п. 48"),
        ("ow_signs", "Наличие и исправность указателей с расстоянием (светоотражающих или световых)", 6, "ППР п. 48"),
        ("ow_winter", "Подготовка к зиме: утепление колодцев, откачка воды", 12, "СП 8.13130 (рекомендуемая)"),
    ],
    "extinguishers": [
        ("ext_look", "Осмотр: наличие на местах, пломба, давление по манометру, доступность, сроки перезарядки", 3, G_EXT + " (рекомендуемая)"),
        ("ext_tech", "Ежегодная проверка: корпус, ЗПУ, покрытие, инструкция, манометр, клеймо, масса, шланг и насадок, крепление", 12, G_EXT + ".7"),
        ("ext_leak", "Визуальная проверка утечки вытесняющего газа", 12, G_EXT + ".7"),
        ("ext_open", "Вскрытие не менее 3 % порошковых (не менее 1 шт.): сыпучесть, комки, влага; при отклонении — перезарядка всей марки", 12, G_EXT + ".7"),
        ("ext_recharge_op", "Перезарядка по паспорту или по результатам проверки", 60, "ППР п. 60"),
        ("ext_journal", "Записи в журнале ТО огнетушителей, бирки", 12, "ГОСТ Р 59641-2021, прил. А"),
    ],
    "fireproof": [
        ("fp_visual", "Визуальный осмотр покрытия: отслоения, трещины, повреждения, увлажнение", 12, "ППР п. 13, ГОСТ Р 59637-2021"),
        ("fp_thick", "Инструментальный контроль толщины покрытия (краски, мастики)", 12, "ГОСТ Р 59637-2021"),
        ("fp_quality", "Контроль качества пропитки (древесина, ткани) — отбор проб при необходимости", 12, "ГОСТ Р 59637-2021"),
        ("fp_act", "Акт проверки состояния огнезащиты, проверка срока службы покрытия", 12, "ППР п. 13"),
    ],
    "ladders": [
        ("lad_insp", "Осмотр лестниц и ограждений кровли: целостность, коррозия, крепления, сварные швы; очистка от снега и наледи", 12, "ППР п. 17"),
        ("lad_test", "Эксплуатационные испытания нагрузкой с протоколом", 60, "ППР п. 17, ГОСТ Р 53254-2009"),
    ],
    "fire_doors": [
        ("door_close", "Самозакрывание (доводчики), плотный притвор, отсутствие клиньев и подпорок", 3, "ППР п. 14, ГОСТ Р 59642-2021"),
        ("door_seal", "Состояние уплотнителей (в т.ч. терморасширяющихся), фурнитуры, «антипаники»", 3, "ГОСТ Р 59642-2021"),
        ("door_mark", "Маркировка (шильдик), отсутствие самовольных изменений конструкции", 12, "ГОСТ Р 59642-2021"),
    ],
    "emergency_light": [
        ("el_auto", "Автоматическое переключение на аварийное питание", 6, "ТД изготовителя (рекомендуемая)"),
        ("el_battery", "Работа светильников и знаков «Выход» от встроенных АКБ, замена ламп и АКБ", 6, "ТД изготовителя (рекомендуемая)"),
    ],
}

TASK_OPS = {  # какие перечни операций открываются в акте по регламентной работе
    "aps_to": "aps", "soue_to": "soue", "aupt_to": "aupt", "smoke_to": "smoke", "monitoring_to": "monitoring",
    "vpv_to": "vpv", "vpv_check": "vpv", "vpv_hoses": "vpv", "pumps_check": "pumps", "valves_check": "pumps",
    "outer_water_check": "outer_water", "ext_inspect": "extinguishers", "ext_annual": "extinguishers",
    "ext_recharge": "extinguishers", "fireproof_check": "fireproof", "ladders_inspect": "ladders",
    "ladders_test": "ladders", "fire_doors_check": "fire_doors", "emergency_light_check": "emergency_light",
}

AUPT_GROUPS = {"Газовое": "aupt_gas", "Порошковое": "aupt_powder", "Аэрозольное": "aupt_aerosol"}


def ops_key(system_code, systems):
    if system_code == "aupt":
        return AUPT_GROUPS.get((systems.get("aupt") or {}).get("kind", ""), "aupt_water")
    return system_code


def ops_for_task(task_code, systems):
    sc = TASK_OPS.get(task_code)
    if not sc or sc not in systems:
        return None, []
    key = ops_key(sc, systems)
    return key, OPS.get(key, [])


def period_label(m):
    if m in PERIOD_LABELS:
        return PERIOD_LABELS[m]
    return {1: "ежемесячно", 3: "раз в квартал", 6: "раз в полгода", 12: "раз в год",
            36: "раз в 3 года", 60: "раз в 5 лет"}.get(m, f"раз в {m} мес.")


# ---------------------------------------------------------------------------
# Цены (ориентир рынка Москвы и МО, 2025–2026, руб. с НДС «от — до»).
# kind: unit (цена за единицу за одно выполнение), tier (абонентская плата по ступеням),
#       base_area (база до N м² + надбавка за каждые step м²), fixed (за выполнение).
# events/год берутся из периодичности работы на объекте.
# est=True — экспертное допущение, источников с прямыми ценами мало.
# ---------------------------------------------------------------------------
PRICES_NOTE = ("Ориентировочный бюджет по открытым прайсам обслуживающих организаций Москвы и МО (2025–2026), "
               "диапазон «от — до». Не включает ремонт, замену оборудования и ЗИП, стоимость работ по договору "
               "уточняется после обследования. Для регионов задайте поправочный коэффициент.")

PRICES = [
    {"code": "aps", "task": "aps_to", "title": "ТО пожарной сигнализации (абонентская плата)", "qty": "aps_devices",
     "unit": "устройств", "kind": "tier",
     "tiers": [[10, 1650, 5000], [20, 2650, 8500], [30, 3650, 12000], [50, 4400, 18000], [100, 7700, 26000],
               [200, 9500, 38000]], "step": 50, "extra": [1000, 5000]},
    {"code": "soue", "task": "soue_to", "title": "ТО системы оповещения (СОУЭ)", "qty": "soue_units",
     "unit": "оповещателей", "kind": "unit", "min": 50, "max": 140, "min_charge": [1000, 2500], "est": True},
    {"code": "aupt_water", "task": "aupt_to", "title": "ТО водяного (пенного) пожаротушения", "qty": "aupt_area",
     "unit": "м² защищаемой площади", "kind": "tier", "when": "aupt_water",
     "tiers": [[1000, 9950, 15450], [3000, 12000, 19900], [10000, 18000, 29900]], "step": 5000,
     "extra": [6000, 10000]},
    {"code": "aupt_mod", "task": "aupt_to", "title": "ТО модульного пожаротушения (газ, порошок, аэрозоль)",
     "qty": "aupt_modules", "unit": "модулей", "kind": "tier", "when": "aupt_modules",
     "tiers": [[10, 3000, 5000], [30, 5000, 8000], [50, 6000, 10000], [100, 9000, 15000]], "step": 50,
     "extra": [4000, 7000]},
    {"code": "smoke", "task": "smoke_to", "title": "ТО противодымной вентиляции", "qty": "smoke_units",
     "unit": "вентиляторов и клапанов", "kind": "unit", "min": 200, "max": 600, "min_charge": [2000, 5000],
     "est": True},
    {"code": "monitoring", "task": "monitoring_to", "title": "ТО ПАК вывода сигнала на пульт", "qty": "one",
     "unit": "станция", "kind": "fixed", "min": 3700, "max": 7000},
    {"code": "vpv_to", "task": "vpv_to", "title": "Ежемесячное ТО ВПВ", "qty": "one", "unit": "система",
     "kind": "fixed", "min": 1500, "max": 4000, "est": True},
    {"code": "vpv_check", "task": "vpv_check", "title": "Проверка пожарных кранов на водоотдачу",
     "qty": "vpv_cranes", "unit": "кранов", "kind": "unit", "min": 350, "max": 900},
    {"code": "vpv_hoses", "task": "vpv_hoses", "title": "Перекатка пожарных рукавов", "qty": "vpv_cranes",
     "unit": "рукавов", "kind": "unit", "min": 100, "max": 500},
    {"code": "pumps", "task": "pumps_check", "title": "Проверка пожарных насосов", "qty": "pump_units",
     "unit": "агрегатов", "kind": "unit", "min": 500, "max": 1500},
    {"code": "outer_water", "task": "outer_water_check", "title": "Проверка гидрантов / водоёмов",
     "qty": "hydrants", "unit": "источников", "kind": "unit", "min": 1500, "max": 7000},
    {"code": "ext_annual", "task": "ext_annual", "title": "Ежегодное ТО огнетушителей", "qty": "ext_count",
     "unit": "огнетушителей", "kind": "unit", "min": 100, "max": 300},
    {"code": "ext_recharge", "task": "ext_recharge", "title": "Перезарядка огнетушителей (ОП-4/5)",
     "qty": "ext_count", "unit": "огнетушителей", "kind": "unit", "min": 130, "max": 400},
    {"code": "fireproof", "task": "fireproof_check", "title": "Проверка качества огнезащиты (лаборатория, акт)",
     "qty": "fireproof_area", "unit": "м² обработки", "kind": "base_area", "base": [10000, 22500], "upto": 1000,
     "step": 1000, "extra": [3000, 7500]},
    {"code": "ladders_test", "task": "ladders_test", "title": "Испытания пожарных лестниц и ограждений кровли",
     "qty": "ladders", "unit": "лестниц", "kind": "unit", "min": 5000, "max": 15000},
    {"code": "ladders_inspect", "task": "ladders_inspect", "title": "Обследование наружных лестниц",
     "qty": "ladders", "unit": "лестниц", "kind": "unit", "min": 500, "max": 3000},
    {"code": "elight", "task": "emergency_light_check", "title": "Проверка аварийного освещения",
     "qty": "elight", "unit": "светильников", "kind": "unit", "min": 30, "max": 100, "min_charge": [1000, 3000],
     "est": True},
    {"code": "dampers", "task": "dampers_check", "title": "Проверка огнезадерживающих клапанов",
     "qty": "ozk", "unit": "клапанов", "kind": "unit", "min": 300, "max": 800, "est": True},
    {"code": "over_life", "task": "over_life_test", "title": "Испытания систем сверх срока службы",
     "qty": "old_systems", "unit": "систем", "kind": "unit", "min": 15000, "max": 50000, "est": True},
]

NOT_PRICED = {  # работы, которые не оцениваются (своими силами или только по смете)
    "instr_repeat": "силами эксплуатанта", "evac_drill": "силами эксплуатанта",
    "sizod_check": "силами эксплуатанта", "ext_inspect": "силами эксплуатанта",
    "fire_doors_check": "силами эксплуатанта", "spz_plan": "входит в договор ТО",
    "valves_check": "входит в ТО насосной", "vent_clean": "по смете (зависит от длины воздуховодов)",
    "chimney_clean": "по смете",
}


def _n(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def quantity(key, p, s, old_systems=0):
    """Возвращает (количество, оценено_ли_приблизительно)."""
    area = _n(p.get("area_m2"))
    g = lambda sys, k: _n((s.get(sys) or {}).get(k))
    if key == "one":
        return 1, False
    if key == "aps_devices":
        v = g("aps", "detectors")
        return (v, False) if v else (max(5, round(area / 25)), True)
    if key == "soue_units":
        v = g("soue", "units")
        return (v, False) if v else (max(2, round(area / 80)), True)
    if key == "aupt_area":
        v = g("aupt", "area")
        return (v, False) if v else ((area, True) if area else (500, True))
    if key == "aupt_modules":
        v = g("aupt", "modules")
        return (v, False) if v else (max(2, round((g("aupt", "area") or area or 200) / 50)), True)
    if key == "smoke_units":
        v = g("smoke", "units")
        return (v, False) if v else (4, True)
    if key == "vpv_cranes":
        v = g("vpv", "cranes")
        return (v, False) if v else (max(2, round(area / 800)), True)
    if key == "pump_units":
        v = g("pumps", "units")
        return (v, False) if v else (2, True)
    if key == "hydrants":
        v = g("outer_water", "count")
        return (v, False) if v else (1, True)
    if key == "ext_count":
        v = g("extinguishers", "count")
        return (v, False) if v else (max(2, round(area / 100)), True)
    if key == "fireproof_area":
        v = g("fireproof", "area")
        return (v, False) if v else (1000, True)
    if key == "ladders":
        v = g("ladders", "count")
        return (v, False) if v else (1, True)
    if key == "elight":
        v = g("emergency_light", "count")
        return (v, False) if v else (max(4, round(area / 50)), True)
    if key == "ozk":
        v = g("ventilation", "ozk_count")
        return (v, False) if v else (2, True)
    if key == "old_systems":
        return old_systems, False
    return 0, False


def price_per_event(item, qty, mult=1.0):
    """(min, max) за одно выполнение работы."""
    k = item["kind"]
    if k == "fixed":
        lo, hi = item["min"], item["max"]
    elif k == "unit":
        lo, hi = qty * item["min"], qty * item["max"]
        if item.get("min_charge"):
            lo, hi = max(lo, item["min_charge"][0]), max(hi, item["min_charge"][1])
    elif k == "tier":
        lo = hi = None
        for upto, a, b in item["tiers"]:
            if qty <= upto:
                lo, hi = a, b
                break
        if lo is None:
            last_upto, a, b = item["tiers"][-1]
            steps = -(-(qty - last_upto) // item["step"])
            lo, hi = a + steps * item["extra"][0], b + steps * item["extra"][1]
    elif k == "base_area":
        steps = max(0, -(-(qty - item["upto"]) // item["step"]))
        lo, hi = item["base"][0] + steps * item["extra"][0], item["base"][1] + steps * item["extra"][1]
    else:
        lo = hi = 0
    return lo * mult, hi * mult


def apply_overrides(overrides):
    """Цены с учётом правок обслуживающей организации: {code: {"min":..,"max":..,"mult":..}}."""
    out = []
    for it in PRICES:
        it = dict(it)
        ov = (overrides or {}).get(it["code"], {})
        if it["kind"] in ("unit", "fixed"):
            if ov.get("min") is not None:
                it["min"] = ov["min"]
            if ov.get("max") is not None:
                it["max"] = ov["max"]
        it["mult"] = ov.get("mult", 1.0) if it["kind"] in ("tier", "base_area") else 1.0
        out.append(it)
    return out


def budget(p, s, task_rows, overrides=None, global_coef=1.0, old_systems=0):
    """
    task_rows: список dict с ключами code, period (мес.), title — активные работы объекта.
    Возвращает строки и итоги по году.
    """
    coef = (_n(p.get("price_coef")) or 1.0) * (global_coef or 1.0)
    by_task = {t["code"]: t for t in task_rows}
    aupt_kind = ops_key("aupt", s) if "aupt" in s else None
    lines, skipped = [], []
    for it in apply_overrides(overrides):
        t = by_task.get(it["task"])
        if not t:
            continue
        if it.get("when") == "aupt_water" and aupt_kind != "aupt_water":
            continue
        if it.get("when") == "aupt_modules" and aupt_kind in (None, "aupt_water"):
            continue
        qty, est = quantity(it["qty"], p, s, old_systems)
        if not qty:
            continue
        per_year = 12 / max(1, t["period"])
        lo, hi = price_per_event(it, qty, it["mult"])
        lines.append(dict(code=it["code"], task=it["task"], title=it["title"], qty=qty, qty_est=est, unit=it["unit"],
                          per_year=per_year, event_min=lo * coef, event_max=hi * coef,
                          year_min=lo * coef * per_year, year_max=hi * coef * per_year, price_est=bool(it.get("est"))))
    for t in task_rows:
        if t["code"] in NOT_PRICED:
            skipped.append(dict(title=t["title"], reason=NOT_PRICED[t["code"]]))
    tot_min = sum(l["year_min"] for l in lines)
    tot_max = sum(l["year_max"] for l in lines)
    return dict(lines=lines, skipped=skipped, year_min=tot_min, year_max=tot_max,
                month_min=tot_min / 12, month_max=tot_max / 12, coef=coef)


def ops_status(ops, last_done_map, today=None):
    """Статус каждой операции: last, due, status (overdue/soon/ok/nodata/info)."""
    today = today or date.today()
    from app_utils import add_months  # noqa: локальный импорт, чтобы не тянуть Flask
    out = []
    for code, text, per, ref in ops:
        last = last_done_map.get(code)
        if per <= 0:
            status, due = "info", None
        elif not last:
            status, due = "nodata", None
        else:
            due = add_months(date.fromisoformat(last), per)
            d = (due - today).days
            status = "overdue" if d < 0 else "soon" if d <= (7 if per <= 1 else 30) else "ok"
        out.append(dict(code=code, text=text, period=per, period_label=period_label(per), ref=ref, last=last,
                        due=due.isoformat() if due else None, status=status))
    return out


# Операция в акте автоматически засчитывает связанную регламентную работу
OP_TASK = {
    "vpv_water": "vpv_check", "vpv_roll": "vpv_hoses", "vpv_month": "vpv_to",
    "pump_start": "pumps_check", "pump_valves": "valves_check",
    "ext_look": "ext_inspect", "ext_tech": "ext_annual", "ext_recharge_op": "ext_recharge",
    "lad_insp": "ladders_inspect", "lad_test": "ladders_test",
    "fp_act": "fireproof_check", "door_close": "fire_doors_check", "el_auto": "emergency_light_check",
    "ow_test": "outer_water_check", "sm_dampers": "dampers_check",
}
