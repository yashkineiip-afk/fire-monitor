// ===== Демо-версия «Мониторинг ПБ»: все данные хранятся в браузере =====
const KEY = "firemon_demo_v1", ROLE_KEY = "firemon_demo_role";
const SIDE = {client:"Эксплуатант", provider:"Обслуживающая организация"};
const TSTATUS = {overdue:["Просрочено","red"], soon:["Скоро срок","yellow"], ok:["В норме","green"], nodata:["Нет данных","gray"]};
const LEVELS = {red:"Требует внимания", yellow:"Есть вопросы", green:"В норме"};
const SEV = {critical:"Критическое", medium:"Значительное", low:"Незначительное"};
const ISTATUS = {open:"Открыто", in_progress:"В работе", resolved:"Устранено"};
const IKIND = {remark:"Замечание", request:"Заявка"};
const ANSWERS = {yes:"Да", no:"Нет", na:"Н/П"};
const WORK_TYPES = ["Техническое обслуживание","Проверка работоспособности","Испытания","Осмотр","Ремонт","Перезарядка / замена","Инструктаж","Тренировка","Прочее"];
const RESULTS = ["Исправно / выполнено","Выполнено с замечаниями","Неисправно"];

// ---------- утилиты ----------
const h = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const iso = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
const TODAY = () => { const d = new Date(); d.setHours(0,0,0,0); return d; };
const parse = s => { if (!s) return null; const [y,m,d] = s.split("-").map(Number); return new Date(y, m-1, d); };
const ruDate = s => { const d = parse(String(s||"").slice(0,10)); return d ? d.toLocaleDateString("ru-RU") : "—"; };
function addMonths(d, m) {
  const t = new Date(d.getFullYear(), d.getMonth() + m, 1);
  const last = new Date(t.getFullYear(), t.getMonth() + 1, 0).getDate();
  t.setDate(Math.min(d.getDate(), last)); return t;
}
const days = (a, b) => Math.round((a - b) / 86400000);
function periodLabel(m) {
  if (m === 1) return "ежемесячно"; if (m === 3) return "раз в квартал"; if (m === 6) return "раз в полгода";
  if (m % 12 === 0) { const y = m / 12; return y === 1 ? "раз в год" : y >= 5 ? `раз в ${y} лет` : `раз в ${y} года`; }
  return `раз в ${m} мес.`;
}
const pill = (cls, text) => `<span class="pill ${cls}">${h(text)}</span>`;

// ---------- хранилище ----------
let DB, ROLE;
function load() {
  try { DB = JSON.parse(localStorage.getItem(KEY)); } catch (e) { DB = null; }
  if (!DB || !DB.objects) { DB = seed(); save(); }
  if (!DB.prices) DB.prices = {coef: 1, items: {}};
  DB.objects.forEach(syncTasks); save();
  try { ROLE = JSON.parse(localStorage.getItem(ROLE_KEY)); } catch (e) { ROLE = null; }
  if (!ROLE) ROLE = {mode:"provider"};
}
function save() { try { localStorage.setItem(KEY, JSON.stringify(DB)); } catch (e) { alert("Не удалось сохранить: закончилось место в браузере."); } }
const nid = () => ++DB.seq;
const isProv = () => ROLE.mode === "provider";
const userName = () => isProv() ? "Инженер (демо)" : "Представитель: " + (client(ROLE.clientId)?.name || "");
const client = id => DB.clients.find(c => c.id === id);
const obj = id => DB.objects.find(o => o.id === id);
const visible = () => DB.objects.filter(o => !o.archived && (isProv() || o.clientId === ROLE.clientId));

// ---------- логика ----------
function syncTasks(o) {
  const y = TODAY().getFullYear(); o.tasks = o.tasks || {};
  const appl = TASKS.filter(t => t.applies(o.profile, o.systems, y)).map(t => t.code);
  for (const code of appl) {
    const t = TASKS_BY_CODE[code], per = taskPeriod(t, o.profile, o.systems), ex = o.tasks[code];
    if (ex) { ex.active = true; if (!ex.custom) ex.period = per; }
    else o.tasks[code] = {period: per, custom: false, side: t.side, last: null, active: true};
  }
  for (const code in o.tasks) if (!appl.includes(code)) o.tasks[code].active = false;
}
function taskRows(o) {
  const today = TODAY(), rows = [];
  for (const [code, r] of Object.entries(o.tasks || {})) {
    const t = TASKS_BY_CODE[code]; if (!t || !r.active) continue;
    const last = parse(r.last), due = last ? addMonths(last, r.period) : null;
    let status = "nodata", dd = null;
    if (due) { dd = days(due, today); const warn = r.period <= 1 ? 7 : 30; status = dd < 0 ? "overdue" : dd <= warn ? "soon" : "ok"; }
    rows.push({code, ...t, side: r.side, period: r.period, custom: r.custom, last: r.last, due: due ? iso(due) : null, status, days: dd});
  }
  const ord = {overdue:0, nodata:1, soon:2, ok:3};
  return rows.sort((a, b) => ord[a.status] - ord[b.status] || (a.due || "").localeCompare(b.due || ""));
}
function checklistRows(o) {
  return CHECKLIST.filter(([, , , c]) => c(o.profile, o.systems)).map(([no, text, ref]) => {
    const a = (o.checklist || {})[no] || {};
    return {no, text, ref, fromFile: no <= 29, answer: a.answer || null, comment: a.comment || "", at: a.at};
  });
}
function summary(o) {
  const tasks = taskRows(o), cl = checklistRows(o).filter(c => c.answer !== "na");
  const cnt = {overdue:0, soon:0, ok:0, nodata:0}; tasks.forEach(t => cnt[t.status]++);
  const yes = cl.filter(c => c.answer === "yes").length, no = cl.filter(c => c.answer === "no").length;
  const un = cl.filter(c => !c.answer).length;
  const open = (o.issues || []).filter(i => i.status !== "resolved");
  const crit = open.filter(i => i.severity === "critical").length;
  const level = (cnt.overdue || no || crit) ? "red" : (cnt.soon || cnt.nodata || un || open.length) ? "yellow" : "green";
  const lastJ = (o.journal || []).map(j => j.date).sort().pop();
  return {tasks: cnt, clTotal: cl.length, yes, no, un, pct: cl.length ? Math.round(100 * yes / cl.length) : 0,
          open: open.length, crit, req: open.filter(i => i.kind === "request").length, level, lastJ};
}
function addIssue(o, title, desc = "", severity = "medium", kind = "remark", due = null, clNo = null) {
  o.issues = o.issues || [];
  o.issues.push({id: nid(), title: title.slice(0, 300), desc, severity, status: "open", kind, due, clNo,
                 created: iso(TODAY()), by: userName()});
}
function markDone(o, code, date) { const t = o.tasks[code]; if (t && (!t.last || t.last < date)) t.last = date; }

