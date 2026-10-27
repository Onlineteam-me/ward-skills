#!/usr/bin/env python3
"""ward-content-factory — служебный движок оркестратора (только стандартная библиотека Python).

Команды:
  check                         проверка подключений (мастер настройки, workflows/setup.md)
  summary                       сводка по статусам («что в работе»)
  list   [--status S]           список пуль (№ · статус · пуля · формат)
  show   N                      все поля пули №N
  next-number                   следующий свободный №
  add    --json FILE            создать пулю из JSON {"Поле": значение}
  set    N --field F (--value V | --file PATH)   записать одно поле пули №N
  status N STATUS [--note T]    перевести пулю №N в статус (проверяет порядок)
  infer  [--apply]              подобрать статусы по заполненным полям (перевод старой базы на модель)
  adapt  N --format F --platforms "TikTok,Instagram Reels" [--name] [--hook] [--text-file] [--caption-file] [--status]
                                создать адаптацию пули №N (связь с пулей ставится сама)
  adapt-list N                  адаптации пули №N (id · название · статус · площадки · дата)
  adapt-set REC --field F (--value V | --file PATH)   записать поле адаптации
  qc     (--unit N | --file PATH --kind K) [--json]   QC-гейт по красным линиям Ward

Ключи — config/secrets.yml или переменные окружения (TEABLE_API_TOKEN, ZERNIO_API_KEY, HEYGEN_API_KEY).
Токены никогда не печатаются.
"""
import argparse, json, os, re, sys, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Порядок статусов единицы контента — источник правды: knowledge/status_model.md
STATUSES = ["Идея", "Пуля", "Тексты готовы", "Медиа готовы", "На проверке", "Запланировано", "Опубликовано"]
REJECTED = "Отклонено"
LEGACY = {"В работе": "Пуля", "Готово": "Тексты готовы"}   # старые варианты → ближайший новый

UNIT_REQUIRED = ["Пуля", "№", "Статус", "Приоритет", "Сегмент ДНК", "Этап воронки", "Инсайт / боль",
                 "Формула хука", "Хук A", "Хук B", "Хук C", "Тезисы тела", "Формат", "CTA",
                 "Красные линии / проверить", "Сценарий HeyGen", "Threads-посты", "Текст карусели", "Адаптации"]
UNIT_RECOMMENDED = ["Аватар", "Папка с медиа", "QC-отчёт"]
ADAPT_REQUIRED = ["Название", "Формат", "Площадки", "Статус", "Сценарий / текст", "Подпись к публикации",
                  "Дата публикации", "Ссылка на публикацию", "Файлы", "Заметки", "Пуля"]
ADAPT_STATUS_RECOMMENDED = ["Запланировано"]


# ───────────────────────── конфиг ─────────────────────────
def _mini_yaml(text):
    """Мини-парсер YAML (вложенные словари, скаляры, inline-списки/словари). Хватает для наших конфигов."""
    root, stack = {}, [(-1, None)]
    stack[0] = (-1, root)
    for raw in text.splitlines():
        line = re.sub(r"\s+#.*$", "", raw) if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        ind = len(line) - len(line.lstrip())
        key, _, val = line.strip().partition(":")
        while stack[-1][0] >= ind:
            stack.pop()
        parent = stack[-1][1]
        val = val.strip()
        if val == "":
            parent[key] = {}
            stack.append((ind, parent[key]))
        else:
            parent[key] = _scalar(val)
    return root


def _scalar(v):
    if v.startswith(("[", "{")):
        j = re.sub(r"([{,]\s*)([A-Za-z_][\w]*)\s*:", r'\1"\2":', v)
        try:
            return json.loads(j)
        except ValueError:
            return v
    if v[:1] in "\"'":
        return v[1:-1]
    if v in ("true", "false"):
        return v == "true"
    if v in ("null", "~"):
        return None
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return v


def load_yaml(path):
    if not os.path.exists(path):
        return {}
    text = open(path, encoding="utf-8").read()
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return _mini_yaml(text)


SETTINGS = load_yaml(os.path.join(ROOT, "config", "settings.yml"))
SECRETS = load_yaml(os.path.join(ROOT, "config", "secrets.yml"))


