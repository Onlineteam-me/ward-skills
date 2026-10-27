#!/usr/bin/env python3
"""
teable.py — движок записи parsing-ward. НЕ писать заново каждый раз.

Команды:
  python teable.py write <rows.json>     # пишет отобранное в «Отобранные новости» (Статус=Новое)
  python teable.py reject <rows.json>     # пишет низкие примеры в «Отсеяно (калибровка)»
  python teable.py sweep                   # переносит Статус=Отклонено из Отобранных в Отсеяно
  python teable.py queue                   # печатает Утверждённое без линка «Единицы контента» (очередь на контент)
  python teable.py seen                    # печатает все известные URL (для дедупа) -> stdout
  python teable.py make_unit <unit.json>   # переносит утверждённую новость в «Единицы контента»
  python teable.py add_source "Имя" "URL" "RSS" <кластер>   # добавить источник в реестр
  python teable.py toggle_source "Имя" on|off               # включить/выключить источник
  python teable.py del_source "Имя"                         # удалить источник
  python teable.py check                   # проверить конфиг и доступ к Teable (первый запуск)

rows.json — список объектов. Поля «Отобранные новости»:
  Заголовок, "Заголовок (RU)", "Дата новости" (ISO|YYYY-MM-DD), Суть,
  "Ссылка на источник" ("Источник — URL"), Рекомендация ([...]), Релевантность (int), Комментарий?
ID и «Дата парсинга» проставляются автоматически.
"""
import sys, json, os, re, datetime, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def load_yaml_simple(path):
    """Минимальный YAML-ридер (без зависимостей): ключи, вложенность 2 уровня, списки [..]."""
    cfg = {}
    stack = [(-1, cfg)]
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        key, _, val = line.strip().partition(":")
        val = re.split(r"\s+#", val, maxsplit=1)[0].strip()  # срезать inline-комментарий
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
T = CFG["teable"]["tables"]
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def is_placeholder(v):
    """Значение не настроено: пусто или осталась заглушка {{...}}."""
    return not v or "{{" in str(v)

def config_problems():
    """Список того, что не настроено перед запуском (заглушки, токен)."""
    probs = []
    if is_placeholder(BASE):
        probs.append("teable.base_url — заглушка, впиши адрес API Teable")
    for k, v in T.items():
        if is_placeholder(v):
            probs.append(f"teable.tables.{k} — заглушка, впиши ID таблицы")
    if not TOKEN or "xxxx" in str(TOKEN):
        probs.append("токен Teable не задан: создай config/secrets.yml по образцу secrets.example.yml "
                     "или задай env TEABLE_API_TOKEN")
    return probs

def require_config():
    probs = config_problems()
    if probs:
        print("⚠ STOP: скилл ещё не настроен (см. README.md → «Перед первым запуском»):")
        for p in probs:
            print(f"    — {p}")
        sys.exit(2)

def api(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=H, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:300]}

def get_records(table, view=None):
    url = f"{BASE}/table/{table}/record?take=1000&fieldKeyType=name"
    if view:
        url += f"&viewId={view}"
    s, d = api("GET", url)
    return d.get("records", []) if s == 200 else []

def all_known_urls():
    """URL из Отобранных + Отсеяно + Единиц контента (для дедупа).
    Единицы обязательны: make_unit УДАЛЯЕТ строку из «Отобранных», и без этой
    таблицы уже отработанная новость снова считается новой (повторная запись)."""
    urls = set()
    for tbl in (T["selected"], T["rejected"], T["content_units"]):
        for r in get_records(tbl):
            for k in ("Ссылка на источник", "Ссылка"):
                v = (r["fields"].get(k) or "").strip()
                if v:
                    # обратная совместимость: старые записи могли иметь "Имя — URL"
                    urls.add(v.split("—")[-1].strip() if "—" in v else v)
    return urls