// ---------- демо-данные ----------
function seed() {
  const db = {v: 1, seq: 5000, clients: [], objects: [], prices: {coef: 1, items: {}}};
  db.clients.push({id: 1, name: "ООО «Бизнес-Парк Север»", inn: "7700000000", contact: "Иванов И. И.", phone: "+7 900 000-00-00"});
  db.clients.push({id: 2, name: "ИП Смирнова А. В. (арендатор)", contact: "Смирнова А. В."});
  const ago = n => { const d = TODAY(); d.setDate(d.getDate() - n); return iso(d); };
  const o1 = {id: 11, clientId: 1, name: "БЦ «Север», корпус А", address: "г. Москва, ул. Примерная, д. 1",
    profile: {purpose:"Офисный центр", usage_right:"Собственник", responsible_name:"Иванов И. И.", responsible_position:"Главный инженер",
      responsible_phone:"+7 900 000-00-00", fclass:"Ф4.3 — Органы управления, офисы, банки, НИИ, редакции", floors:"9", underground:"1",
      height_m:"28", area_m2:"12500", fire_resistance:"II", constr_class:"С0", year_built:"2012", max_people:"600", workplaces10:true,
      night_stay:true, mgn:true, declaration:"Да", facade_banners:true, smoking_place:true},
    systems: {aps:{kind:"Адресная", brand:"Рубеж-2ОП", detectors:"840", year:"2012", life:"10"}, soue:{type:"3", brand:"Соната", units:"160", year:"2012", life:"10"},
      smoke:{kind:"дымоудаление, подпор", units:"26", year:"2012", life:"15"}, vpv:{cranes:"36"}, pumps:{units:"2"},
      outer_water:{kind:"Пожарные гидранты", count:"2", distance:"80"}, extinguishers:{count:"120", types:"ОП-4, ОУ-3"},
      fire_doors:{count:"48"}, emergency_light:{count:"210"}, ventilation:{ozk:true, ozk_count:"14"}},
    tasks: {}, checklist: {}, journal: [], issues: []};
  const o2 = {id: 12, clientId: 1, name: "Склад №2", address: "Московская обл., г. Химки, Промзона, стр. 5",
    profile: {purpose:"Склад непродовольственных товаров", usage_right:"Арендатор", responsible_name:"Сидоров П. П.",
      fclass:"Ф5.2 — Складские здания, стоянки, архивы, книгохранилища", floors:"1", height_m:"12", area_m2:"4800",
      fire_resistance:"IV", constr_class:"С0", year_built:"2018", max_people:"25", has_prod_storage:true, categories:"В2, В3",
      declaration:"Не знаю", smoking_place:true},
    systems: {aps:{kind:"Адресно-аналоговая", year:"2018", life:"10"}, aupt:{kind:"Водяное спринклерное", rooms:"складской зал", area:"4200", year:"2018", life:"10"},
      soue:{type:"2", year:"2018", life:"10"}, extinguishers:{count:"30", types:"ОП-5"}, fireproof:{what:"металлоконструкции", area:"2600", year:"2018", life:"10"},
      ladders:{count:"2"}},
    tasks: {}, checklist: {}, journal: [], issues: []};
  const o3 = {id: 13, clientId: 2, name: "Детский клуб «Радуга»", address: "г. Москва, ул. Садовая, д. 7, пом. 3",
    profile: {purpose:"Детский развивающий центр", usage_right:"Арендатор", responsible_name:"Смирнова А. В.",
      fclass:"Ф4.1 — Школы, внешкольные учреждения, СПО", floors:"1", area_m2:"220", max_people:"40", declaration:"Нет"},
    systems: {aps:{kind:"Пороговая", year:"2021", life:"10"}, soue:{type:"2", year:"2021", life:"10"},
      extinguishers:{count:"4", types:"ОП-4"}, emergency_light:{count:"12"}},
    tasks: {}, checklist: {}, journal: [], issues: []};
  db.objects.push(o1, o2, o3);
  DB = db; let jid = 1000;
  db.objects.forEach(syncTasks);
  const hist = {11: {aps_to:20, soue_to:20, smoke_to:45, vpv_check:170, vpv_hoses:300, pumps_check:25, ext_inspect:80,
                     ext_annual:340, evac_drill:200, instr_repeat:150, spz_plan:320},
                12: {aps_to:10, aupt_to:10, soue_to:10, fireproof_check:400, ladders_test:900},
                13: {aps_to:12, soue_to:12, ext_inspect:30, ext_annual:100, instr_repeat:90, spz_plan:60}};
  for (const [oid, items] of Object.entries(hist)) {
    const o = db.objects.find(x => x.id === +oid);
    for (const [code, n] of Object.entries(items)) {
      o.tasks[code].last = ago(n);
      o.journal.push({id: jid++, date: ago(n), task: code, system: TASKS_BY_CODE[code].system || "", type: "Плановая работа",
                      desc: TASKS_BY_CODE[code].title, result: RESULTS[0], performer: "Инженер Петров", by: "Инженер (демо)"});
    }
  }
  [[1,"yes"],[2,"yes"],[3,"yes"],[4,"yes"],[9,"yes"],[14,"yes"],[16,"no"],[20,"yes"],[29,"yes"],[13,"no"]]
    .forEach(([n, a]) => o1.checklist[n] = {answer: a, comment: "", at: iso(TODAY())});
  o1.journal.push({id: jid++, date: ago(20), task: "aps_to", system: "aps", type: "Техническое обслуживание",
    desc: "Регламентное ТО АПС: выполнено операций — 4, неисправностей — 1", result: RESULTS[1], performer: "Инженер Петров", by: "Инженер (демо)",
    ops: [{code: "aps_ppkp_insp", status: "ok", note: ""}, {code: "aps_ibe_insp", status: "ok", note: ""}, {code: "aps_ppkp_func", status: "ok", note: ""},
          {code: "aps_ibe_func", status: "defect", note: "АКБ 12 В: 12,4 В — требуется замена"}]});
  o1.issues.push({id: 2004, title: "АПС: замена АКБ в ИБЭ", desc: "АКБ 12 В: 12,4 В", severity: "medium", status: "open", kind: "remark", created: ago(20), by: "Инженер (демо)"});
  o1.issues.push({id: 2001, title: "Чек-лист п. 16: не заделаны кабельные проходки на 3 этаже", desc: "Кабельный лоток у лифтового холла",
                  severity: "medium", status: "open", kind: "remark", clNo: 16, created: ago(5), by: "Инженер (демо)"});
  o1.issues.push({id: 2002, title: "Чек-лист п. 13: нет документов на баннер фасада", desc: "", severity: "low", status: "open",
                  kind: "remark", clNo: 13, created: ago(5), by: "Инженер (демо)"});
  o2.issues.push({id: 2003, title: "Не закрывается противопожарная дверь в рампе", desc: "Сломан доводчик", severity: "critical",
                  status: "open", kind: "request", created: ago(2), by: "Представитель: ООО «Бизнес-Парк Север»"});
  return db;
}

// ---------- общие куски разметки ----------
function levelPill(l) { return pill(l, LEVELS[l]); }
function tPill(s) { return pill(TSTATUS[s][1], TSTATUS[s][0]); }
function sevPill(s) { return pill({critical:"red", medium:"yellow", low:"gray"}[s], SEV[s]); }
function iPill(s) { return pill({open:"red", in_progress:"yellow", resolved:"green"}[s], ISTATUS[s]); }
const opts = (list, sel) => list.map(v => `<option ${v === sel ? "selected" : ""}>${h(v)}</option>`).join("");
const optsKV = (obj, sel) => Object.entries(obj).map(([k, v]) => `<option value="${h(k)}" ${k === sel ? "selected" : ""}>${h(v)}</option>`).join("");
function sysParams(code, prm) {
  return SYSTEMS[code].fields.filter(f => prm[f.key]).map(f => `${f.label}: ${prm[f.key] === true ? "да" : h(prm[f.key])}`).join("; ");
}

function header() {
  const r = location.hash;
  const nav = [["#/", "Объекты", r === "#/" || r === "" || r.startsWith("#/o/")], ["#/plan", "План-график", r === "#/plan"],
    ["#/issues", "Замечания и заявки", r === "#/issues"]];
  if (isProv()) nav.push(["#/clients", "Эксплуатанты", r === "#/clients"], ["#/prices", "Цены", r === "#/prices"]);
  const roleSel = `<select data-act="role" class="rolesel">
      <option value="p" ${isProv() ? "selected" : ""}>Вход: обслуживающая организация</option>
      ${DB.clients.map(c => `<option value="${c.id}" ${!isProv() && ROLE.clientId === c.id ? "selected" : ""}>Вход: эксплуатант — ${h(c.name)}</option>`).join("")}
    </select>`;
  return `<header class="top"><div class="wrap">
    <a class="brand" href="#/"><span class="dot"></span>Мониторинг ПБ <span class="demo">ДЕМО</span></a>
    <nav class="nav">${nav.map(([u, t, on]) => `<a href="${u}" class="${on ? "on" : ""}">${t}</a>`).join("")}<a href="#/data" class="${r === "#/data" ? "on" : ""}">Данные</a></nav>
    <div class="who">${roleSel}</div></div></header>
    <div class="normbar"><div class="wrap">${h(NORMS_NOTE)}</div></div>`;
}

// ---------- страницы ----------
function pageDashboard() {
  const q = (sessionStorage.getItem("q") || "").toLowerCase();
  const rows = visible().filter(o => !q || `${o.name} ${o.address} ${client(o.clientId)?.name || ""}`.toLowerCase().includes(q))
    .map(o => [o, summary(o)]);
  const ord = {red:0, yellow:1, green:2};
  rows.sort((a, b) => ord[a[1].level] - ord[b[1].level] || a[0].name.localeCompare(b[0].name));
  const T = k => rows.filter(([, s]) => s.level === k).length;
  const sum = f => rows.reduce((a, [, s]) => a + f(s), 0);
  return `<div class="head"><div><h1>${isProv() ? "Объекты на обслуживании" : "Мои объекты"}</h1><div class="muted">${TODAY().toLocaleDateString("ru-RU")}</div></div>
    <div class="actions">${isProv() ? `<a class="btn" href="#/new">+ Новый объект</a>` : ""}</div></div>
    <div class="grid k" style="margin-bottom:1rem">
      <div class="kpi"><div class="v">${rows.length}</div><div class="l">объектов</div></div>
      <div class="kpi red"><div class="v">${T("red")}</div><div class="l">требуют внимания</div></div>
      <div class="kpi yellow"><div class="v">${T("yellow")}</div><div class="l">есть вопросы</div></div>
      <div class="kpi green"><div class="v">${T("green")}</div><div class="l">в норме</div></div>
      <div class="kpi red"><div class="v">${sum(s => s.tasks.overdue)}</div><div class="l">просроченных работ</div></div>
      <div class="kpi"><div class="v">${sum(s => s.open)}</div><div class="l">открытых замечаний${sum(s => s.req) ? `, из них заявок: ${sum(s => s.req)}` : ""}</div></div>
    </div>
    <form class="rowform" data-form="search" style="margin-bottom:.8rem"><input type="text" name="q" value="${h(q)}" placeholder="Поиск: название, адрес, эксплуатант" style="min-width:260px"><button class="btn ghost sm">Найти</button></form>
    <div class="tablewrap"><table class="tbl"><thead><tr><th>Объект</th><th>Состояние</th><th>Чек-лист</th><th>Работы</th><th>Замечания</th><th>Последняя запись</th></tr></thead><tbody>
    ${rows.map(([o, s]) => `<tr class="row-${s.level}">
      <td><a href="#/o/${o.id}"><b>${h(o.name)}</b></a><div class="small muted">${h(o.address)}${isProv() && client(o.clientId) ? " · " + h(client(o.clientId).name) : ""}</div></td>
      <td>${levelPill(s.level)}</td>
      <td style="min-width:120px"><div class="bar"><i style="width:${s.pct}%"></i></div><div class="small muted">${s.yes} из ${s.clTotal}${s.no ? ` · <span style="color:var(--red)">нет: ${s.no}</span>` : ""}</div></td>
      <td class="small">${s.tasks.overdue ? pill("red", "просрочено " + s.tasks.overdue) + " " : ""}${s.tasks.soon ? pill("yellow", "скоро " + s.tasks.soon) + " " : ""}${s.tasks.nodata ? pill("gray", "нет данных " + s.tasks.nodata) : ""}${!(s.tasks.overdue || s.tasks.soon || s.tasks.nodata) ? pill("green", "все в срок") : ""}</td>
      <td class="small">${s.open ? s.open + (s.crit ? ` · <span style="color:var(--red)">крит.: ${s.crit}</span>` : "") : '<span class="muted">—</span>'}</td>
      <td class="small muted">${ruDate(s.lastJ)}</td></tr>`).join("") ||
      `<tr><td colspan="6" class="empty">${isProv() ? 'Объектов нет. <a href="#/new">Заведите первый объект</a>.' : "За этой организацией нет объектов."}</td></tr>`}
    </tbody></table></div>`;
}