def is_placeholder(v):
    return v is None or (isinstance(v, str) and (("{{" in v) or v.strip() in ("", "xxx") or v.endswith("_xxx")))


def secret(section, key, env):
    v = os.environ.get(env) or (SECRETS.get(section) or {}).get(key)
    return None if is_placeholder(v) else v


def cfg(*path):
    cur = SETTINGS
    for p in path:
        cur = (cur or {}).get(p) if isinstance(cur, dict) else None
    return cur


def placeholders(d=None, prefix=""):
    d = SETTINGS if d is None else d
    out = []
    for k, v in d.items():
        p = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out += placeholders(v, p)
        elif isinstance(v, str) and "{{" in v:
            out.append((p, v))
    return out


# ───────────────────────── HTTP ─────────────────────────
def http(method, url, headers, payload=None, timeout=60):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={**headers, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read()[:300].decode(errors="ignore")}
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, {"error": str(e)}


def teable(method, path, payload=None):
    token, base = secret("teable", "api_token", "TEABLE_API_TOKEN"), cfg("teable", "api_url")
    if not token or is_placeholder(base):
        sys.exit("✗ Teable не настроен: нужен api_url в settings.yml и api_token в secrets.yml. Запусти «настрой завод».")
    code, body = http(method, base.rstrip("/") + path, {"Authorization": "Bearer " + token}, payload)
    if code >= 300 or code == 0:
        sys.exit(f"✗ Teable {method} {path.split('?')[0]}: {code} {body.get('error', '')}")
    return body


def table_id(name):
    v = cfg("teable", "tables", name)
    if is_placeholder(v):
        sys.exit(f"✗ В settings.yml не заполнен teable.tables.{name}")
    return v


def all_records(tid):
    """Все записи таблицы постранично. 🔴 Teable отдаёт максимум 100 за запрос."""
    take = min(int(cfg("teable", "page_size") or 100), 100)
    out, skip = [], 0
    while True:
        recs = teable("GET", f"/table/{tid}/record?fieldKeyType=name&take={take}&skip={skip}")["records"]
        out += recs
        if len(recs) < take:
            return out
        skip += take


def units():
    return sorted(all_records(table_id("units")), key=lambda r: r["fields"].get("№") or 0)


def unit_by_number(n):
    for r in units():
        if r["fields"].get("№") == n:
            return r
    sys.exit(f"✗ Пуля №{n} не найдена")


def patch_unit(rec_id, fields):
    return teable("PATCH", f"/table/{table_id('units')}/record/{rec_id}",
                  {"record": {"fields": fields}, "fieldKeyType": "name", "typecast": True})


