#!/usr/bin/env python3
"""
fetch_sources.py — движок парсинга parsing-ward. НЕ писать заново каждый раз.

Читает «Источники» (Активен=true) из Teable, тянет свежие позиции (RSS/Сайт),
фильтрует по окну свежести, дедупит против уже известных URL, печатает JSON в stdout
и сохраняет в workspace/fetch_YYYY-MM-DD.json.

Использование:
  python fetch_sources.py                 # все активные источники
  python fetch_sources.py --hours 72      # переопределить окно свежести
  python fetch_sources.py --no-dedup      # не дедупить (для теста)

Дальше: модель читает JSON, оценивает по knowledge/scoring_rubric.md, формирует rows.json,
и зовёт teable.py write rows.json.

ВЕБ-источники (Тип=Сайт): простая HTML-страница новостей/объявлений парсится тут
универсально (ссылки вида /news/, /announcement/, /press/ и т.п. с текстом заголовка).
JS-рендеренные сайты (список fetch.js_sites в config) скрипт пропускает — модель
добирает их через WebSearch. Тип Telegram скрипт не парсит (хрупко) — только вручную.
"""
import sys, os, json, re, html, time, datetime, urllib.request, urllib.error
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from teable import CFG, get_records, all_known_urls, T, require_config  # переиспользуем конфиг и дедуп

UA = CFG["fetch"]["user_agent"]
HOURS = int(CFG["fetch"]["freshness_hours"])
MAXP = int(CFG["fetch"]["max_per_source"])
A = "{http://www.w3.org/2005/Atom}"

def clean(t):
    t = re.sub(r"<[^>]+>", "", t or "")
    return html.unescape(re.sub(r"\s+", " ", t)).strip()

def fetch(url, timeout=25, retries=2):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    for attempt in range(retries + 1):
        try:
            return urllib.request.urlopen(req, timeout=timeout).read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(2 + attempt * 3)   # backoff на троттлинг
                continue
            raise

def parse_date(s):
    if not s:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            d = datetime.datetime.strptime(s.strip(), fmt)
            return d.replace(tzinfo=None)
        except ValueError:
            continue
    return None

def fresh(dt, cutoff):
    return dt is None or dt >= cutoff   # без даты — пропускаем (модель решит)

def first(it, *tags):
    for t in tags:
        e = it.find(t)
        if e is not None and (e.text or e.get("href")):
            return e
    return None

def fetch_rss(url, cutoff):
    out = []
    root = ET.fromstring(fetch(url))
    items = root.findall(".//item") or root.findall(f".//{A}entry")
    for it in items[:MAXP * 2]:
        te = first(it, "title", f"{A}title")
        le = first(it, "link", f"{A}link")
        de = first(it, "pubDate", "published", f"{A}published", "updated", f"{A}updated")
        se = first(it, "description", "summary", f"{A}summary")
        link = (le.text or le.get("href")) if le is not None else ""
        dt = parse_date(de.text) if de is not None else None
        if not fresh(dt, cutoff):
            continue
        out.append({"title": clean(te.text) if te is not None else "",
                    "url": link.strip(),
                    "date": dt.strftime("%Y-%m-%d") if dt else "",
                    "summary": clean(se.text)[:280] if se is not None else ""})
        if len(out) >= MAXP:
            break
    return out

# Подсказки в пути ссылки, по которым на HTML-странице узнаём новость/объявление.
NEWS_PATH_HINTS = ("/news/", "/novyny/", "/novosti/", "/announcement", "/press", "/article",
                   "/blog/", "/post/", "/media/", "/law/", "/statement")

def _js_site(url):
    return any(d in url for d in (CFG["fetch"].get("js_sites") or []))

def fetch_site(name, url, cutoff):
    """Универсальный HTML-парс страницы новостей. Возвращает [] для JS-сайтов (fetch.js_sites)
    — их модель добирает через WebSearch. Дату со страницы не угадываем: date="" → модель решает
    по самому материалу (правило свежести ≤7 дней всё равно проверяет teable.py write)."""
    if _js_site(url):
        return []
    out, seen_local = [], set()
    htmltext = fetch(url).decode("utf-8", "ignore")
    m = re.match(r"(https?://[^/]+)", url)
    origin = m.group(1) if m else ""
    for a in re.finditer(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', htmltext, re.S):
        href, text = a.group(1).strip(), clean(a.group(2))
        if len(text) < 20 or not any(h in href.lower() for h in NEWS_PATH_HINTS):
            continue
        if href.startswith("/"):
            href = origin + href
        if not href.startswith("http") or href in seen_local:
            continue
        seen_local.add(href)
        out.append({"title": text[:200], "url": href, "date": "", "summary": ""})
        if len(out) >= MAXP:
            break
    return out

def main():
    require_config()
    args = sys.argv[1:]
    hours = HOURS
    if "--hours" in args:
        hours = int(args[args.index("--hours") + 1])
    dedup = "--no-dedup" not in args
    cutoff = datetime.datetime.now() - datetime.timedelta(hours=hours)
    seen = all_known_urls() if dedup else set()

    sources = [r["fields"] for r in get_records(T["sources"])
               if r["fields"].get("Активен")]
    sources.sort(key=lambda f: f.get("Кластер", 99))
    result, errors = [], []
    for s in sources:
        name, typ, addr = s.get("Название", ""), s.get("Тип", ""), s.get("Адрес", "")
        cl = s.get("Кластер", 99)
        try:
            if typ == "RSS":
                items = fetch_rss(addr, cutoff)
            elif typ == "Сайт":
                items = fetch_site(name, addr, cutoff)
            else:
                items = []   # Telegram / Twitter и пр. — скрипт не парсит, модель добирает вручную
            items = [it for it in items if it["url"] and it["url"] not in seen]
            for it in items:
                seen.add(it["url"])
            if items:
                result.append({"source": name, "cluster": cl, "type": typ, "items": items})
        except Exception as e:
            errors.append({"source": name, "error": f"{type(e).__name__}: {e}"})
        time.sleep(0.7)   # вежливая пауза между источниками (меньше 429)

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    out = {"date": today, "hours": hours, "sources_ok": len(result),
           "items_total": sum(len(r["items"]) for r in result),
           "errors": errors, "groups": result}
    os.makedirs(os.path.join(ROOT, "workspace"), exist_ok=True)
    path = os.path.join(ROOT, "workspace", f"fetch_{today}.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"\n# сохранено: {path}", file=sys.stderr)

if __name__ == "__main__":
    main()