function objectHead(o, tab) {
  const s = summary(o), c = client(o.clientId);
  const tabs = [["", "Обзор"], ["checklist", "Чек-лист", s.no], ["schedule", "График работ", s.tasks.overdue], ["regulations", "Регламент ТО"], ["journal", "Журнал"],
    ["issues", "Замечания и заявки", s.open], ["budget", "Бюджет"]];
  return `<div class="head"><div><h1>${h(o.name)}</h1><div class="muted">${h(o.address || "Адрес не указан")}${c ? " · " + h(c.name) : ""}</div></div>
    <div class="actions">${levelPill(s.level)}<a class="btn ghost sm" href="#/o/${o.id}/report">Отчёт для печати</a><a class="btn ghost sm" href="#/o/${o.id}/edit">Анкета</a></div></div>
    <nav class="tabs">${tabs.map(([t, n, cnt]) => `<a href="#/o/${o.id}${t ? "/" + t : ""}" class="${tab === t ? "on" : ""}">${n}${cnt ? `<span class="cnt">${cnt}</span>` : ""}</a>`).join("")}</nav>`;
}

function pageObject(o) {
  const p = o.profile, s = o.systems, sm = summary(o), tasks = taskRows(o);
  const shown = tasks.filter(t => ["overdue", "soon", "nodata"].includes(t.status));
  const issues = (o.issues || []).filter(i => i.status !== "resolved");
  const journal = [...(o.journal || [])].sort((a, b) => b.date.localeCompare(a.date) || b.id - a.id).slice(0, 6);
  const dl = [["Назначение", p.purpose], ["Класс ФПО", p.fclass], ["Этажность / высота", `${p.floors || "—"} эт. / ${p.height_m || "—"} м`],
    ["Площадь", p.area_m2 ? p.area_m2 + " м²" : ""], ["Огнестойкость / класс К", `${p.fire_resistance || "—"} / ${p.constr_class || "—"}`],
    ["Людей одновременно", p.max_people], ["Эксплуатирует", p.usage_right],
    ["Ответственный за ПБ", [p.responsible_name, p.responsible_phone].filter(Boolean).join(", ")]];
  return objectHead(o, "") + normWarnings(p, s, TODAY().getFullYear()).map(w => `<div class="warn">⚠ ${h(w)}</div>`).join("") + `
  <div class="grid k" style="margin:1rem 0">
    <div class="kpi ${sm.pct >= 90 ? "green" : sm.pct >= 60 ? "yellow" : "red"}"><div class="v">${sm.pct}%</div><div class="l">чек-лист выполнен (${sm.yes} из ${sm.clTotal})</div></div>
    <div class="kpi red"><div class="v">${sm.tasks.overdue}</div><div class="l">просроченных работ</div></div>
    <div class="kpi yellow"><div class="v">${sm.tasks.soon}</div><div class="l">работ скоро по сроку</div></div>
    <div class="kpi"><div class="v">${sm.tasks.nodata}</div><div class="l">работ без данных</div></div>
    <div class="kpi ${sm.crit ? "red" : ""}"><div class="v">${sm.open}</div><div class="l">открытых замечаний</div></div>
    ${(() => { const ro = regulations(o).reduce((a, r) => a + r.overdue, 0), b = budget(o);
      return `<a class="kpi ${ro ? "red" : ""}" href="#/o/${o.id}/regulations" style="color:inherit;text-decoration:none"><div class="v">${ro}</div><div class="l">операций ТО по ГОСТ просрочено</div></a>
      <a class="kpi" href="#/o/${o.id}/budget" style="color:inherit;text-decoration:none"><div class="v" style="font-size:1.2rem">${Math.round(b.yMin / 1000)}–${Math.round(b.yMax / 1000)} тыс. ₽</div><div class="l">бюджет ТО в год (ориентир)</div></a>`; })()}</div>
  <div class="grid two"><div>
    <div class="panel"><h2 style="margin-top:0">Ближайшие и просроченные работы</h2>
      ${shown.length ? `<table class="tbl">${shown.slice(0, 8).map(t => `<tr><td>${h(t.title)}<div class="small muted">${SIDE[t.side]} · ${periodLabel(t.period)}</div></td><td style="white-space:nowrap">${tPill(t.status)}<div class="small muted">${t.due ? ruDate(t.due) : ""}</div></td></tr>`).join("")}</table>
      ${shown.length > 8 ? `<p class="small"><a href="#/o/${o.id}/schedule">Все работы (${shown.length}) →</a></p>` : ""}` : `<p class="muted">Все работы выполняются в срок.</p>`}</div>
    <div class="panel"><h2 style="margin-top:0">Открытые замечания</h2>
      ${issues.map(i => `<div style="padding:.4rem 0;border-bottom:1px solid var(--line)">${sevPill(i.severity)} <span class="tag">${IKIND[i.kind]}</span> ${h(i.title)}${i.due ? `<span class="small muted"> · срок ${ruDate(i.due)}</span>` : ""}</div>`).join("") || `<p class="muted">Нет открытых замечаний.</p>`}
      <p class="small"><a href="#/o/${o.id}/issues">${isProv() ? "Добавить замечание" : "Подать заявку"} →</a></p></div>
  </div><div>
    <div class="panel"><h2 style="margin-top:0">Объект</h2><dl class="kv">${dl.map(([k, v]) => `<dt>${k}</dt><dd>${h(v || "—")}</dd>`).join("")}</dl></div>
    <div class="panel"><h2 style="margin-top:0">Системы и оборудование</h2>
      ${Object.entries(s).filter(([c]) => SYSTEMS[c]).map(([c, prm]) => `<div style="padding:.35rem 0;border-bottom:1px solid var(--line)"><b>${h(SYSTEMS[c].name)}</b><div class="small muted">${sysParams(c, prm)}</div></div>`).join("") || `<p class="muted">Системы не указаны. <a href="#/o/${o.id}/edit">Заполните анкету</a>.</p>`}</div>
    <div class="panel"><h2 style="margin-top:0">Последние записи журнала</h2>
      ${journal.map(j => `<div class="small" style="padding:.3rem 0;border-bottom:1px solid var(--line)"><b>${ruDate(j.date)}</b> · ${h(j.desc || j.type)} — <span class="muted">${h(j.result)}</span></div>`).join("") || `<p class="muted">Записей пока нет.</p>`}</div>
    ${isProv() ? `<button class="btn ghost sm" data-act="archive" data-id="${o.id}">В архив</button>` : ""}
  </div></div>`;
}