# ───────────────────────── check ─────────────────────────
def cmd_check(_):
    ok = True

    def line(mark, text):
        print(f"{mark} {text}")

    print("═══ Заглушки в config/settings.yml ═══")
    ph = placeholders()
    for p, v in ph:
        line("⚠️ ", f"{p} = {v}")
    if not ph:
        line("✅", "заглушек нет")

    print("\n═══ Ключи (config/secrets.yml или env) ═══")
    for sec, key, env, name in [("teable", "api_token", "TEABLE_API_TOKEN", "Teable"),
                                ("zernio", "api_key", "ZERNIO_API_KEY", "Zernio"),
                                ("heygen", "api_key", "HEYGEN_API_KEY", "HeyGen")]:
        if secret(sec, key, env):
            line("✅", f"{name}: ключ найден")
        else:
            ok = False
            line("❌", f"{name}: ключа нет → впиши {sec}.{key} в config/secrets.yml (образец secrets.example.yml) или задай {env}")

    print("\n═══ Teable ═══")
    if secret("teable", "api_token", "TEABLE_API_TOKEN") and not is_placeholder(cfg("teable", "api_url")) \
            and not is_placeholder(cfg("teable", "base_id")):
        tables = {t["id"]: t["name"] for t in teable("GET", f"/base/{cfg('teable', 'base_id')}/table")}
        line("✅", f"база доступна, таблиц: {len(tables)} ({', '.join(tables.values())})")
        for key in ("units", "adaptations", "research", "accounts"):
            tid = cfg("teable", "tables", key)
            if is_placeholder(tid):
                ok = False
                line("❌", f"teable.tables.{key} — заглушка. Таблицы в базе: " +
                     "; ".join(f"{n} = {i}" for i, n in tables.items()))
            elif tid not in tables:
                ok = False
                line("❌", f"teable.tables.{key} = {tid} — такой таблицы в базе нет")
            else:
                line("✅", f"{key} → «{tables[tid]}»")
        ok &= _check_fields()
    else:
        ok = False
        line("❌", "нет api_url / base_id / токена — Teable не проверен")

    print("\n═══ Zernio ═══")
    zkey = secret("zernio", "api_key", "ZERNIO_API_KEY")
    if zkey:
        code, body = http("GET", cfg("zernio", "rest_api_base").rstrip("/") + "/accounts", {"Authorization": "Bearer " + zkey})
        if code == 200:
            accs = body.get("accounts", body if isinstance(body, list) else [])
            found = {str(a.get("_id") or a.get("id")): f"{a.get('platform')} @{a.get('username', '')}" for a in accs}
            line("✅", f"ключ рабочий, аккаунтов в Zernio: {len(found)}")
            for plat, aid in (cfg("zernio", "accounts") or {}).items():
                if is_placeholder(aid):
                    line("⚠️ ", f"accountId {plat} — заглушка. Доступные: " + "; ".join(f"{v} = {k}" for k, v in found.items()))
                elif aid in found:
                    line("✅", f"{plat} → {found[aid]}")
                else:
                    ok = False
                    line("❌", f"{plat}: accountId {aid} не найден в Zernio")
        else:
            ok = False
            line("❌", f"Zernio ответил {code} — проверь ключ")

    print("\n═══ HeyGen ═══")
    hkey = secret("heygen", "api_key", "HEYGEN_API_KEY")
    if hkey:
        hb = cfg("heygen", "api_base").rstrip("/")
        code, body = http("GET", hb + "/v2/user/remaining_quota", {"X-Api-Key": hkey})
        if code == 200:
            line("✅", f"ключ рабочий, остаток квоты: {(body.get('data') or {}).get('remaining_quota', '?')}")
            code, body = http("GET", hb + "/v2/avatars", {"X-Api-Key": hkey}, timeout=120)
            data = body.get("data") or {}
            known = {a.get("avatar_id") for a in data.get("avatars", [])} | \
                    {p.get("talking_photo_id") for p in data.get("talking_photos", [])}
            for name, a in (cfg("heygen", "avatars") or {}).items():
                if is_placeholder(a.get("avatar_id")) or is_placeholder(a.get("voice_id")):
                    line("⚠️ ", f"аватар {name}: avatar_id / voice_id — заглушка (см. knowledge/avatar_presets.md)")
                elif code == 200 and a["avatar_id"] not in known:
                    ok = False
                    line("❌", f"аватар {name}: avatar_id не найден в аккаунте HeyGen")
                else:
                    line("✅", f"аватар {name} на месте")
        else:
            ok = False
            line("❌", f"HeyGen ответил {code} — проверь ключ")

    print("\n═══ Higgsfield ═══")
    line("ℹ️ ", "MCP проверяется в Claude, не скриптом — workflows/setup.md, шаг 4")

    print("\n═══ Исполнители (соседние скиллы) ═══")
    for key, rel in (cfg("executors") or {}).items():
        p = os.path.normpath(os.path.join(ROOT, rel))
        has = os.path.exists(os.path.join(p, "SKILL.md")) or (key == "brand" and os.path.isdir(p))
        ok &= has
        line("✅" if has else "❌", f"{key}: {rel}" + ("" if has else " — папки нет рядом с оркестратором"))

    print("\nИТОГ:", "✅ завод готов" if ok else "❌ есть что донастроить (см. ❌ выше)")
    sys.exit(0 if ok else 1)


