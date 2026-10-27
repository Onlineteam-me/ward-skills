#!/usr/bin/env python3
"""
backup.py — дамп таблиц парсинг-конвейера в JSON.

Покрывает 4 таблицы: Источники, Отобранные новости, Единицы контента, Отсеяно.
Каждая таблица = свой JSON-файл с записями + схемой полей (для восстановления).
Бэкап = один каталог YYYY-MM-DD_HHMM/ внутри storage.backups_dir
(по умолчанию — workspace/_teable_backups внутри скилла).

Использование:
  python3 backup.py                          # обычный бэкап (по дате)
  python3 backup.py --tag pre-cleanup        # с тегом в имени каталога
  python3 backup.py --rotate 30              # удалить бэкапы старше 30 дней

🔴 НЕ автоматически удаляет — `--rotate` только при явном флаге.
"""
import sys, os, json, datetime, shutil, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from teable import CFG, T, H, BASE, require_config  # переиспользуем конфиг и заголовки

_SKILL_ROOT = os.path.dirname(HERE)
ROOT = (CFG.get("storage", {}).get("backups_dir") or "").strip() \
    or os.path.join(_SKILL_ROOT, "workspace", "_teable_backups")

def fetch(url):
    req = urllib.request.Request(url, headers=H)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()[:300]}

def backup_table(table_id, name, out_dir):
    """Дампит одну таблицу: схема + все записи."""
    schema = fetch(f"{BASE}/table/{table_id}/field")
    views = fetch(f"{BASE}/table/{table_id}/view")
    records = []
    # пагинация на случай больших таблиц
    skip = 0
    while True:
        page = fetch(f"{BASE}/table/{table_id}/record?take=500&skip={skip}&fieldKeyType=name")
        if isinstance(page, dict) and "records" in page:
            chunk = page["records"]
            records.extend(chunk)
            if len(chunk) < 500:
                break
            skip += 500
        else:
            # ошибка чтения — пишем в файл что было, плюс ошибку
            err = page.get("error", "unknown")
            print(f"  ! {name}: ошибка чтения records — {err[:120]}")
            break
    out_path = os.path.join(out_dir, f"{name}.json")
    json.dump({
        "table_id": table_id,
        "table_name": name,
        "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "schema": schema,
        "views": views,
        "records_count": len(records),
        "records": records,
    }, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  ✓ {name}: {len(records)} записей → {os.path.basename(out_path)}")
    return len(records)

def main():
    args = sys.argv[1:]
    tag = None
    if "--tag" in args:
        tag = args[args.index("--tag") + 1]
    if "--rotate" in args:
        days = int(args[args.index("--rotate") + 1])
        rotate(days)
        return

    require_config()
    today = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    suffix = f"_{tag}" if tag else ""
    out_dir = os.path.join(ROOT, today + suffix)
    os.makedirs(out_dir, exist_ok=True)
    print(f"бэкап → {out_dir}")

    tables = [
        ("sources",       "Источники"),
        ("selected",      "Отобранные новости"),
        ("content_units", "Единицы контента"),
        ("rejected",      "Отсеяно"),
    ]
    total = 0
    for key, human in tables:
        total += backup_table(T[key], human, out_dir)
    print(f"\nИтого: {total} записей в 4 таблицах")
    print(f"📂 {out_dir}")

def rotate(days):
    """Удалить каталоги старше N дней."""
    if not os.path.isdir(ROOT):
        print("нет каталога бэкапов — нечего ротировать")
        return
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    removed = 0
    for name in os.listdir(ROOT):
        path = os.path.join(ROOT, name)
        if not os.path.isdir(path):
            continue
        # имя начинается с YYYY-MM-DD
        try:
            dt = datetime.datetime.strptime(name[:10], "%Y-%m-%d")
        except ValueError:
            continue
        if dt < cutoff:
            shutil.rmtree(path)
            removed += 1
            print(f"  - удалён {name}")
    print(f"\nудалено старых бэкапов: {removed} (порог {days} дней)")

if __name__ == "__main__":
    main()
