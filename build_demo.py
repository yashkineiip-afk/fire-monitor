"""Сборка демо-версии в один файл demo/index.html.
Регламенты ТО и цены берутся из maintenance.py, чтобы демо и полная версия совпадали.
Запуск: python build_demo.py
"""
import json
import os

import maintenance as mt

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "demo_src")


def read(name):
    with open(os.path.join(SRC, name), encoding="utf-8") as f:
        return f.read()


data = {
    "OPS": {k: [list(o) for o in v] for k, v in mt.OPS.items()},
    "TASK_OPS": mt.TASK_OPS, "AUPT_GROUPS": mt.AUPT_GROUPS, "OP_TASK": mt.OP_TASK,
    "PRICES": mt.PRICES, "NOT_PRICED": mt.NOT_PRICED, "PRICES_NOTE": mt.PRICES_NOTE,
    "PERIOD_LABELS": {str(k): v for k, v in mt.PERIOD_LABELS.items()},
}
maint_js = "const MT = " + json.dumps(data, ensure_ascii=False) + ";\n"

html = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Мониторинг ПБ — демо</title>
<style>
{read('style.css')}
</style></head>
<body><div id="app"></div>
<script>
{maint_js}
{read('norms.js')}
{read('maintenance.js')}
{read('app.js')}
</script></body></html>"""
os.makedirs(os.path.join(BASE, "demo"), exist_ok=True)
with open(os.path.join(BASE, "demo", "index.html"), "w", encoding="utf-8") as f:
    f.write(html)
print("demo/index.html:", len(html), "байт")