def next_id_base():
    today = datetime.datetime.now().strftime("%Y%m%d")
    prefix = int(today) * 1000
    mx = prefix
    for r in get_records(T["selected"]):
        v = r["fields"].get("ID")
        if isinstance(v, (int, float)) and prefix <= int(v) < prefix + 1000:
            mx = max(mx, int(v))
    return mx  # вернёт prefix или последний; +1 при использовании

MAX_ROWS_PER_RUN = 15
MAX_NEWS_AGE_DAYS = 7
LOCK_FILE = os.path.join(ROOT, "workspace", ".write_lock")
MIN_HOURS_BETWEEN_RUNS = 20

def check_write_lock():
    """Не даёт запускать write чаще чем раз в MIN_HOURS_BETWEEN_RUNS часов."""
    if os.path.exists(LOCK_FILE):
        try:
            ts = float(open(LOCK_FILE).read().strip())
            elapsed_h = (datetime.datetime.now().timestamp() - ts) / 3600
            if elapsed_h < MIN_HOURS_BETWEEN_RUNS:
                return False, f"Парсинг уже был {elapsed_h:.1f}ч назад (лимит {MIN_HOURS_BETWEEN_RUNS}ч). Лок: {LOCK_FILE}"
        except (ValueError, OSError):
            pass
    return True, ""

def set_write_lock():
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    with open(LOCK_FILE, "w") as f:
        f.write(str(datetime.datetime.now().timestamp()))

def cmd_write(rows_path):
    ok, msg = check_write_lock()
    if not ok:
        print(f"ABORT: {msg}")
        sys.exit(1)
    rows = json.load(open(rows_path, encoding="utf-8"))
    if len(rows) > MAX_ROWS_PER_RUN:
        print(f"ABORT: {len(rows)} строк > лимит {MAX_ROWS_PER_RUN}. Похоже на баг — проверь источник.")
        sys.exit(1)
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(days=MAX_NEWS_AGE_DAYS)
    known = all_known_urls()
    pd = now.strftime("%Y-%m-%dT00:00:00.000Z")
    base = next_id_base()
    recs = []
    skipped_old = []
    skipped_dup = []
    for i, r in enumerate(rows, 1):
        f = {k: v for k, v in r.items() if v not in (None, "")}
        nd = f.get("Дата новости", "")
        try:
            news_dt = datetime.datetime.fromisoformat(str(nd).replace("Z", "").split("T")[0])
            if news_dt < cutoff:
                skipped_old.append(f.get("Заголовок", "?")[:50])
                continue
        except (ValueError, TypeError):
            pass
        url = f.get("Ссылка на источник", "")
        if url and url in known:
            skipped_dup.append(f.get("Заголовок", "?")[:50])
            continue
        f["Статус"] = "Новое"
        f["Дата парсинга"] = pd
        f["ID"] = base + i
        if nd and "T" not in str(nd):
            f["Дата новости"] = f"{nd}T00:00:00.000Z"
        recs.append({"fields": f})
    if skipped_old:
        print(f"SKIP (старше {MAX_NEWS_AGE_DAYS}д): {len(skipped_old)} — {skipped_old}")
    if skipped_dup:
        print(f"SKIP (дубль URL): {len(skipped_dup)} — {skipped_dup}")
    if not recs:
        print("write: 0 записей после фильтрации, ничего не пишем."); return
    s, d = api("POST", f"{BASE}/table/{T['selected']}/record",
               {"fieldKeyType": "name", "records": recs})
    written = len(d.get('records', []))
    print(f"write: status {s}, записано {written}/{len(recs)}")
    if s in (200, 201) and written > 0:
        set_write_lock()
        print(f"  lock set — следующий write возможен через {MIN_HOURS_BETWEEN_RUNS}ч")
    elif s not in (200, 201):
        print("  ERR:", d.get("error"))