def _check_fields():
    ok = True
    for key, required, recommended in (("units", UNIT_REQUIRED, UNIT_RECOMMENDED), ("adaptations", ADAPT_REQUIRED, [])):
        tid = cfg("teable", "tables", key)
        if is_placeholder(tid):
            continue
        fields = {f["name"]: f for f in teable("GET", f"/table/{tid}/field")}
        miss = [f for f in required if f not in fields]
        if miss:
            ok = False
            print(f"❌ {key}: нет обязательных полей: {', '.join(miss)}")
        else:
            print(f"✅ {key}: обязательные поля на месте")
        rec = [f for f in recommended if f not in fields]
        if rec:
            print(f"⚠️  {key}: рекомендуется добавить поля: {', '.join(rec)} (knowledge/teable_schema.md)")
        st = fields.get("Статус")
        if st:
            have = [c["name"] for c in (st.get("options") or {}).get("choices", [])]
            want = STATUSES + [REJECTED] if key == "units" else ADAPT_STATUS_RECOMMENDED
            lack = [s for s in want if s not in have]
            if lack:
                mark = "❌" if key == "units" else "⚠️ "
                ok &= key != "units"
                print(f"{mark} {key}.Статус: не хватает вариантов: {', '.join(lack)} (сейчас: {', '.join(have)})")
            else:
                print(f"✅ {key}.Статус: все варианты статусной модели есть")
    return ok


# ───────────────────────── сводка и чтение ─────────────────────────
def short(s, n=70):
    s = (s or "").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def cmd_summary(_):
    recs = units()
    groups = {}
    for r in recs:
        groups.setdefault(r["fields"].get("Статус") or "(без статуса)", []).append(r)
    order = STATUSES + [REJECTED] + [s for s in groups if s not in STATUSES + [REJECTED]]
    print(f"Всего пуль: {len(recs)}\n")
    for s in order:
        if s not in groups:
            continue
        hint = f"  ⚠️ старый статус → считать «{LEGACY[s]}»" if s in LEGACY else ""
        print(f"■ {s} — {len(groups[s])}{hint}")
        for r in groups[s]:
            f = r["fields"]
            print(f"   №{f.get('№')} · {short(f.get('Пуля'))}  [{', '.join(f.get('Формат') or [])}]")
        print()


def cmd_list(a):
    for r in units():
        f = r["fields"]
        if a.status and f.get("Статус") != a.status:
            continue
        print(f"№{f.get('№')}\t{f.get('Статус')}\t{short(f.get('Пуля'))}\t{', '.join(f.get('Формат') or [])}")


def cmd_show(a):
    f = unit_by_number(a.n)["fields"]
    for k, v in f.items():
        print(f"── {k} ──\n{v}\n")


def cmd_next(_):
    print(max([r["fields"].get("№") or 0 for r in units()] + [0]) + 1)


def cmd_add(a):
    fields = json.load(open(a.json, encoding="utf-8"))
    fields.setdefault("Статус", "Идея")
    if "№" not in fields:
        fields["№"] = max([r["fields"].get("№") or 0 for r in units()] + [0]) + 1
    body = teable("POST", f"/table/{table_id('units')}/record",
                  {"records": [{"fields": fields}], "fieldKeyType": "name", "typecast": True})
    print(f"✅ создана пуля №{fields['№']} ({body['records'][0]['id']}) со статусом «{fields['Статус']}»")


def cmd_set(a):
    rec = unit_by_number(a.n)
    val = open(a.file, encoding="utf-8").read() if a.file else a.value
    patch_unit(rec["id"], {a.field: val})
    print(f"✅ №{a.n}: поле «{a.field}» записано ({len(val or '')} симв.)")


