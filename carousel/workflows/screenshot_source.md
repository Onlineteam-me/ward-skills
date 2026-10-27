# Workflow — Скриншот источника для layout `source` (формат C / B2)

> Когда в карусели нужен слайд-пруф со скрином статьи/репозитория/поста. НЕ писать одноразовый screenshot-скрипт каждый раз — есть готовый `scripts/screenshot_url.py`.

---

## 🔴 ГЛАВНОЕ ПРАВИЛО — реальный скрин, не отрисованная карточка

**Для слайда `source` использовать ТОЛЬКО настоящий скриншот источника, полученный через `scripts/screenshot_url.py`. НИКОГДА не рисовать HTML-«карточку в стиле сайта» и не выдавать её за скрин.**

Причина: отрисованные карточки читаются как фейк, пропадает эффект «пруф что источник реальный» — ради которого слайд-источник и существует. Если сам скрипт не смог сделать скрин (сайт заблокирован, требует логин) — сказать пользователю и спросить, что делать (реальный скрин вручную / оставить без слайда-источника / другой формат), а НЕ рисовать подделку.

## 🔴 ПРАВИЛО 2026-07-10 — скрин ДОЛЖЕН показывать хедер источника

**После получения скрина ОБЯЗАТЕЛЬНО открыть его через `Read` и проверить визуально по 3 критериям:**

1. Виден **логотип издания** сверху (Latent Space, EL PAIS, GitHub OG-card, HN).
2. Виден **заголовок статьи / название репо**.
3. Виден **автор или подзаголовок**.

Если хотя бы 2 из 3 отсутствуют → скрин снят с середины/футера, это **брак**. Переснимай.

**Признак бага «скрин из середины»:** на изображении чистый текст статьи без хедера, без логотипа, без заголовка. Ты фактически видишь абзац из body, будто читатель уже проскроллил статью.

**Причина бага:** до 2026-07-10 `screenshot_url.py` после kill_overlays мог оставить страницу с уехавшим вниз скроллом (SPA-фреймворки типа Substack при консент-баннерах делают `scrollIntoView` на body). Viewport 1280×900 забирал середину.

**Фикс в скрипте:** перед `page.screenshot()` теперь всегда `window.scrollTo(0, 0)` + wait. Если скрипт всё же вернул брак (старая версия, редкий кейс) — переснимай inline Playwright с явным scroll-to-top:

```python
await page.goto(url, wait_until="domcontentloaded")
await page.wait_for_timeout(4000)
await page.evaluate("document.querySelectorAll('[class*=modal],[class*=paywall],[role=dialog]').forEach(el=>el.remove()); document.body.style.overflow='auto'; window.scrollTo(0,0);")
await page.wait_for_timeout(1500)
await page.screenshot(path=out, full_page=False)
```

### Специальные обработчики (уже встроены в скрипт)

- **GitHub** (`github.com/*/*`) → скрипт автоматически подтягивает **официальную OG-card репозитория** через `opengraph-image` API. Это настоящее изображение GitHub'а: имя репо, описание, счётчики (stars, forks, contributors, issues), аватар автора. Эталон — `examples/source_screenshots/github_og_card_reference.png`.
- **Twitter/X** — через oEmbed API (аналогично)
- **Reddit** — старый интерфейс `old.reddit.com` даёт чистый скрин без модалок

Если появится новый источник, где OG-card даёт лучший результат чем скриншот страницы — добавить в `special-source` handlers в `screenshot_url.py`.

---

## 🔴 Специфика по типу издания — куда обычно смотреть

**Правило (2026-07-10):** GitHub — исключение, там OG-card = готовая чистая картинка. Всё остальное (обычные сайты, СМИ, соцсети) снимается через playwright, и **у каждого типа издания свои типовые ломающие элементы**. Ниже — карта того, что реально мешает и что делать.

### 📰 Substack (Latent Space, Every, One Useful Thing, Not Boring)
- **Проблема:** subscribe-модалка выпадает через 3-5 секунд после загрузки, ждёт email. `body { overflow: hidden }` после этого.
- **Что делает скрипт:** блокирует `.subscribe-widget-form`, `.tp-modal`, `.tp-container`, `[class*=freeSubscribePrompt]`.
- **Признак правильного скрина:** сверху видно **лого издания** («Latent Space» логотип) + **заголовок статьи**.
- **Если брак (пусто/футер):** переснять inline Playwright с `wait_for_timeout(5000)` — Substack медленно гидрируется.
- **Фолбэк:** wayback (`http://archive.org/wayback/available?url=...`) — Substack хорошо архивируется.