def cmd_reject(rows_path):
    rows = json.load(open(rows_path, encoding="utf-8"))
    recs = [{"fields": {k: v for k, v in r.items() if v not in (None, "")}} for r in rows]
    s, d = api("POST", f"{BASE}/table/{T['rejected']}/record",
               {"fieldKeyType": "name", "records": recs})
    print(f"reject: status {s}, записано {len(d.get('records', []))}/{len(recs)}")

def cmd_sweep():
    """Переносит Статус=Отклонено из «Отобранных» в «Отсеяно» зеркально (все поля 1-в-1)
    + штамп «Дата отсева» = сейчас. Поле «Единицы контента» не переносится (link)."""
    moved = 0
    today_iso = datetime.datetime.now().strftime("%Y-%m-%dT00:00:00.000Z")
    MIRROR = ["Заголовок", "Заголовок (RU)", "Дата парсинга", "Дата новости",
              "Суть", "Ссылка на источник", "Рекомендация",
              "Релевантность", "ID"]
    for r in get_records(T["selected"]):
        if r["fields"].get("Статус") != "Отклонено":
            continue
        f = r["fields"]
        payload = {k: f[k] for k in MIRROR if f.get(k) not in (None, "", [])}
        payload["Дата отсева"] = today_iso
        s, _ = api("POST", f"{BASE}/table/{T['rejected']}/record",
                   {"fieldKeyType": "name", "records": [{"fields": payload}]})
        if s in (200, 201):
            api("DELETE", f"{BASE}/table/{T['selected']}/record/{r['id']}")
            moved += 1
        else:
            print(f"  ERR sweep {r['id']}: {_}")
    print(f"sweep: перенесено в «Отсеяно» {moved}")

def cmd_queue():
    """Утверждённое без линка «Единицы контента», отсортировано по Релевантность ↓
    (правило строка-целиком: берём самое горячее первым)."""
    out = []
    view = CFG["teable"].get("selected_view")
    for r in get_records(T["selected"], None if is_placeholder(view) else view):
        f = r["fields"]
        if f.get("Статус") == "Утверждено":
            out.append({"id": r["id"], "ID": f.get("ID"),
                        "Релевантность": f.get("Релевантность") or 0,
                        "Заголовок": f.get("Заголовок (RU)") or f.get("Заголовок"),
                        "Рекомендация": f.get("Рекомендация", []),
                        "Ссылка": f.get("Ссылка на источник", ""),
                        "Суть": f.get("Суть", "")})
    out.sort(key=lambda x: -x["Релевантность"])
    print(json.dumps(out, ensure_ascii=False, indent=2))

def cmd_check():
    """Проверка настройки: заглушки, токен, доступ к каждой таблице."""
    probs = config_problems()
    if probs:
        print("⚠ Не настроено:")
        for p in probs:
            print(f"    — {p}")
        return
    for k, tid in T.items():
        s, d = api("GET", f"{BASE}/table/{tid}/record?take=1&fieldKeyType=name")
        print(f"  {'✓' if s == 200 else '✗'} {k}: status {s}" + ("" if s == 200 else f" — {d.get('error','')[:120]}"))
    lr = CFG.get("storage", {}).get("local_root")
    print(f"  {'✓' if not is_placeholder(lr) and os.path.isdir(lr) else '⚠'} storage.local_root: {lr}")

def cmd_seen():
    print("\n".join(sorted(all_known_urls())))