def cmd_status(a):
    rec = unit_by_number(a.n)
    cur = rec["fields"].get("Статус")
    cur = LEGACY.get(cur, cur)
    new = a.status
    if new not in STATUSES + [REJECTED]:
        sys.exit(f"✗ Нет такого статуса: {new}. Допустимо: {', '.join(STATUSES + [REJECTED])}")
    if new != REJECTED and cur in STATUSES and STATUSES.index(new) > STATUSES.index(cur) + 1 and not a.force:
        sys.exit(f"✗ №{a.n}: из «{cur}» нельзя прыгнуть в «{new}» — шаги не пропускаем (--force, если человек так решил)")
    if new == "Запланировано" and not a.force:
        rep = qc_unit(rec["fields"])
        if rep["red"]:
            sys.exit(f"✗ №{a.n}: QC-гейт не пройден ({len(rep['red'])} 🔴) — в планирование нельзя")
    fields = {"Статус": new}
    if a.note:
        old = rec["fields"].get("Красные линии / проверить") or ""
        fields["Красные линии / проверить"] = (old + "\n" if old else "") + f"[{new}] {a.note}"
    patch_unit(rec["id"], fields)
    print(f"✅ №{a.n}: «{rec['fields'].get('Статус')}» → «{new}»")


def infer_status(f):
    """Статус по заполненности полей — для перевода старой базы на статусную модель."""
    fmt = " ".join(f.get("Формат") or []).lower()
    need = [c for k, c in (("аватар", "Сценарий HeyGen"), ("threads", "Threads-посты"), ("карусел", "Текст карусели")) if k in fmt]
    if need and all((f.get(c) or "").strip() for c in need):
        return "Тексты готовы"
    if (f.get("Хук A") or "").strip() and (f.get("Тезисы тела") or "").strip():
        return "Пуля"
    return "Идея"


def cmd_infer(a):
    changes = []
    for r in units():
        f = r["fields"]
        cur, guess = f.get("Статус"), infer_status(f)
        cur_n = LEGACY.get(cur, cur)
        if cur_n in STATUSES and STATUSES.index(cur_n) > STATUSES.index(guess) or cur == REJECTED:
            guess = cur_n
        if guess != cur:
            changes.append((r, cur, guess))
            print(f"№{f.get('№')}: «{cur}» → «{guess}»  {short(f.get('Пуля'), 50)}")
    if not changes:
        print("✅ все статусы уже по модели")
    elif a.apply:
        for r, _, guess in changes:
            patch_unit(r["id"], {"Статус": guess})
        print(f"✅ переведено: {len(changes)}")
    else:
        print(f"\nЭто предпросмотр ({len(changes)} изменений). Записать — с флагом --apply, после «ок» человека.")


# ───────────────────────── адаптации ─────────────────────────
def cmd_adapt(a):
    rec = unit_by_number(a.n)
    fields = {"Название": a.name or f"П-{a.n:02d} · {a.format}", "Формат": a.format,
              "Площадки": [p.strip() for p in a.platforms.split(",") if p.strip()],
              "Статус": a.status, "Язык": "RU", "Пуля": [{"id": rec["id"]}]}
    for key, path in (("Сценарий / текст", a.text_file), ("Подпись к публикации", a.caption_file)):
        if path:
            fields[key] = open(path, encoding="utf-8").read()
    if a.hook:
        fields["Хук"] = a.hook
    body = teable("POST", f"/table/{table_id('adaptations')}/record",
                  {"records": [{"fields": fields}], "fieldKeyType": "name", "typecast": True})
    print(f"✅ адаптация «{fields['Название']}» создана: {body['records'][0]['id']}")


def cmd_adapt_list(a):
    rec = unit_by_number(a.n)
    ids = {x["id"] if isinstance(x, dict) else x for x in rec["fields"].get("Адаптации") or []}
    for r in all_records(table_id("adaptations")):
        if r["id"] in ids:
            f = r["fields"]
            print(f"{r['id']}\t{f.get('Название')}\t{f.get('Статус')}\t{', '.join(f.get('Площадки') or [])}\t{f.get('Дата публикации') or ''}")


def cmd_adapt_set(a):
    val = open(a.file, encoding="utf-8").read() if a.file else a.value
    if a.field in ("Площадки",):
        val = [p.strip() for p in val.split(",")]
    teable("PATCH", f"/table/{table_id('adaptations')}/record/{a.rec}",
           {"record": {"fields": {a.field: val}}, "fieldKeyType": "name", "typecast": True})
    print(f"✅ {a.rec}: «{a.field}» записано")