### 🌐 Крупные СМИ (El País, Telegraph, Reuters, NYT, WSJ, FT)
- **Проблема:** paywall или register-wall поверх контента, cookie-banner OneTrust снизу, иногда newsletter-модалка сбоку.
- **Что делает скрипт:** блокирует `.meter-wall`, `.newsletter-signup`, `.register-wall`, `#hp-app-messaging-toolkit` (WSJ), OneTrust на сетевом уровне.
- **Признак правильного скрина:** сверху видно **лого издания** (EL PAIS, THE TELEGRAPH) + **заголовок статьи** + **автор/дата**.
- **Если полный paywall:** WebFetch → сохранить текст. Скрин делать через wayback снапшот или через HN-обсуждение (`news.ycombinator.com/item?id=<id>`), где статья цитируется.
- **El País специфика:** статьи английской версии часто отдаются нормально при UA `Mozilla/5.0`. Испанская версия жёстче.

### 👥 Reddit (r/*/comments/*)
- **Проблема:** «Continue to Reddit» cookie-баннер, «Welcome to Reddit» плашка, sign-in wall сбоку.
- **Что делает скрипт:** блокирует `.infobar`, `[class*=CookiesInformation]`, snoo action bar. Использует `old.reddit.com` (старый интерфейс — гораздо чище).
- **Признак правильного скрина:** сверху видно **лого Reddit + subreddit** + **заголовок поста** + **автор + счётчик upvotes**.
- **Если пост заблокирован:** URL переписать на `https://old.reddit.com/r/<sub>/comments/<id>/` — иногда прямой ссылка новой версии редиректит на login. Плюс `user-agent: Chrome` через inline Playwright.
- **Фолбэк:** OG-image Reddit-поста через `curl https://embed.reddit.com/media?url=<post_url>`. Или скрин r/<subreddit> листинга, если пост найдётся в первых 5-10.

### 🐦 Twitter/X
- **Проблема:** полный login wall после 3 секунд для гостей. Виден только tweet + автор, ниже — «Sign in to see more».
- **Что делает скрипт:** блокирует `[data-testid=sheetDialog]`, login-form.
- **Признак правильного скрина:** видно **@username + аватар** + **текст твита** + **дата/лайки**.
- **Фолбэк:** oEmbed API (`https://publish.twitter.com/oembed?url=<tweet_url>`) — отдаёт HTML embed с текстом. Или nitter-mirror (nitter.net/... — иногда доступен).

### 💼 LinkedIn
- **Проблема:** полный login wall, обойти нельзя.
- **Что делает скрипт:** пытается убрать `.artdeco-modal-overlay`, но контент всё равно закрыт.
- **Стратегия:** НЕ использовать LinkedIn как источник. Найти оригинальный пост в другом месте (профильный блог автора, кросс-пост в Twitter/HN). Если пост есть только на LinkedIn — процитировать текст без скрина и в caption слайда написать «LinkedIn пост автора» без изображения.

### 🎥 YouTube
- **Проблема:** видеоплеер, куча оверлеев подписки.
- **Стратегия:** НЕ снимать сам YouTube. Использовать `https://i.ytimg.com/vi/<video_id>/maxresdefault.jpg` — HD-обложка видео. Это официальный превью, чистый и настоящий пруф.

### 📱 Telegram (t.me/*)
- **Проблема:** web-версия работает, но пост может отдаваться в minimal-виде.
- **Стратегия:** URL с добавкой `?embed=1&mode=tme` даёт чистый embed без «Open in Telegram» плашки.

---

### Как выбирать fallback (если скрин источника не получился)

1. **Сначала** — inline Playwright с явным `wait 5000ms + scrollTo(0,0) + kill JS`.
2. **Затем** — wayback снапшот (`http://archive.org/wayback/available?url=...`).
3. **Затем** — HN обсуждение статьи (`hn.algolia.com/api/v1/search?query=...&tags=story`).
4. **Затем** — OG-image через мета-теги статьи (curl → grep `og:image`).
5. **Последнее** — скрин листинга (r/<sub>, /education/, tag-page) где пост виден в контексте.