function pageForm(o) {
  const p = o ? o.profile : {}, s = o ? o.systems : {};
  const field = (f, val, name) => {
    if (f.type === "bool") return `<label class="check"><input type="checkbox" name="${name}" ${val ? "checked" : ""}> ${h(f.label)}</label>`;
    let inp;
    if (f.type === "select") inp = `<select name="${name}"><option value="">—</option>${opts(f.options, val)}</select>`;
    else if (f.type === "textarea") inp = `<textarea name="${name}">${h(val)}</textarea>`;
    else inp = `<input type="${f.type === "number" ? "number" : "text"}" step="any" name="${name}" value="${h(val)}">`;
    return `<div class="field" ${f.type === "textarea" ? 'style="grid-column:1/-1"' : ""}><label>${h(f.label)}</label>${inp}${f.hint ? `<div class="hint">${h(f.hint)}</div>` : ""}</div>`;
  };
  return `<div class="head"><div><h1>${o ? "Анкета объекта" : "Новый объект"}</h1><div class="muted">По ответам система определит применимые требования, чек-лист и график регламентных работ.</div></div>
    ${o ? `<div class="actions"><a class="btn ghost" href="#/o/${o.id}">← К объекту</a></div>` : ""}</div>
  <form data-form="object" data-id="${o ? o.id : ""}">
    <div class="panel"><h2 style="margin-top:0">Объект</h2><div class="fields">
      <div class="field"><label>Название *</label><input type="text" name="name" required value="${h(o?.name)}"></div>
      <div class="field"><label>Адрес</label><input type="text" name="address" value="${h(o?.address)}"></div>
      ${isProv() ? `<div class="field"><label>Эксплуатирующая организация</label><select name="clientId"><option value="">— не выбрана —</option>${DB.clients.map(c => `<option value="${c.id}" ${o && o.clientId === c.id ? "selected" : ""}>${h(c.name)}</option>`).join("")}</select></div>
      <div class="field"><label>…или новая организация</label><input type="text" name="newClient" placeholder="ООО «…» — будет создана"></div>` : ""}
    </div></div>
    ${QUESTIONNAIRE.map(sec => `<div class="panel"><h2 style="margin-top:0">${h(sec.title)}</h2><div class="fields">${sec.fields.map(f => field(f, p[f.key], "p_" + f.key)).join("")}</div></div>`).join("")}
    <div class="panel"><h2 style="margin-top:0">Системы противопожарной защиты и оборудование</h2>
      <p class="muted small">Отметьте, что есть на объекте, и заполните сведения. От этого зависят регламентные работы и пункты чек-листа.</p>
      ${Object.entries(SYSTEMS).map(([code, sd]) => { const sp = s[code]; return `<div class="sys ${sp ? "on" : ""}">
        <label class="check"><input type="checkbox" data-sys name="sys_${code}" ${sp ? "checked" : ""}> ${h(sd.name)}</label>
        <div class="sysfields fields">${sd.fields.map(f => field(f, sp ? sp[f.key] : "", `s_${code}_${f.key}`)).join("")}</div></div>`; }).join("")}
    </div>
    <button class="btn">${o ? "Сохранить анкету" : "Создать объект"}</button></form>`;
}

function pageChecklist(o) {
  const rows = checklistRows(o);
  return objectHead(o, "checklist") + `<p class="muted small">Требования, применимые к объекту по анкете. Пп. 1–29 — из опросного листа сотрудников, остальные добавлены по системам объекта. «Нет» создаёт замечание, «Да» закрывает его. <i>В демо-версии файлы не прикрепляются.</i></p>
  <form data-form="checklist" data-id="${o.id}" class="panel">
    ${rows.map(r => `<div class="cl-item"><div class="cl-no">${r.no}</div>
      <div>${h(r.text)}<div class="small muted">${h(r.ref)}${r.fromFile ? "" : ' · <span class="tag">по системам объекта</span>'}${r.at ? " · обновлено " + ruDate(r.at) : ""}</div></div>
      <div class="cl-ans">${Object.entries(ANSWERS).map(([k, v]) => `<label><input type="radio" name="a_${r.no}" value="${k}" ${r.answer === k ? "checked" : ""}><span>${v}</span></label>`).join("")}</div>
      <div class="cl-extra"><input type="text" name="c_${r.no}" value="${h(r.comment)}" placeholder="Комментарий, реквизиты документа"></div></div>`).join("")}
    <div class="savebar"><button class="btn">Сохранить чек-лист</button></div></form>`;
}

function pageSchedule(o) {
  const today = iso(TODAY());
  return objectHead(o, "schedule") + `<p class="muted small">Работы сформированы по анкете. Отметка о выполнении создаёт запись в журнале и сдвигает следующий срок. «Нет данных» — внесите дату последнего выполнения.</p>
  <div class="tablewrap"><table class="tbl"><thead><tr><th>Работа</th><th>Кто</th><th>Периодичность</th><th>Выполнено</th><th>Следующий срок</th><th>Отметить выполнение</th></tr></thead><tbody>
  ${taskRows(o).map(t => `<tr class="row-${t.status === "nodata" ? "" : TSTATUS[t.status][1]}">
    <td><b>${h(t.title)}</b><div class="small muted">${h(t.ref)}</div>${t.hint ? `<div class="small muted">${h(t.hint)}</div>` : ""}</td>
    <td class="small">${SIDE[t.side]}</td>
    <td class="small">${periodLabel(t.period)}${t.custom ? ' <span class="tag">изменено</span>' : ""}
      ${isProv() ? `<details><summary>изменить</summary><form data-form="taskedit" data-id="${o.id}" data-code="${t.code}" style="margin-top:.4rem">
        <div class="field"><label>Месяцев</label><input type="number" name="period" min="1" max="120" value="${t.period}"></div>
        <div class="field"><label>Кто выполняет</label><select name="side">${optsKV(SIDE, t.side)}</select></div>
        <label class="check"><input type="checkbox" name="reset"> вернуть норматив</label><button class="btn sm">Сохранить</button></form></details>` : ""}</td>
    <td class="small">${ruDate(t.last)}</td>
    <td style="white-space:nowrap">${tPill(t.status)}<div class="small muted">${t.due ? ruDate(t.due) : ""} ${t.days === null ? "" : t.days < 0 ? `(${-t.days} дн. назад)` : `(через ${t.days} дн.)`}</div></td>
    <td>${opsForTask(t.code, o.systems)[1].length ? `<a class="btn sm" href="#/o/${o.id}/act/${t.code}">Акт ТО по ГОСТ →</a><details><summary>быстрая отметка</summary>` : ""}<form data-form="taskdone" data-id="${o.id}" data-code="${t.code}">
      <div class="rowform"><input type="date" name="date" value="${today}" max="${today}" required><button class="btn sm">Выполнено</button></div>
      <details><summary>результат, примечание</summary><select name="result" style="margin-top:.4rem">${opts(RESULTS)}</select>
        <input type="text" name="note" placeholder="Примечание" style="margin-top:.4rem"><input type="text" name="performer" placeholder="Исполнитель" style="margin-top:.4rem"></details></form>${opsForTask(t.code, o.systems)[1].length ? "</details>" : ""}</td>
  </tr>`).join("") || `<tr><td colspan="6" class="empty">Работ нет — заполните системы в анкете.</td></tr>`}
  </tbody></table></div>`;
}

function pageJournal(o) {
  const today = iso(TODAY()), sysOpts = Object.keys(o.systems).filter(c => SYSTEMS[c]);
  const entries = [...(o.journal || [])].sort((a, b) => b.date.localeCompare(a.date) || b.id - a.id);
  return objectHead(o, "journal") + `<div class="panel"><h2 style="margin-top:0">Новая запись</h2>
    <form data-form="journal" data-id="${o.id}"><div class="fields">
      <div class="field"><label>Дата</label><input type="date" name="date" value="${today}" max="${today}" required></div>
      <div class="field"><label>Вид работ</label><select name="type">${opts(WORK_TYPES)}</select></div>
      <div class="field"><label>Система</label><select name="system"><option value="">—</option>${sysOpts.map(c => `<option value="${c}">${h(SYSTEMS[c].name)}</option>`).join("")}</select></div>
      <div class="field"><label>Засчитать как регламентную работу</label><select name="task"><option value="">— нет —</option>${taskRows(o).map(t => `<option value="${t.code}">${h(t.title)}</option>`).join("")}</select></div>
      <div class="field"><label>Результат</label><select name="result">${opts(RESULTS)}</select><div class="hint">«Неисправно» создаст критическое замечание</div></div>
      <div class="field"><label>Исполнитель</label><input type="text" name="performer" placeholder="${h(userName())}"></div>
      <div class="field" style="grid-column:1/-1"><label>Описание</label><textarea name="desc" placeholder="Что сделано, что выявлено"></textarea></div>
    </div><button class="btn">Добавить запись</button></form></div>
  <div class="tablewrap"><table class="tbl"><thead><tr><th>Дата</th><th>Работа</th><th>Система</th><th>Результат</th><th>Исполнитель</th></tr></thead><tbody>
  ${entries.map(j => `<tr class="row-${j.result === "Неисправно" ? "red" : j.result === "Выполнено с замечаниями" ? "yellow" : ""}">
    <td style="white-space:nowrap">${ruDate(j.date)}</td><td>${h(j.type)}${j.task ? ' <span class="tag">по графику</span>' : ""}<div class="small">${h(j.desc)}</div>
      ${(j.ops || []).length ? `<details><summary>операции (${j.ops.length}) · <a href="#/o/${o.id}/actview/${j.id}">акт</a></summary><ul class="small" style="margin:.3rem 0;padding-left:1.1rem">${j.ops.map(x => `<li>${pill({ok:"green", defect:"red", skip:"gray"}[x.status], OP_STATUS[x.status])} ${h((OP_TEXT[x.code] || [x.code])[0])}${x.note ? ` — <i>${h(x.note)}</i>` : ""}</li>`).join("")}</ul></details>` : ""}</td>
    <td class="small">${SYSTEMS[j.system] ? h(SYSTEMS[j.system].name) : "—"}</td><td class="small">${h(j.result)}</td>
    <td class="small">${h(j.performer)}<div class="muted">внёс: ${h(j.by || "")}</div></td></tr>`).join("") || `<tr><td colspan="5" class="empty">Записей нет</td></tr>`}
  </tbody></table></div>`;
}