# ───────────────────────── QC-гейт ─────────────────────────
# Источник правды для правил — этот блок. Человеческое описание — knowledge/qc_gate.md.
EXCHANGES = (r"binance|bybit|okx|okex|bitget|mexc|kucoin|gate\.?io|htx|huobi|bingx|whitebit|kraken|coinbase|"
             r"bitfinex|bitmex|deribit|weex|lbank|phemex|bitstamp|kuna|"
             r"бинанс\w*|байбит\w*|окх|битгет\w*|мекс\w*|кукоин\w*|хуоби|вайтбит\w*|кракен\w*|коинбейс\w*|"
             r"pocket\s*option|quotex|olymp\s*trade|iq\s*option|binomo|exness|alpari|альпари|"
             r"cryptology|криптолоджи\w*|vataga|ватага|peterson|петерсон\w*")
RED = [
    ("shadowban", r"\bзаработ\w*|\bзароб(і|и)т\w*|\bзаробля\w*|\bдоход(а|у|ом|ов|ам|ами|ах|е|ы|н\w*)?\b|\bдохід\w*|\bбыстр\w*\s+деньг\w*|\bшвидк\w*\s+грош\w*",
     "Слова теневого бана: «заработок / доход / быстрые деньги» — переформулировать («результат», «навык», «профессия»)"),
    ("exchange", r"\b(" + EXCHANGES + r")\b", "Название биржи / брокера / конкурента — убрать («биржа», «платформа»)"),
    ("link", r"https?://|www\.|\bt\.me/|\b[\w-]+\.(com|io|net|org|ua|ru|me)\b", "Внешняя ссылка — убрать"),
    ("rub", r"₽|\bруб(\.|л\w*)?\b|\brub\b", "Рубли запрещены — только $ / USDT"),
    ("promise", r"\bбез\s+риск\w*|\bгарантированн\w*|\b100\s*%\s*(результат|прибыл|профит)", "Обещание без риска / гарантии"),
]
YELLOW = [
    ("amount", r"(\$\s?\d|\d[\d\s.,]*\s?(\$|usdt|usd|долл\w*|грн|€|евро|k\b|к\b|тыс\w*))|"
               r"\b(сто|двест\w*|тристa|пятьсот|тысяч\w*|миллион\w*)\s+(долл\w*|usdt)",
     "Сумма — убедиться, что это не обещание дохода и не «заработал за N дней»"),
    ("guarantee", r"\bгарант\w*", "Слово «гарант…» — допустимо только в разоблачении («обещают гарантию — беги»)"),
    ("glamour", r"\bламбо\w*|\blambo\w*|\bламборгин\w*|\bроскош\w*|\bяхт\w*|\bсуперкар\w*", "Глянец — допустим только как высмеивание"),
    ("war", r"\bвойн\w*|\bвійн\w*|\bфронт\w*|\bзсу\b|\bмобилиз\w*|\bмобіліз\w*", "Военная тема — бережно, без эксплуатации травмы"),
    ("big_lever", r"\bx\s?\d{2,3}\b|\bплеч\w*\s+\d", "Большое плечо — только как пример ошибки, с объяснением риска"),
]
SERVICE_PREFIXES = ("символов:", "каркас", "проверить/подставить", "субтитры:", "визуал:")
CTA_RE = r"подпиш\w*[^.\n]{0,40}(не\s+потерят\w*|не\s+загубит\w*|не\s+втратит\w*)|підпиш\w*[^.\n]{0,40}не\s+втратит\w*"
DISCLAIMER_RE = r"не\s+финансов\w*\s+рекомендац\w*|не\s+фінансов\w*\s+(порад\w*|рекомендац\w*)"


def _blocks(text, start, end):
    return re.findall(re.escape(start) + r"(.*?)" + re.escape(end), text, flags=re.S)