Если ни один пункт не сработал — сказать пользователю и спросить, что делать. НЕ рисовать HTML-карточку (правило #15).

---

## Когда нужен

- Слайд `layout: "source"` в `slides.json`
- Обложка B2 (скриншот-источник) для формата B
- Слайд-пруф «вот реальный источник» в ньюсджекинге (формат C)

## Шаг 1 — Сделать чистый скриншот

### 🔴 Всегда с `--validate` (обязательно)

```bash
"<venv>/bin/python" "<skill>/scripts/screenshot_url.py" \
  "https://www.example.com/article" \
  "<готовые>/<карусель>/черновики/_assets/source_NN.png" \
  --validate
```

Флаг `--validate` включает **автоматическую проверку + retry**:
1. После скриншота скрипт анализирует страницу на остаточные оверлеи
2. Если находит проблемы — ретраит с эскалацией стратегий (до 3 попыток)
3. Exit code `0` = чисто, `2` = warning (оверлей не удалось убить)

### Batch-режим (10+ каруселей)

Добавить `--json-report` для сводного отчёта:

```bash
REPORT="<готовые>/screenshot_report.json"

"<venv>/bin/python" "<skill>/scripts/screenshot_url.py" \
  "https://example.com/article1" \
  "<готовые>/carousel_01/черновики/_assets/source_02.png" \
  --validate --json-report "$REPORT"

"<venv>/bin/python" "<skill>/scripts/screenshot_url.py" \
  "https://example.com/article2" \
  "<готовые>/carousel_02/черновики/_assets/source_02.png" \
  --validate --json-report "$REPORT"

# В конце — проверить отчёт:
python3 -c "
import json
report = json.load(open('$REPORT'))
warnings = [r for r in report if r['status'] == 'warning']
if warnings:
    print(f'⚠ {len(warnings)} скриншот(ов) с проблемами:')
    for w in warnings:
        print(f'  {w[\"url\"]} → {w[\"issues\"]}')
else:
    print(f'✓ все {len(report)} скриншотов чистые')
"
```

### Параметры

- `<venv>` — `config/settings.yml → env.python_with_playwright`
- Размер по умолчанию: 1280×900, headless Chromium, видимая верхняя часть
- Опц. `--width 1440 --height 1024` если нужно крупнее
- `--max-retries N` — макс попыток (default: 3)

## 🔴 Что делает скрипт (важно — НЕ повторять руками)

### Стратегия очистки (3 попытки с эскалацией)

**Попытка 1 — click accept + kill JS:**
1. Ждёт 2 сек загрузки
2. Ищет кнопку Accept/Agree/Allow/Принять и **кликает** (не только удаляет баннер)
3. JS-чистка: удаление попапов по селекторам + fixed/sticky оверлеев
4. Второй проход JS (ленивые попапы)

**Попытка 2 — aggressive kill (если попытка 1 не помогла):**
1. Ждёт 3 сек (для ленивых попапов)
2. Повторно пробует click accept
3. Убивает ВСЁ fixed/sticky с z-index > 10 (без проверки ширины)

**Попытка 3 — reload + nuke (крайняя мера):**
1. Перезагружает страницу БЕЗ блокировки consent-скриптов (некоторые сайты ломаются без них)
2. Ждёт 3 сек → кликает Accept → чистит всё
3. Удаляет любой `[role=dialog]`, `[aria-modal=true]`

### Блокировка на сетевом уровне

OneTrust, Cookiebot, TrustArc, Didomi, Quantcast, Usercentrics, Sourcepoint, iubenda, Civic, Termly, Securiti, Osano, Complianz, Moove — попапы этих провайдеров не загружаются вообще.

### Валидация (при `--validate`)

После каждой попытки проверяет:
- Остались ли `fixed/sticky` элементы шириной ≥50% экрана
- Есть ли полупрозрачные backdrop-оверлеи (rgba с z-index > 999)
- `body { overflow: hidden }` всё ещё стоит?
- Есть ли `[role=dialog]` / `[role=alertdialog]`?
- Есть ли подозрительные fixed-элементы в центре экрана

## Шаг 2 — Вставить в JSON

```json
{ "n": 2, "layout": "source", "slug": "source",
  "kicker": "ИСТОЧНИК · CNBC",
  "hero": ["AI начал собирать AI", {"t": "— окно для эксперта закрывается","accent":true}],
  "screenshot": "черновики/_assets/source_02.png",
  "url": "cnbc.com/2026/06/02/...",
  "caption": "Что это значит для эксперта — разбираем" }
```

Движок (`render.py` → layout `source`) вставит реальный скриншот в браузер-мокап.

## Чек-лист (автоматизирован при `--validate`)

- [x] На скрине **виден заголовок/контент** статьи (а не куки/подписка) → автопроверка оверлеев
- [x] Нет полупрозрачных оверлеев → автопроверка backdrop
- [ ] Текст читаем (не слишком много пустого пространства сверху) → визуальная проверка (при `warning`)
- [x] `body { overflow: hidden }` снят → автопроверка

**Если скрипт вернул `warning`** (exit code 2):
1. Открой скриншот вручную — возможно, сайт требует логин/подписку (это не cookie-баннер)
2. Если это новый consent-провайдер → добавь его домен в `BLOCK_HOSTS` в `screenshot_url.py`
3. Если это новый тип попапа → добавь селектор в `KILL_SELECTORS`

## Связано
- `scripts/screenshot_url.py` — сам скрипт (с авто-валидацией)
- `scripts/render.py` → layout `source` — куда вставляется
- `knowledge/format_C_recipe.md` — ньюсджекинг-рецепт
- `knowledge/visual_dna_format_B.md` — обложка B2