function issuesTable(list, showObj) {
  const today = iso(TODAY());
  return `<div class="tablewrap"><table class="tbl"><thead><tr><th>Замечание</th>${showObj ? "<th>Объект</th>" : ""}<th>Важность</th><th>Статус</th><th>Срок</th><th>Действие</th></tr></thead><tbody>
  ${list.map(([o, i]) => `<tr class="row-${i.severity === "critical" && i.status !== "resolved" ? "red" : ""}">
    <td><span class="tag">${IKIND[i.kind]}</span> <b>${h(i.title)}</b>${i.desc ? `<div class="small">${h(i.desc)}</div>` : ""}
      <div class="small muted">${ruDate(i.created)} · ${h(i.by || "")}${i.resolution ? " · решение: " + h(i.resolution) : ""}</div></td>
    ${showObj ? `<td class="small"><a href="#/o/${o.id}/issues">${h(o.name)}</a></td>` : ""}
    <td>${sevPill(i.severity)}</td><td>${iPill(i.status)}${i.resolved ? `<div class="small muted">${ruDate(i.resolved)}</div>` : ""}</td>
    <td class="small" style="${i.due && i.due < today && i.status !== "resolved" ? "color:var(--red)" : ""}">${ruDate(i.due)}</td>
    <td><form data-form="issueupd" data-id="${o.id}" data-iid="${i.id}"><div class="rowform"><select name="status">${optsKV(ISTATUS, i.status)}</select><button class="btn sm">OK</button></div>
      <details><summary>комментарий</summary><input type="text" name="resolution" placeholder="Что сделано" style="margin-top:.3rem"></details></form></td></tr>`).join("")
    || `<tr><td colspan="6" class="empty">Нет записей</td></tr>`}</tbody></table></div>`;
}
const issueSort = (a, b) => (a.status === "resolved") - (b.status === "resolved") ||
  ({critical:0, medium:1, low:2}[a.severity] - {critical:0, medium:1, low:2}[b.severity]) || (b.created || "").localeCompare(a.created || "");

function pageIssues(o) {
  return objectHead(o, "issues") + `<div class="panel"><h2 style="margin-top:0">${isProv() ? "Новое замечание" : "Заявка в обслуживающую организацию"}</h2>
    <form data-form="issue" data-id="${o.id}"><div class="fields">
      <div class="field" style="grid-column:1/-1"><label>Суть *</label><input type="text" name="title" required placeholder="${isProv() ? "Например: не работает извещатель в пом. 214" : "Например: сработала сигнализация, нужен выезд"}"></div>
      <div class="field"><label>Важность</label><select name="severity">${optsKV(SEV, "medium")}</select></div>
      <div class="field"><label>Срок устранения</label><input type="date" name="due"></div>
      <div class="field" style="grid-column:1/-1"><label>Подробности</label><textarea name="desc"></textarea></div>
    </div><button class="btn">${isProv() ? "Добавить" : "Отправить заявку"}</button></form></div>` +
    issuesTable([...(o.issues || [])].sort(issueSort).map(i => [o, i]), false);
}

function pageAllIssues() {
  const f = sessionStorage.getItem("ifilter") || "active";
  const list = [];
  visible().forEach(o => (o.issues || []).forEach(i => {
    if (f === "all" || (f === "active" ? i.status !== "resolved" : i.status === f)) list.push([o, i]);
  }));
  list.sort((a, b) => issueSort(a[1], b[1]));
  return `<div class="head"><h1>Замечания и заявки</h1><form class="rowform" data-form="ifilter"><select name="f">
    <option value="active" ${f === "active" ? "selected" : ""}>Активные</option>${optsKV(ISTATUS, f)}<option value="all" ${f === "all" ? "selected" : ""}>Все</option></select><button class="btn ghost sm">Показать</button></form></div>` + issuesTable(list, true);
}

function pagePlan() {
  const horizon = +(sessionStorage.getItem("horizon") || 60), side = sessionStorage.getItem("side") || "";
  const items = [];
  visible().forEach(o => taskRows(o).forEach(t => {
    if (side && t.side !== side) return;
    if (["overdue", "nodata"].includes(t.status) || (t.days !== null && t.days <= horizon)) items.push([o, t]);
  }));
  const ord = {overdue:0, soon:1, ok:2, nodata:3};
  items.sort((a, b) => ord[a[1].status] - ord[b[1].status] || (a[1].due || "9999").localeCompare(b[1].due || "9999"));
  return `<div class="head"><div><h1>План-график работ</h1><div class="muted">Просроченные, без данных и со сроком в ближайшие ${horizon} дней — по всем объектам</div></div>
    <form class="rowform" data-form="plan"><select name="days">${[14, 30, 60, 90, 180, 365].map(d => `<option value="${d}" ${horizon === d ? "selected" : ""}>${d} дней</option>`).join("")}</select>
    <select name="side"><option value="">Все исполнители</option>${optsKV(SIDE, side)}</select><button class="btn ghost sm">Показать</button></form></div>
  <div class="tablewrap"><table class="tbl"><thead><tr><th>Срок</th><th>Статус</th><th>Работа</th><th>Объект</th><th>Кто</th></tr></thead><tbody>
  ${items.map(([o, t]) => `<tr><td style="white-space:nowrap">${t.due ? ruDate(t.due) : "—"}</td><td>${tPill(t.status)}</td>
    <td>${h(t.title)}<div class="small muted">${h(t.ref)} · ${periodLabel(t.period)}</div></td>
    <td><a href="#/o/${o.id}/schedule">${h(o.name)}</a><div class="small muted">${h(o.address)}</div></td><td class="small">${SIDE[t.side]}</td></tr>`).join("")
    || `<tr><td colspan="5" class="empty">На выбранный период работ нет</td></tr>`}</tbody></table></div>`;
}

function pageClients() {
  if (!isProv()) return `<div class="panel">Раздел доступен обслуживающей организации.</div>`;
  return `<h1>Эксплуатирующие организации</h1><p class="muted">Собственники, арендаторы, управляющие компании. В полной версии у каждой организации свои логины; в демо — переключатель «Вход» вверху.</p>
  <div class="panel"><h2 style="margin-top:0">Добавить организацию</h2><form data-form="client"><div class="fields">
    <div class="field"><label>Название *</label><input type="text" name="name" required></div>
    <div class="field"><label>ИНН</label><input type="text" name="inn"></div>
    <div class="field"><label>Контактное лицо</label><input type="text" name="contact"></div>
    <div class="field"><label>Телефон</label><input type="text" name="phone"></div></div><button class="btn">Добавить</button></form></div>
  <div class="tablewrap"><table class="tbl"><thead><tr><th>Организация</th><th>Контакт</th><th>Объектов</th></tr></thead><tbody>
  ${DB.clients.map(c => `<tr><td><b>${h(c.name)}</b><div class="small muted">ИНН ${h(c.inn || "—")}</div></td><td class="small">${h(c.contact || "")} ${h(c.phone || "")}</td>
    <td>${DB.objects.filter(o => o.clientId === c.id && !o.archived).length}</td></tr>`).join("")}</tbody></table></div>`;
}

function pageData() {
  return `<h1>Данные демо-версии</h1>
  <div class="panel"><p>Все данные этой демо-версии хранятся <b>только в этом браузере на этом устройстве</b>. Другой сотрудник по той же ссылке увидит свою копию с демо-объектами. Чтобы передать свои записи коллеге, выгрузите файл и отправьте его — коллега загрузит его у себя.</p>
  <div class="actions"><button class="btn" data-act="export">Выгрузить данные (файл)</button>
  <label class="btn ghost" style="margin:0">Загрузить файл<input type="file" accept=".json" data-act="import" hidden></label>
  <button class="btn ghost" data-act="reset">Сбросить к демо-данным</button></div></div>
  <div class="panel small muted">В полной версии на сервере данные общие: инженер отметил ТО — эксплуатант сразу видит; эксплуатант подал заявку — она приходит вам. Там же вход по логину и паролю, прикрепление актов и фото.</div>`;
}