def qc_text(text, kind):
    """kind: heygen | threads | carousel | caption | plain. Возвращает {'red': [...], 'yellow': [...], 'ok': [...]}"""
    rep = {"red": [], "yellow": [], "ok": []}
    low = (text or "").lower()
    if not low.strip():
        rep["red"].append(f"[{kind}] ячейка пустая")
        return rep
    # Служебные строки исполнителей (инструкция, разметка, «Зачем:») не проверяем на слова — только контент.
    # Служебные строки с цитатами правил («не использовать слова …») тоже не считаем нарушением.
    body = re.sub(r"═══ инструкция ═══.*?═{5,}", "", low, flags=re.S)
    content = "\n".join(l for l in body.splitlines()
                        if not l.strip().startswith(SERVICE_PREFIXES) and "не использовать" not in l)
    for code, rx, msg in RED:
        hits = sorted({m.group(0).strip() for m in re.finditer(rx, content, flags=re.I)})
        (rep["red"].append(f"[{kind}] {msg}: {', '.join(hits)}") if hits else None)
    for code, rx, msg in YELLOW:
        hits = sorted({m.group(0).strip() for m in re.finditer(rx, content, flags=re.I)})
        (rep["yellow"].append(f"[{kind}] {msg}: {', '.join(hits[:6])}") if hits else None)

    if kind == "heygen":
        spoken = _blocks(body, "▼ текст для озвучки ▼", "▲ конец текста ▲")
        if not spoken:
            rep["red"].append("[heygen] нет блока «▼ ТЕКСТ ДЛЯ ОЗВУЧКИ ▼ … ▲ КОНЕЦ ТЕКСТА ▲»")
        for s in spoken:
            if not re.search(CTA_RE, s):
                rep["red"].append("[heygen] в озвучке нет призыва «Подпишись, чтобы не потерять»")
            if re.search(r"\d", s):
                rep["yellow"].append("[heygen] цифры в озвучке — HeyGen читает их криво, лучше словами")
            if re.search(r"[—–]", s):
                rep["yellow"].append("[heygen] длинные тире в озвучке — заменить точкой или запятой")
            if re.search(r"https?://|[\U0001F300-\U0001FAFF]", s):
                rep["red"].append("[heygen] ссылка или эмодзи в озвучке")
        caption = re.search(r"подпись к публикации:(.*?)(?=\n(субтитры|каркас|проверить/подставить)|\Z)", body, flags=re.S)
        if caption and not re.search(DISCLAIMER_RE, caption.group(1)):
            rep["red"].append("[heygen] в подписи к публикации нет «Не финансовая рекомендация»")
        if caption and not re.search(CTA_RE, caption.group(1)):
            rep["red"].append("[heygen] в подписи к публикации нет «Подпишись, чтобы не потерять»")
    elif kind == "threads":
        posts = re.findall(r"▼ пост (\d+)[^\n]*\n(.*?)\n▲ конец поста \1 ▲", body, flags=re.S)
        if not posts:
            rep["red"].append("[threads] нет блоков «▼ ПОСТ k ▼ … ▲ КОНЕЦ ПОСТА k ▲»")
        for k, body in posts:
            n = len(body.strip())
            if n > 500:
                rep["red"].append(f"[threads] пост {k}: {n} символов — лимит Threads 500")
    elif kind in ("carousel", "caption"):
        if kind == "carousel":
            slides = re.findall(r"▼ слайд (\d+) из (\d+)", body)
            if not slides:
                rep["red"].append("[carousel] нет блоков «▼ СЛАЙД k из N ▼»")
            elif int(slides[-1][1]) > 10:
                rep["red"].append(f"[carousel] {slides[-1][1]} слайдов — максимум 10")
            m = re.search(r"═══ подпись к посту ═══(.*?)(═══ конец ═══|$)", body, flags=re.S)
            cap = m.group(1) if m else ""
            if not cap.strip():
                rep["red"].append("[carousel] нет блока «═══ ПОДПИСЬ К ПОСТУ ═══»")
        else:
            cap = low
        if cap and not re.search(CTA_RE, cap):
            rep["red"].append(f"[{kind}] в подписи нет «Подпишись, чтобы не потерять»")
        if cap and not re.search(DISCLAIMER_RE, cap):
            rep["red"].append(f"[{kind}] в подписи нет «Не финансовая рекомендация»")
        if re.search(r"(^|\s)#[\wа-яё]+", cap or ""):
            rep["yellow"].append(f"[{kind}] хэштеги в подписи — по стандарту не используем")
    if not rep["red"]:
        rep["ok"].append(f"[{kind}] красные линии не нарушены")
    return rep


