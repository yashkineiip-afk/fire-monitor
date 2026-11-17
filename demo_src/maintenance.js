// ===== Регламенты ТО по ГОСТ и бюджет (логика; данные — MT из maintenance.py) =====
function mtPeriodLabel(m) {
  if (MT.PERIOD_LABELS[String(m)]) return MT.PERIOD_LABELS[String(m)];
  return ({1:"ежемесячно", 3:"раз в квартал", 6:"раз в полгода", 12:"раз в год", 36:"раз в 3 года", 60:"раз в 5 лет"})[m] || `раз в ${m} мес.`;
}
function opsKey(sys, s) { return sys === "aupt" ? (MT.AUPT_GROUPS[(s.aupt || {}).kind || ""] || "aupt_water") : sys; }
function opsForTask(code, s) {
  const sc = MT.TASK_OPS[code];
  if (!sc || !(sc in s)) return [null, []];
  const key = opsKey(sc, s); return [key, MT.OPS[key] || []];
}
const OP_TEXT = {}; for (const ops of Object.values(MT.OPS)) for (const [c, t, , r] of ops) OP_TEXT[c] = [t, r];
const OP_STATUS = {ok: "Выполнено, норма", defect: "Выявлена неисправность", skip: "Не выполнялось"};

function opsLastDone(o) {
  const last = {};
  for (const j of o.journal || []) for (const op of j.ops || [])
    if (op.status !== "skip" && (!last[op.code] || last[op.code] < j.date)) last[op.code] = j.date;
  return last;
}
function opsStatus(ops, last) {
  const today = TODAY();
  return ops.map(([code, text, per, ref]) => {
    const l = last[code]; let status, due = null;
    if (per <= 0) status = "info";
    else if (!l) status = "nodata";
    else { due = addMonths(parse(l), per); const d = days(due, today); status = d < 0 ? "overdue" : d <= (per <= 1 ? 7 : 30) ? "soon" : "ok"; }
    return {code, text, period: per, periodLabel: mtPeriodLabel(per), ref, last: l || null, due: due ? iso(due) : null, status};
  });
}
function regulations(o) {
  const last = opsLastDone(o), out = [], seen = new Set();
  for (const code of Object.keys(o.systems)) {
    if (!SYSTEMS[code]) continue;
    const key = opsKey(code, o.systems); if (seen.has(key) || !MT.OPS[key]) continue; seen.add(key);
    const rows = opsStatus(MT.OPS[key], last);
    out.push({system: code, key, name: SYSTEMS[code].name, ops: rows,
              overdue: rows.filter(r => r.status === "overdue").length, nodata: rows.filter(r => r.status === "nodata").length});
  }
  return out;
}

function quantity(key, p, s, oldSystems) {
  const area = num(p.area_m2), g = (sys, k) => num((s[sys] || {})[k]);
  const r = (v, est) => [v, est];
  switch (key) {
    case "one": return r(1, false);
    case "aps_devices": return g("aps","detectors") ? r(g("aps","detectors"), false) : r(Math.max(5, Math.round(area / 25)), true);
    case "soue_units": return g("soue","units") ? r(g("soue","units"), false) : r(Math.max(2, Math.round(area / 80)), true);
    case "aupt_area": return g("aupt","area") ? r(g("aupt","area"), false) : r(area || 500, true);
    case "aupt_modules": return g("aupt","modules") ? r(g("aupt","modules"), false) : r(Math.max(2, Math.round((g("aupt","area") || area || 200) / 50)), true);
    case "smoke_units": return g("smoke","units") ? r(g("smoke","units"), false) : r(4, true);
    case "vpv_cranes": return g("vpv","cranes") ? r(g("vpv","cranes"), false) : r(Math.max(2, Math.round(area / 800)), true);
    case "pump_units": return g("pumps","units") ? r(g("pumps","units"), false) : r(2, true);
    case "hydrants": return g("outer_water","count") ? r(g("outer_water","count"), false) : r(1, true);
    case "ext_count": return g("extinguishers","count") ? r(g("extinguishers","count"), false) : r(Math.max(2, Math.round(area / 100)), true);
    case "fireproof_area": return g("fireproof","area") ? r(g("fireproof","area"), false) : r(1000, true);
    case "ladders": return g("ladders","count") ? r(g("ladders","count"), false) : r(1, true);
    case "elight": return g("emergency_light","count") ? r(g("emergency_light","count"), false) : r(Math.max(4, Math.round(area / 50)), true);
    case "ozk": return g("ventilation","ozk_count") ? r(g("ventilation","ozk_count"), false) : r(2, true);
    case "old_systems": return r(oldSystems, false);
  }
  return r(0, false);
}
function pricePerEvent(it, qty, mult) {
  let lo = 0, hi = 0;
  if (it.kind === "fixed") { lo = it.min; hi = it.max; }
  else if (it.kind === "unit") {
    lo = qty * it.min; hi = qty * it.max;
    if (it.min_charge) { lo = Math.max(lo, it.min_charge[0]); hi = Math.max(hi, it.min_charge[1]); }
  } else if (it.kind === "tier") {
    const t = it.tiers.find(([upto]) => qty <= upto);
    if (t) { lo = t[1]; hi = t[2]; }
    else { const [u, a, b] = it.tiers[it.tiers.length - 1], st = Math.ceil((qty - u) / it.step); lo = a + st * it.extra[0]; hi = b + st * it.extra[1]; }
  } else if (it.kind === "base_area") {
    const st = Math.max(0, Math.ceil((qty - it.upto) / it.step)); lo = it.base[0] + st * it.extra[0]; hi = it.base[1] + st * it.extra[1];
  }
  return [lo * mult, hi * mult];
}
function priceItems() {
  const ov = (DB.prices && DB.prices.items) || {};
  return MT.PRICES.map(it => {
    const x = {...it}, o = ov[it.code] || {};
    if (["unit", "fixed"].includes(it.kind)) { if (o.min != null) x.min = o.min; if (o.max != null) x.max = o.max; x.mult = 1; }
    else x.mult = o.mult != null ? o.mult : 1;
    return x;
  });
}
function budget(o) {
  const p = o.profile, s = o.systems, coef = (num(p.price_coef) || 1) * ((DB.prices && DB.prices.coef) || 1);
  const rows = taskRows(o), byTask = Object.fromEntries(rows.map(t => [t.code, t]));
  const ak = "aupt" in s ? opsKey("aupt", s) : null, old = overLife(s, TODAY().getFullYear()).length;
  const lines = [], skipped = [];
  for (const it of priceItems()) {
    const t = byTask[it.task]; if (!t) continue;
    if (it.when === "aupt_water" && ak !== "aupt_water") continue;
    if (it.when === "aupt_modules" && (!ak || ak === "aupt_water")) continue;
    const [qty, est] = quantity(it.qty, p, s, old); if (!qty) continue;
    const perYear = 12 / Math.max(1, t.period), [lo, hi] = pricePerEvent(it, qty, it.mult);
    lines.push({title: it.title, qty, est, unit: it.unit, perYear, eMin: lo * coef, eMax: hi * coef,
                yMin: lo * coef * perYear, yMax: hi * coef * perYear, priceEst: !!it.est});
  }
  rows.forEach(t => { if (MT.NOT_PRICED[t.code]) skipped.push([t.title, MT.NOT_PRICED[t.code]]); });
  const yMin = lines.reduce((a, l) => a + l.yMin, 0), yMax = lines.reduce((a, l) => a + l.yMax, 0);
  return {lines, skipped, yMin, yMax, coef};
}
const rub = v => Math.round(v).toLocaleString("ru-RU") + " ₽";