function pageReport(o) {
  const p = o.profile, s = o.systems, sm = summary(o), c = client(o.clientId);
  const issues = (o.issues || []).filter(i => i.status !== "resolved");
  return `<div class="report"><div class="actions noprint" style="margin-bottom:1rem"><button class="btn" onclick="window.print()">Печать / сохранить PDF</button><a class="btn ghost" href="#/o/${o.id}">← К объекту</a></div>
  <div class="small muted">Сформировано ${new Date().toLocaleString("ru-RU")} · «Мониторинг ПБ» (демо)</div>
  <h1>Отчёт о противопожарном состоянии объекта</h1>
  <p><b>${h(o.name)}</b>, ${h(o.address || "адрес не указан")}${c ? " · " + h(c.name) : ""}</p>
  <p>Общая оценка: ${levelPill(sm.level)} · чек-лист ${sm.pct}% (${sm.yes}/${sm.clTotal}, «нет» — ${sm.no}, без ответа — ${sm.un}) · работ просрочено ${sm.tasks.overdue}, без данных ${sm.tasks.nodata} · открытых замечаний ${sm.open}</p>
  ${normWarnings(p, s, TODAY().getFullYear()).map(w => `<div class="warn">⚠ ${h(w)}</div>`).join("")}
  <h2>1. Сведения об объекте</h2><dl class="kv">${QUESTIONNAIRE.flatMap(sec => sec.fields).filter(f => p[f.key]).map(f => `<dt>${h(f.label)}</dt><dd>${p[f.key] === true ? "да" : h(p[f.key])}</dd>`).join("")}</dl>
  <h2>2. Системы противопожарной защиты</h2><table class="tbl">${Object.entries(s).filter(([k]) => SYSTEMS[k]).map(([k, prm]) => `<tr><td><b>${h(SYSTEMS[k].name)}</b></td><td class="small">${sysParams(k, prm)}</td></tr>`).join("") || "<tr><td>Не указаны</td></tr>"}</table>
  <h2>3. Регламентные работы</h2><table class="tbl"><tr><th>Работа</th><th>Норма</th><th>Период.</th><th>Выполнено</th><th>Срок</th><th>Статус</th></tr>
  ${taskRows(o).map(t => `<tr><td>${h(t.title)}</td><td class="small">${h(t.ref)}</td><td class="small">${periodLabel(t.period)}</td><td>${ruDate(t.last)}</td><td>${t.due ? ruDate(t.due) : "—"}</td><td>${tPill(t.status)}</td></tr>`).join("")}</table>
  <h2>4. Соблюдение требований (чек-лист)</h2><table class="tbl"><tr><th>№</th><th>Требование</th><th>Ответ</th><th>Комментарий</th></tr>
  ${checklistRows(o).map(r => `<tr><td>${r.no}</td><td class="small">${h(r.text)}<div class="muted">${h(r.ref)}</div></td><td>${r.answer ? pill({yes:"green", no:"red", na:"gray"}[r.answer], ANSWERS[r.answer]) : '<span class="muted">—</span>'}</td><td class="small">${h(r.comment)}</td></tr>`).join("")}</table>
  <h2>5. Регламент ТО по ГОСТ</h2><table class="tbl"><tr><th>Система</th><th>Операций</th><th>Просрочено</th><th>Нет данных</th></tr>
  ${regulations(o).map(r => `<tr><td>${h(r.name)}</td><td>${r.ops.length}</td><td>${r.overdue}</td><td>${r.nodata}</td></tr>`).join("") || '<tr><td colspan="4">—</td></tr>'}</table>
  <h2>6. Ориентировочный бюджет на ТО систем ПЗ</h2>${budgetTable(budget(o))}<p class="small muted">Ориентир по рыночным ценам, без ремонта и замены оборудования.</p>
  <h2>7. Открытые замечания</h2><table class="tbl"><tr><th>Замечание</th><th>Важность</th><th>Срок</th></tr>
  ${issues.map(i => `<tr><td>${h(i.title)}${i.desc ? `<div class="small muted">${h(i.desc)}</div>` : ""}</td><td>${SEV[i.severity]}</td><td>${ruDate(i.due)}</td></tr>`).join("") || '<tr><td colspan="3">Нет</td></tr>'}</table>
  <p class="small muted" style="margin-top:1.5rem">${h(NORMS_NOTE)}</p>
  <div class="sign"><div>Представитель обслуживающей организации</div><div>Представитель эксплуатанта</div></div></div>`;
}

// ---------- регламент ТО, акты, бюджет ----------
const opPill = st => pill({overdue:"red", soon:"yellow", ok:"green", nodata:"gray", info:"gray"}[st],
  {overdue:"Просрочено", soon:"Скоро", ok:"В норме", nodata:"Нет данных", info:"По ТД"}[st]);

function pageAct(o, code) {
  const t = TASKS_BY_CODE[code], [, ops] = opsForTask(code, o.systems);
  if (!t || !ops.length) return objectHead(o, "schedule") + `<div class="panel">Для этой работы нет перечня операций.</div>`;
  const rows = opsStatus(ops, opsLastDone(o)), today = iso(TODAY());
  return objectHead(o, "schedule") + `<h2 style="margin-top:0">Акт ТО: ${h(t.title)}</h2>
  <p class="muted small">Перечень операций по ГОСТ для этой системы. Система отметила к выполнению те, по которым подошёл или прошёл срок. «Неисправность» создаст замечание.</p>
  <form data-form="act" data-id="${o.id}" data-code="${code}" class="panel"><div class="fields">
    <div class="field"><label>Дата</label><input type="date" name="date" value="${today}" max="${today}" required></div>
    <div class="field"><label>Исполнитель</label><input type="text" name="performer" placeholder="${h(userName())}"></div></div>
  <div class="tablewrap"><table class="tbl"><thead><tr><th>Операция</th><th>Периодичность</th><th>Последний раз</th><th>Результат</th></tr></thead><tbody>
  ${rows.map(r => { const pre = ["overdue", "soon", "nodata"].includes(r.status) ? "ok" : "skip";
    return `<tr class="row-${r.status === "overdue" ? "red" : r.status === "soon" ? "yellow" : ""}"><td>${h(r.text)}<div class="small muted">${h(r.ref)}</div></td>
    <td class="small">${r.periodLabel}</td><td class="small">${ruDate(r.last)}<div>${opPill(r.status)}</div></td>
    <td style="min-width:230px"><div class="opans">${[["ok", "Норма"], ["defect", "Неиспр."], ["skip", "Не вып."]].map(([k, v]) => `<label><input type="radio" name="st_${r.code}" value="${k}" ${pre === k ? "checked" : ""}><span>${v}</span></label>`).join("")}</div>
    <input type="text" name="n_${r.code}" placeholder="Замечание / замер" style="margin-top:.3rem"></td></tr>`; }).join("")}
  </tbody></table></div>
  <div class="field"><label>Общий комментарий</label><textarea name="note"></textarea></div>
  <button class="btn">Сохранить акт</button> <a class="btn ghost" href="#/o/${o.id}/schedule">Отмена</a></form>`;
}

function pageActView(o, jid) {
  const j = (o.journal || []).find(x => x.id === jid);
  if (!j) return `<div class="panel">Акт не найден.</div>`;
  const c = client(o.clientId);
  return `<div class="report"><div class="actions noprint" style="margin-bottom:1rem"><button class="btn" onclick="window.print()">Печать / сохранить PDF</button><a class="btn ghost" href="#/o/${o.id}/journal">← К журналу</a></div>
  <h1>Акт технического обслуживания № ${j.id}</h1><p>от ${ruDate(j.date)} · ${h(TASKS_BY_CODE[j.task]?.title || j.type)}</p>
  <dl class="kv"><dt>Объект</dt><dd>${h(o.name)}, ${h(o.address || "")}</dd><dt>Эксплуатант</dt><dd>${h(c?.name || "—")}</dd>
  <dt>Система</dt><dd>${SYSTEMS[j.system] ? h(SYSTEMS[j.system].name) : "—"}</dd><dt>Исполнитель</dt><dd>${h(j.performer)}</dd><dt>Итог</dt><dd>${h(j.result)}</dd></dl>
  <h2>Выполненные работы</h2><table class="tbl"><tr><th>№</th><th>Операция</th><th>Основание</th><th>Результат</th><th>Примечание</th></tr>
  ${(j.ops || []).map((x, i) => `<tr><td>${i + 1}</td><td>${h((OP_TEXT[x.code] || [x.code])[0])}</td><td class="small">${h((OP_TEXT[x.code] || ["", ""])[1])}</td>
    <td>${pill({ok:"green", defect:"red", skip:"gray"}[x.status], OP_STATUS[x.status])}</td><td class="small">${h(x.note || "")}</td></tr>`).join("") || `<tr><td colspan="5">${h(j.desc)}</td></tr>`}</table>
  ${j.desc ? `<p class="small"><b>Комментарий:</b> ${h(j.desc)}</p>` : ""}
  <div class="sign"><div>Представитель обслуживающей организации</div><div>Представитель эксплуатанта</div></div></div>`;
}