def cmd_make_unit(unit_path):
    """Создать строку в «Единицы контента» из JSON и связать с новостью-источником.
    ID единицы наследуется от ID новости (трассируемость).
    JSON: {"news_id": "rec...", "Заголовок (RU)": "...", "Форматы": [...],
           "Заготовка": "...ОБЯЗАТЕЛЬНО...",
           поля контента: "Карусель" (attachments), "Подпись к карусели", "Тред",
           "Статья RU"/EN, "Сценарий видео (сам)"/"(аватар)", "Drive папка" (локальный путь)}.

    🔴 «Заготовка» ОБЯЗАТЕЛЬНА (≥300 симв, ≥3 цифры, ≥2 цитаты, контраст) — без неё ABORT. Правило #13.
    """
    u = json.load(open(unit_path, encoding="utf-8"))
    news_rec_id = u.pop("news_id")

    # 🔴 Валидация «Заготовки» — глубокий разбор источника после WebFetch (правило #13).
    # 5 обязательных компонентов: длина, цифры, цитаты, контраст, тезис/хук.
    zagotovka = (u.get("Заготовка") or "").strip()
    errs = []
    if len(zagotovka) < 300:
        errs.append(f"длина {len(zagotovka)} < 300 симв")
    # Цифры: %, $, млрд/млн/K/k, версии, годы, счётчики (не менее 3 разных)
    digit_matches = re.findall(r"\d[\d.,]*\s*(?:%|\$|€|₴|k|K|M|B|млн|млрд|тыс|USDT|BTC|ETH|монет|бирж|трейдер|пользовател|человек|раз|дней|час|минут|лет|мес)|\$\d|[xх]\d+|№\s*\d+|\d{4}\s*г|20\d{2}", zagotovka)
    if len(set(digit_matches)) < 3:
        errs.append(f"цифр/фактов {len(set(digit_matches))} < 3 (нужно 3 разных: суммы/%/версии/годы)")
    # Цитаты: любые кавычки — прямые "…", ёлочки «…», одинарные "…"
    quotes = re.findall(r"[«\"“]([^«»\"“”\n]{20,})[»\"”]", zagotovka)
    if len(quotes) < 2:
        errs.append(f"прямых цитат {len(quotes)} < 2 (нужно 2 в кавычках длиной ≥20 симв)")
    # Контраст «было→стало»
    contrast_markers = re.findall(r"(?im)^\s*(было|стало|раньше|теперь|до\b|после\b|old|new|before|after)\s*[:—\-]", zagotovka)
    if not contrast_markers:
        errs.append("нет явного контраста «было → стало» (маркеры: 'Было:', 'Стало:', 'Раньше:', 'Теперь:')")
    if errs:
        print("⚠ ABORT: «Заготовка» не проходит валидацию (правило #13):")
        for e in errs:
            print(f"    — {e}")
        print("  WebFetch по «Ссылка на источник» → собрать разбор с цитатами/цифрами/контрастом.")
        print("  См. workflows/content_batch.md → Шаг 2, SKILL.md правило #13.")
        return

    # 🔴 Валидация «Drive папка» — обязательный локальный путь (правило #17).
    local_root = (CFG.get("storage", {}).get("local_root") or "").strip()
    if is_placeholder(local_root) or not os.path.isabs(local_root):
        print("⚠ ABORT: в config/settings.yml не настроен storage.local_root "
              "(абсолютный путь к локальной папке медиа). Заполни заглушку {{CONTENT_FACTORY_DIR}}.")
        return
    LOCAL_PREFIX = local_root.rstrip("/") + "/"
    drive_papka = (u.get("Drive папка") or "").strip()
    if not drive_papka:
        print(f"⚠ ABORT: поле «Drive папка» пустое. Укажи локальный путь, начинающийся с {LOCAL_PREFIX}")
        return
    if drive_papka.startswith("https://drive.google.com"):
        print(f"⚠ ABORT: «Drive папка» содержит URL облачного диска. Используем ТОЛЬКО локальные пути. Замени на {LOCAL_PREFIX}<название>/")
        return
    if not drive_papka.startswith(LOCAL_PREFIX):
        print(f"⚠ ABORT: «Drive папка» должна начинаться с {LOCAL_PREFIX}, получено: {drive_papka[:80]}")
        return

    s, d = api("GET", f"{BASE}/table/{T['selected']}/record/{news_rec_id}?fieldKeyType=name")
    if s != 200:
        print("ERR: не найдена новость", news_rec_id); return
    nf = d.get("fields", {})
    inherited_id = nf.get("ID")
    news_url = (nf.get("Ссылка на источник") or "").strip().rstrip("/")
    news_ru = (nf.get("Заголовок (RU)") or "").strip()
    news_en = (nf.get("Заголовок") or "").strip()

    # 🔴 SAFETY-CHECK: не дублировать уже существующую единицу контента.
    # Проверяем по ID, URL, Заголовок (RU), Заголовок (EN).
    for existing in get_records(T["content_units"]):
        ef = existing["fields"]
        match = None
        if inherited_id and ef.get("ID") == inherited_id:
            match = f"ID={inherited_id}"
        elif news_url and (ef.get("Ссылка на источник") or "").strip().rstrip("/") == news_url:
            match = "URL"
        elif news_ru and (ef.get("Заголовок (RU)") or "").strip() == news_ru:
            match = "Заголовок (RU)"
        elif news_en and (ef.get("Заголовок") or "").strip() == news_en:
            match = "Заголовок (EN)"
        if match:
            print(f"⚠ ABORT: единица контента уже существует (совпадение по {match}).")
            print(f"  Существующий юнит: {existing['id']} — {ef.get('Заголовок (RU)') or ef.get('Заголовок','?')[:60]}")
            print(f"  Новость НЕ удаляется из «Отобранных», юнит НЕ создаётся.")
            return
    u["ID"] = inherited_id
    for src_field, dst_field in [
        ("Заголовок (RU)",     "Заголовок (RU)"),
        ("Заголовок",          "Заголовок"),
        ("Суть",               "Суть"),
        ("Ссылка на источник", "Ссылка на источник"),
        ("Дата парсинга",      "Дата парсинга"),
        ("Дата новости",       "Дата новости"),
        ("Релевантность",      "Релевантность"),
    ]:
        if dst_field not in u and nf.get(src_field) not in (None, ""):
            u[dst_field] = nf[src_field]
    # 🔴 ССЫЛКА НА ИСТОЧНИК обязана перенестись на юнит (правило 2026-06-29):
    # без неё карусель не соберёт слайд-источник (скрин-пруф). Перелинк «Источник» остаётся
    # резервным путём, но URL-поле должно быть заполнено явно.
    if not u.get("Ссылка на источник"):
        print(f"  ⚠ ВНИМАНИЕ: у новости {news_rec_id} пустая «Ссылка на источник» — "
              f"юнит создаётся БЕЗ URL источника. Карусель не сможет сделать слайд-источник. "
              f"Заполни «Ссылка на источник» в новости и пере-создай, либо достань URL по перелинку.")
    # 🔴 Жизненный цикл: Принято (parsing-ward ставит сразу) → На правки (редактор, если что-то править)
    # Per-format статусы публикации: Post Insta + Threads пост = «Не опубликован» (zernio меняет на «Опубликован»).
    u["Статус"] = u.get("Статус", "Принято")
    u.setdefault("Post Insta", "Не опубликован")
    u.setdefault("Threads пост", "Не опубликован")
    payload = {k: v for k, v in u.items() if v not in (None, "", [])}
    s, d = api("POST", f"{BASE}/table/{T['content_units']}/record",
               {"fieldKeyType": "name", "records": [{"fields": payload}]})
    if s in (200, 201):
        unit_rec_id = d["records"][0]["id"]
        # 🔴 Ставим новую запись НА ВЕРХ default view (правило #14) — свежее всегда сверху.
        view_id = CFG["teable"].get("content_units_view")
        if is_placeholder(view_id):
            print("  ⚠ teable.content_units_view не настроен — запись не поднята наверх (создана в конце).")
            top_recs = []
        else:
            top_recs = get_records(T["content_units"], view_id)
            top_recs = [r for r in top_recs if r["id"] != unit_rec_id]
        if top_recs:
            anchor_id = top_recs[0]["id"]
            ps, pd = api("PUT", f"{BASE}/table/{T['content_units']}/view/{view_id}/record-order",
                         {"anchorId": anchor_id, "position": "before", "recordIds": [unit_rec_id]})
            if ps not in (200, 201):
                print(f"  ⚠ не удалось поставить наверх: {pd}")
        # Перенос: удаляем строку из «Отобранных новостей» (inbox чистый).
        ds, _ = api("DELETE", f"{BASE}/table/{T['selected']}/record/{news_rec_id}")
        if ds == 200:
            print(f"make_unit: создана {unit_rec_id} (ID {inherited_id}) наверху таблицы, новость {news_rec_id} удалена из «Отобранных»")
        else:
            print(f"make_unit: создана {unit_rec_id} (ID {inherited_id}), ⚠ не удалось удалить новость {news_rec_id}: {_}")
    else:
        print("ERR make_unit:", d)