def qc_unit(f):
    """QC всех текстовых ячеек пули, которые нужны по её полю «Формат»."""
    fmt = " ".join(f.get("Формат") or []).lower()
    plan = []
    if "heygen" in fmt or "аватар" in fmt:
        plan.append(("heygen", f.get("Сценарий HeyGen")))
    if "threads" in fmt:
        plan.append(("threads", f.get("Threads-посты")))
    if "карусел" in fmt:
        plan.append(("carousel", f.get("Текст карусели")))
    rep = {"red": [], "yellow": [], "ok": []}
    if not plan:
        rep["red"].append("в поле «Формат» нет ни одного формата завода (AI-аватар / Threads / Карусель)")
    for kind, text in plan:
        r = qc_text(text, kind)
        for k in rep:
            rep[k] += r[k]
    return rep


def cmd_qc(a):
    if a.unit is not None:
        rep = qc_unit(unit_by_number(a.unit)["fields"])
        title = f"QC пули №{a.unit}"
    else:
        rep = qc_text(open(a.file, encoding="utf-8").read(), a.kind)
        title = f"QC файла {os.path.basename(a.file)} ({a.kind})"
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        verdict = "🔴 НЕ ПРОЙДЕН — в постинг нельзя" if rep["red"] else ("🟡 ПРОЙДЕН с замечаниями — посмотреть глазами" if rep["yellow"] else "🟢 ПРОЙДЕН")
        print(f"{title}: {verdict}")
        for k, mark in (("red", "🔴"), ("yellow", "🟡"), ("ok", "🟢")):
            for x in rep[k]:
                print(f"  {mark} {x}")
    sys.exit(1 if rep["red"] else 0)


def main():
    p = argparse.ArgumentParser(description="ward-content-factory: движок оркестратора")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    sub.add_parser("summary").set_defaults(fn=cmd_summary)
    s = sub.add_parser("list"); s.add_argument("--status"); s.set_defaults(fn=cmd_list)
    s = sub.add_parser("show"); s.add_argument("n", type=int); s.set_defaults(fn=cmd_show)
    sub.add_parser("next-number").set_defaults(fn=cmd_next)
    s = sub.add_parser("infer"); s.add_argument("--apply", action="store_true"); s.set_defaults(fn=cmd_infer)
    s = sub.add_parser("add"); s.add_argument("--json", required=True); s.set_defaults(fn=cmd_add)
    s = sub.add_parser("set"); s.add_argument("n", type=int); s.add_argument("--field", required=True)
    g = s.add_mutually_exclusive_group(required=True); g.add_argument("--value"); g.add_argument("--file")
    s.set_defaults(fn=cmd_set)
    s = sub.add_parser("status"); s.add_argument("n", type=int); s.add_argument("status")
    s.add_argument("--note"); s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("adapt"); s.add_argument("n", type=int); s.add_argument("--format", required=True)
    s.add_argument("--platforms", required=True); s.add_argument("--name"); s.add_argument("--hook")
    s.add_argument("--text-file"); s.add_argument("--caption-file"); s.add_argument("--status", default="Черновик")
    s.set_defaults(fn=cmd_adapt)
    s = sub.add_parser("adapt-list"); s.add_argument("n", type=int); s.set_defaults(fn=cmd_adapt_list)
    s = sub.add_parser("adapt-set"); s.add_argument("rec"); s.add_argument("--field", required=True)
    g = s.add_mutually_exclusive_group(required=True); g.add_argument("--value"); g.add_argument("--file")
    s.set_defaults(fn=cmd_adapt_set)
    s = sub.add_parser("qc"); s.add_argument("--unit", type=int); s.add_argument("--file")
    s.add_argument("--kind", choices=["heygen", "threads", "carousel", "caption", "plain"], default="plain")
    s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_qc)
    a = p.parse_args()
    if a.cmd == "qc" and a.unit is None and not a.file:
        p.error("qc: нужен --unit N или --file PATH")
    a.fn(a)


if __name__ == "__main__":
    main()