function pageRegs(o) {
  const regs = regulations(o);
  return objectHead(o, "regulations") + `<p class="muted small">Что конкретно должно выполняться с каждой системой по ГОСТ Р 59636…59643-2021 и ППР, когда это делали последний раз и когда срок. Отметки ставятся через «Акт ТО».</p>
  ${regs.map(r => { const t = taskRows(o).find(x => MT.TASK_OPS[x.code] === r.system);
    return `<div class="panel"><div class="head" style="margin-bottom:.4rem"><h2 style="margin:0">${h(r.name)}</h2><div class="actions">
      ${r.overdue ? pill("red", "просрочено " + r.overdue) : ""}${r.nodata ? pill("gray", "нет данных " + r.nodata) : ""}${t ? `<a class="btn sm" href="#/o/${o.id}/act/${t.code}">Заполнить акт ТО</a>` : ""}</div></div>
    <table class="tbl"><thead><tr><th>Операция</th><th>Периодичность</th><th>Последний раз</th><th>Срок</th><th>Статус</th></tr></thead>
    ${r.ops.map(x => `<tr><td>${h(x.text)}<div class="small muted">${h(x.ref)}</div></td><td class="small">${x.periodLabel}</td><td class="small">${ruDate(x.last)}</td><td class="small">${x.due ? ruDate(x.due) : "—"}</td><td>${opPill(x.status)}</td></tr>`).join("")}</table></div>`; }).join("")
    || `<div class="panel empty">Нет систем с регламентом ТО. Отметьте системы в анкете.</div>`}`;
}

function budgetTable(b) {
  return `<div class="tablewrap"><table class="tbl"><thead><tr><th>Работа</th><th>Объём</th><th>Раз в год</th><th>За раз</th><th>В год</th></tr></thead><tbody>
  ${b.lines.map(l => `<tr><td>${h(l.title)}${l.priceEst ? ' <span class="tag">цена — оценка</span>' : ""}</td>
    <td class="small">${Math.round(l.qty)} ${h(l.unit)}${l.est ? '<div class="muted">≈ по площади — уточните в анкете</div>' : ""}</td>
    <td class="small">${l.perYear < 1 ? `1 раз в ${Math.round(1 / l.perYear)} лет` : +l.perYear.toFixed(1)}</td>
    <td class="small" style="white-space:nowrap">${rub(l.eMin)} – ${rub(l.eMax)}</td><td style="white-space:nowrap"><b>${rub(l.yMin)} – ${rub(l.yMax)}</b></td></tr>`).join("")
    || '<tr><td colspan="5" class="empty">Нет работ для оценки — заполните системы в анкете</td></tr>'}</tbody>
  <tfoot><tr><td colspan="4"><b>Итого в год</b></td><td style="white-space:nowrap"><b>${rub(b.yMin)} – ${rub(b.yMax)}</b></td></tr></tfoot></table></div>`;
}

function pageBudget(o) {
  const b = budget(o);
  return objectHead(o, "budget") + `<div class="grid k" style="margin-bottom:1rem">
    <div class="kpi"><div class="v" style="font-size:1.35rem">${rub(b.yMin)} – ${rub(b.yMax)}</div><div class="l">ориентировочно в год</div></div>
    <div class="kpi"><div class="v" style="font-size:1.35rem">≈ ${rub((b.yMin + b.yMax) / 2)}</div><div class="l">середина диапазона в год</div></div>
    <div class="kpi"><div class="v" style="font-size:1.35rem">${rub(b.yMin / 12)} – ${rub(b.yMax / 12)}</div><div class="l">в среднем в месяц</div></div>
    <div class="kpi"><div class="v" style="font-size:1.35rem">× ${+b.coef.toFixed(2)}</div><div class="l">поправочный коэффициент</div></div></div>
  ${budgetTable(b)}
  ${b.skipped.length ? `<div class="panel small"><b>Не входит в оценку:</b><ul style="margin:.4rem 0 0;padding-left:1.1rem">${b.skipped.map(([t, r]) => `<li>${h(t)} — <span class="muted">${h(r)}</span></li>`).join("")}</ul></div>` : ""}
  <p class="small muted">${h(MT.PRICES_NOTE)} Периодичность берётся из графика работ объекта. ${isProv() ? '<a href="#/prices">Изменить цены</a>' : ""}</p>`;
}

function pagePrices() {
  if (!isProv()) return `<div class="panel">Раздел доступен обслуживающей организации.</div>`;
  return `<h1>Цены для расчёта бюджета</h1><p class="muted">${h(MT.PRICES_NOTE)}</p>
  <form data-form="prices" class="panel"><div class="field" style="max-width:320px"><label>Общий коэффициент (регион, НДС, ваша наценка)</label>
    <input type="number" step="0.01" name="coef" value="${DB.prices.coef}"></div>
  <div class="tablewrap"><table class="tbl"><thead><tr><th>Работа</th><th>Расчёт</th><th>Цена от, ₽</th><th>Цена до, ₽</th></tr></thead>
  ${priceItems().map(it => `<tr><td><b>${h(it.title)}</b>${it.est ? ' <span class="tag">оценка</span>' : ""}</td>
    ${["unit", "fixed"].includes(it.kind) ? `<td class="small">${it.kind === "unit" ? `за единицу (${h(it.unit)})` : "за выполнение"}${it.min_charge ? `<div class="muted">мин. ${it.min_charge[0]}–${it.min_charge[1]} ₽ за выезд</div>` : ""}</td>
      <td><input type="number" step="any" name="min_${it.code}" value="${it.min}" style="width:110px"></td><td><input type="number" step="any" name="max_${it.code}" value="${it.max}" style="width:110px"></td>`
    : `<td class="small">${it.kind === "tier" ? `абонентская плата по ступеням (${h(it.unit)}): ${it.tiers.map(t => `до ${t[0]} — ${t[1]}–${t[2]} ₽`).join("; ")}` : `до ${it.upto} м² — ${it.base[0]}–${it.base[1]} ₽, далее +${it.extra[0]}–${it.extra[1]} ₽ за ${it.step} м²`}</td>
      <td colspan="2"><label class="small">Множитель</label><input type="number" step="0.01" name="mult_${it.code}" value="${it.mult}" style="width:110px"></td>`}</tr>`).join("")}
  </table></div><button class="btn">Сохранить цены</button></form>`;
}

// ---------- роутер ----------
function route() {
  const parts = (location.hash || "#/").slice(2).split("/").filter(Boolean);
  let html;
  if (!parts.length) html = pageDashboard();
  else if (parts[0] === "plan") html = pagePlan();
  else if (parts[0] === "issues") html = pageAllIssues();
  else if (parts[0] === "clients") html = pageClients();
  else if (parts[0] === "data") html = pageData();
  else if (parts[0] === "prices") html = pagePrices();
  else if (parts[0] === "new") html = isProv() ? pageForm(null) : `<div class="panel">Новые объекты заводит обслуживающая организация.</div>`;
  else if (parts[0] === "o") {
    const o = obj(+parts[1]);
    if (!o || (!isProv() && o.clientId !== ROLE.clientId)) html = `<div class="panel">Объект не найден или нет доступа. <a href="#/">К списку</a></div>`;
    else if (parts[2] === "act") html = pageAct(o, parts[3]);
    else if (parts[2] === "actview") html = pageActView(o, +parts[3]);
    else html = ({"": pageObject, checklist: pageChecklist, schedule: pageSchedule, journal: pageJournal, issues: pageIssues,
                  edit: pageForm, report: pageReport, regulations: pageRegs, budget: pageBudget}[parts[2] || ""] || pageObject)(o);
  } else html = pageDashboard();
  const isReport = parts[2] === "report" || parts[2] === "actview";
  document.getElementById("app").innerHTML = (isReport ? "" : header()) +
    `<main class="wrap">${flashHtml()}${html}</main>`;
  document.querySelectorAll(".sys input[data-sys]").forEach(cb => cb.addEventListener("change", () => cb.closest(".sys").classList.toggle("on", cb.checked)));
}
let FLASH = null;
const flash = (msg, cls = "ok") => { FLASH = [msg, cls]; };
function flashHtml() { if (!FLASH) return ""; const [m, c] = FLASH; FLASH = null; return `<div class="flash ${c}">${h(m)}</div>`; }
function go(hash) { if (location.hash === hash) route(); else location.hash = hash; window.scrollTo(0, 0); }