def cmd_add_source(name, addr, stype, cluster):
    """Добавить источник в реестр «Источники». Дедуп по адресу."""
    for r in get_records(T["sources"]):
        if (r["fields"].get("Адрес") or "").rstrip("/") == addr.rstrip("/"):
            print(f"SKIP: источник с таким адресом уже есть — {r['fields'].get('Название')}")
            return
    payload = {"Название": name, "Адрес": addr, "Тип": stype,
               "Кластер": int(cluster), "Активен": True}
    s, d = api("POST", f"{BASE}/table/{T['sources']}/record",
               {"fieldKeyType": "name", "records": [{"fields": payload}]})
    if s in (200, 201):
        print(f"add_source: добавлен «{name}» ({stype}, кластер {cluster}) → {addr}")
    else:
        print(f"ERR add_source: status {s}", d.get("error"))

def cmd_toggle_source(needle, state):
    """Включить/выключить источник (поле «Активен») без удаления из реестра."""
    want = str(state).lower() in ("on", "true", "1", "да")
    for r in get_records(T["sources"]):
        f = r["fields"]
        if needle in (f.get("Название") or "") or needle in (f.get("Адрес") or ""):
            s, d = api("PATCH", f"{BASE}/table/{T['sources']}/record/{r['id']}",
                       {"fieldKeyType": "name", "record": {"fields": {"Активен": want}}})
            if s == 200:
                print(f"toggle_source: «{f.get('Название')}» → Активен={want}")
            else:
                print(f"ERR toggle_source: status {s}", d.get("error"))
            return
    print(f"toggle_source: не найден источник по «{needle}»")

