#!/usr/bin/env python3
"""
cleanup_zombies.py — автоматическая чистка таблицы «Отобранные новости».
Удаляет записи со Статус=Новое, у которых Дата новости старше 7 дней.
Можно запускать cron-задачей (например, каждые 3 часа) как страховочную сетку.

Причина: другие Claude-сессии могут писать в Teable API напрямую,
обходя защиты teable.py. Этот скрипт ловит мусор постфактум.
"""
import json, os, re, datetime, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def load_yaml_simple(path):
    cfg = {}
    stack = [(-1, cfg)]
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        key, _, val = line.strip().partition(":")
        val = re.split(r"\s+#", val, maxsplit=1)[0].strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if val == "":
            d = {}
            parent[key] = d
            stack.append((indent, d))
        else:
            if val.startswith("[") and val.endswith("]"):
                parent[key] = [x.strip().strip('"').strip("'") for x in val[1:-1].split(",") if x.strip()]
            else:
                parent[key] = val.strip().strip('"').strip("'")
    return cfg

CFG = load_yaml_simple(os.path.join(ROOT, "config", "settings.yml"))
_SEC_PATH = os.path.join(ROOT, "config", "secrets.yml")
SEC = load_yaml_simple(_SEC_PATH) if os.path.exists(_SEC_PATH) else {}
TOKEN = os.environ.get("TEABLE_API_TOKEN") or SEC.get("teable_api_token")
BASE = CFG["teable"]["base_url"]
TABLE = CFG["teable"]["tables"]["selected"]
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

MAX_AGE_DAYS = 7

def api(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=H, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:300]}

def main():
    if not TOKEN or "{{" in str(BASE) or "{{" in str(TABLE):
        print("⚠ STOP: скилл не настроен — заполни config/settings.yml (заглушки {{...}}) и config/secrets.yml")
        return
    cutoff = datetime.datetime.now() - datetime.timedelta(days=MAX_AGE_DAYS)
    s, data = api("GET", f"{BASE}/table/{TABLE}/record?take=500&fieldKeyType=name")
    if s != 200:
        print(f"ERR: не смог получить записи: {s}")
        return
    records = data.get("records", [])
    zombies = []
    for r in records:
        f = r.get("fields", {})
        if f.get("Статус") != "Новое":
            continue
        nd = f.get("Дата новости", "")
        try:
            news_dt = datetime.datetime.fromisoformat(str(nd).replace("Z", "").split("T")[0])
            if news_dt < cutoff:
                zombies.append((r["id"], f.get("Заголовок", "?")[:50], str(nd)[:10]))
        except (ValueError, TypeError):
            pass
    if not zombies:
        print(f"cleanup: чисто, зомби нет (проверено {len(records)} записей)")
        return
    deleted = 0
    for rid, title, date in zombies:
        ds, _ = api("DELETE", f"{BASE}/table/{TABLE}/record/{rid}")
        if ds in (200, 204):
            deleted += 1
    print(f"cleanup: удалено {deleted}/{len(zombies)} зомби (Новое + старше {MAX_AGE_DAYS}д)")
    for _, title, date in zombies[:5]:
        print(f"  - {date} | {title}")
    if len(zombies) > 5:
        print(f"  ... и ещё {len(zombies)-5}")

if __name__ == "__main__":
    main()