// ---------- обработчики форм ----------
const FORMS = {
  search(f, d) { sessionStorage.setItem("q", d.get("q") || ""); route(); },
  ifilter(f, d) { sessionStorage.setItem("ifilter", d.get("f")); route(); },
  plan(f, d) { sessionStorage.setItem("horizon", d.get("days")); sessionStorage.setItem("side", d.get("side")); route(); },
  object(f, d) {
    const profile = {}, systems = {};
    QUESTIONNAIRE.forEach(sec => sec.fields.forEach(fl => { profile[fl.key] = fl.type === "bool" ? d.has("p_" + fl.key) : (d.get("p_" + fl.key) || "").trim(); }));
    for (const [code, sd] of Object.entries(SYSTEMS)) if (d.has("sys_" + code)) {
      systems[code] = {}; sd.fields.forEach(fl => { const n = `s_${code}_${fl.key}`; systems[code][fl.key] = fl.type === "bool" ? d.has(n) : (d.get(n) || "").trim(); });
    }
    let clientId = null;
    if (isProv()) {
      const nc = (d.get("newClient") || "").trim();
      if (nc) { clientId = nid(); DB.clients.push({id: clientId, name: nc}); } else clientId = d.get("clientId") ? +d.get("clientId") : null;
    }
    let o = f.dataset.id ? obj(+f.dataset.id) : null;
    if (o) { Object.assign(o, {name: d.get("name").trim() || o.name, address: (d.get("address") || "").trim(), profile, systems}); if (isProv()) o.clientId = clientId; }
    else { o = {id: nid(), clientId, name: d.get("name").trim(), address: (d.get("address") || "").trim(), profile, systems, tasks: {}, checklist: {}, journal: [], issues: []}; DB.objects.push(o); }
    syncTasks(o); save();
    flash(f.dataset.id ? "Анкета сохранена, график работ и чек-лист пересчитаны" : "Объект создан. Сформированы чек-лист и график регламентных работ.");
    go(`#/o/${o.id}`);
  },
  checklist(f, d) {
    const o = obj(+f.dataset.id); o.checklist = o.checklist || {};
    for (const r of checklistRows(o)) {
      const ans = d.get("a_" + r.no) || null, com = (d.get("c_" + r.no) || "").trim();
      if (ans !== r.answer || com !== r.comment) o.checklist[r.no] = {answer: ans, comment: com, at: iso(TODAY())};
      const open = (o.issues || []).find(i => i.clNo === r.no && i.status !== "resolved");
      if (ans === "no" && !open) addIssue(o, `Чек-лист п. ${r.no}: ${r.text.slice(0, 150)}`, com, "medium", "remark", null, r.no);
      else if ((ans === "yes" || ans === "na") && open) Object.assign(open, {status: "resolved", resolved: iso(TODAY()), resolution: "Отмечено выполненным в чек-листе"});
    }
    save(); flash("Чек-лист сохранён"); route(); window.scrollTo(0, 0);
  },
  taskdone(f, d) {
    const o = obj(+f.dataset.id), code = f.dataset.code, t = TASKS_BY_CODE[code], date = d.get("date");
    if (!date || date > iso(TODAY())) { flash("Дата не может быть в будущем", "error"); return route(); }
    const result = d.get("result") || RESULTS[0], note = (d.get("note") || "").trim();
    o.journal.push({id: nid(), date, task: code, system: t.system || "", type: "Плановая работа", desc: t.title + (note ? ". " + note : ""),
                    result, performer: (d.get("performer") || "").trim() || userName(), by: userName()});
    markDone(o, code, date);
    if (result === "Неисправно") addIssue(o, "Неисправность: " + t.title, note, "critical");
    save(); flash(`Отмечено: ${t.title} — ${ruDate(date)}`); route();
  },
  taskedit(f, d) {
    const o = obj(+f.dataset.id), tk = o.tasks[f.dataset.code], per = +d.get("period");
    tk.side = d.get("side");
    if (d.has("reset")) tk.custom = false; else if (per >= 1 && per <= 120) { tk.period = per; tk.custom = true; }
    syncTasks(o); save(); flash("Параметры работы обновлены"); route();
  },
  journal(f, d) {
    const o = obj(+f.dataset.id), date = d.get("date");
    if (!date || date > iso(TODAY())) { flash("Дата не может быть в будущем", "error"); return route(); }
    const task = d.get("task") || "", system = d.get("system") || (task ? TASKS_BY_CODE[task].system || "" : ""), result = d.get("result");
    o.journal.push({id: nid(), date, task, system, type: d.get("type"), desc: (d.get("desc") || "").trim(), result,
                    performer: (d.get("performer") || "").trim() || userName(), by: userName()});
    if (task) markDone(o, task, date);
    if (result === "Неисправно") addIssue(o, "Неисправность: " + (SYSTEMS[system]?.name || d.get("type")), d.get("desc") || "", "critical");
    save(); flash("Запись добавлена в журнал"); route();
  },
  issue(f, d) {
    const o = obj(+f.dataset.id);
    addIssue(o, d.get("title").trim(), (d.get("desc") || "").trim(), d.get("severity"), isProv() ? "remark" : "request", d.get("due") || null);
    save(); flash(isProv() ? "Замечание добавлено" : "Заявка отправлена обслуживающей организации"); route();
  },
  issueupd(f, d) {
    const o = obj(+f.dataset.id), i = o.issues.find(x => x.id === +f.dataset.iid);
    i.status = d.get("status"); const r = (d.get("resolution") || "").trim(); if (r) i.resolution = r;
    i.resolved = i.status === "resolved" ? iso(TODAY()) : null;
    save(); flash("Статус обновлён"); route();
  },
  act(f, d) {
    const o = obj(+f.dataset.id), code = f.dataset.code, t = TASKS_BY_CODE[code], [, ops] = opsForTask(code, o.systems), date = d.get("date");
    if (!date || date > iso(TODAY())) { flash("Дата не может быть в будущем", "error"); return route(); }
    const marks = ops.map(([c, text]) => ({code: c, text, status: d.get("st_" + c) || "skip", note: (d.get("n_" + c) || "").trim()}));
    const done = marks.filter(m => m.status !== "skip"), defects = marks.filter(m => m.status === "defect");
    if (!done.length) { flash("Отметьте хотя бы одну выполненную операцию", "error"); return route(); }
    const note = (d.get("note") || "").trim(), jid = nid();
    o.journal.push({id: jid, date, task: code, system: t.system || "", type: "Техническое обслуживание",
      desc: `${t.title}: выполнено операций — ${done.length}` + (defects.length ? `, неисправностей — ${defects.length}` : "") + (note ? ". " + note : ""),
      result: defects.length ? RESULTS[1] : RESULTS[0], performer: (d.get("performer") || "").trim() || userName(), by: userName(),
      ops: marks.map(({code, status, note}) => ({code, status, note}))});
    defects.forEach(m => addIssue(o, `${SYSTEMS[t.system]?.name || ""}: ${m.text.slice(0, 150)}`, m.note, "medium"));
    done.forEach(m => { if (MT.OP_TASK[m.code]) markDone(o, MT.OP_TASK[m.code], date); });
    markDone(o, code, date); save();
    flash(`Акт ТО сохранён: ${done.length} операций` + (defects.length ? `, замечаний: ${defects.length}` : ""));
    go(`#/o/${o.id}/actview/${jid}`);
  },
  prices(f, d) {
    const items = {};
    for (const it of MT.PRICES) {
      const ov = {};
      for (const k of ["min", "max", "mult"]) { const v = parseFloat(String(d.get(`${k}_${it.code}`) || "").replace(",", ".")); if (!isNaN(v)) ov[k] = v; }
      if (Object.keys(ov).length) items[it.code] = ov;
    }
    DB.prices = {coef: parseFloat(String(d.get("coef") || "1").replace(",", ".")) || 1, items};
    save(); flash("Цены сохранены — бюджеты объектов пересчитаны"); route();
  },
  client(f, d) {
    DB.clients.push({id: nid(), name: d.get("name").trim(), inn: d.get("inn"), contact: d.get("contact"), phone: d.get("phone")});
    save(); flash("Организация добавлена"); route();
  },
};
document.addEventListener("submit", e => {
  const f = e.target.closest("form[data-form]"); if (!f) return;
  e.preventDefault(); FORMS[f.dataset.form](f, new FormData(f));
});
document.addEventListener("change", e => {
  const el = e.target;
  if (el.dataset.act === "role") {
    ROLE = el.value === "p" ? {mode: "provider"} : {mode: "client", clientId: +el.value};
    localStorage.setItem(ROLE_KEY, JSON.stringify(ROLE));
    flash(isProv() ? "Вы вошли как обслуживающая организация" : "Вы вошли как эксплуатант: " + client(ROLE.clientId).name);
    go("#/");
  }
  if (el.dataset.act === "import" && el.files[0]) {
    const rd = new FileReader();
    rd.onload = () => { try { const x = JSON.parse(rd.result); if (!x.objects) throw 0; DB = x; save(); flash("Данные загружены"); go("#/"); }
                        catch (err) { flash("Это не файл данных «Мониторинга»", "error"); route(); } };
    rd.readAsText(el.files[0]);
  }
});
document.addEventListener("click", e => {
  const el = e.target.closest("[data-act]"); if (!el || el.tagName === "SELECT" || el.tagName === "INPUT") return;
  const act = el.dataset.act;
  if (act === "export") {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(DB, null, 1)], {type: "application/json"}));
    a.download = `monitoring-demo-${iso(TODAY())}.json`; a.click();
  }
  if (act === "reset" && confirm("Удалить все внесённые данные и вернуть демо-объекты?")) { DB = seed(); save(); flash("Демо-данные восстановлены"); go("#/"); }
  if (act === "archive" && confirm("Перенести объект в архив?")) { obj(+el.dataset.id).archived = true; save(); flash("Объект в архиве"); go("#/"); }
});
window.addEventListener("hashchange", route);
load(); route();