def cmd_del_source(needle):
    """Удалить источник из реестра по названию или адресу (точное вхождение)."""
    for r in get_records(T["sources"]):
        f = r["fields"]
        if needle in (f.get("Название") or "") or needle in (f.get("Адрес") or ""):
            s, d = api("DELETE", f"{BASE}/table/{T['sources']}/record/{r['id']}")
            print(f"del_source: удалён «{f.get('Название')}» → {f.get('Адрес')} (status {s})")
            return
    print(f"del_source: не найден источник по «{needle}»")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "check":
        cmd_check(); sys.exit(0)
    if cmd in ("write", "add_source", "del_source", "toggle_source", "reject",
               "sweep", "queue", "seen", "make_unit"):
        require_config()
    if cmd == "write":   cmd_write(sys.argv[2])
    elif cmd == "add_source": cmd_add_source(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif cmd == "del_source": cmd_del_source(sys.argv[2])
    elif cmd == "toggle_source": cmd_toggle_source(sys.argv[2], sys.argv[3])
    elif cmd == "reject": cmd_reject(sys.argv[2])
    elif cmd == "sweep": cmd_sweep()
    elif cmd == "queue": cmd_queue()
    elif cmd == "seen":  cmd_seen()
    elif cmd == "make_unit": cmd_make_unit(sys.argv[2])
    else:
        print(__doc__)
