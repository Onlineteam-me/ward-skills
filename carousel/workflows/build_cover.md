# Workflow — Сборка cover-слайда

Формат B имеет **два вида обложки**. Выбор по источнику (см. `workflows/onboarding.md`):

- **B1 — Higgsfield-визуал** (тема/идея → сгенерированный объект) → шаги 1-4 ниже.
- **B2 — Скриншот-источник** (GitHub-репо / статья / сайт → реальный скрин) → раздел «Ветка B2» в конце.

Общий принцип обоих: визуал рисует НЕ текст, кириллический текст накладываем HTML/CSS через Playwright (см. `knowledge/known_bugs.md`, Баг 2).

---

## Ветка B1 — Higgsfield-визуал

---

## Зачем разделять Higgsfield и текст

См. `knowledge/known_bugs.md` (Баг 2): nano_banana_2 «плывёт» с кириллицей между слайдами. Решение — Higgsfield рисует ТОЛЬКО визуал (без текста), а текст накладываем HTML/CSS через Playwright.

---

## Шаг 1: Higgsfield — генерация чистого визуала

Преамбула: `prompts/higgsfield_3d_object.md` (без текста, без логотипов).

```
generate_image(
  model="nano_banana_2",
  prompt="<преамбула 3d_object> + <ТЗ объекта> + NO TEXT inside",
  aspect_ratio="4:5",
  resolution="1k"
)
```

Лимиты итераций → `workflows/safe_higgsfield_iteration.md` (макс 3 ретрая).

## Шаг 2: Скачать PNG

```bash
curl -o "/tmp/cover_bg.png" "{image_url}"
sips -g pixelWidth -g pixelHeight "/tmp/cover_bg.png"
# если > 2000 → sips -Z 2000 "/tmp/cover_bg.png"
```

## Шаг 3: HTML-overlay через Playwright

Создай HTML где:
- background-image: `data:image/png;base64,...` (inline base64 для надёжности через `file://`)
- Поверх — текстовые слои (хук, подзаголовок, ник `{{НИК_АККАУНТА}}`, счётчик)
- Шрифты: Inter (см. `knowledge/visual_dna_format_B.md`)

Рендер:
```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
    page.goto(f"file://{html_path}")
    page.wait_for_timeout(500)
    page.screenshot(path=output_png, omit_background=False)
```

## Шаг 4: Self-check

Прочитай готовый PNG (1080×1350, в пределах лимита). Покажи пользователю.

---

## Ветка B2 — Скриншот-источник

Когда обложка/слайд = реальный скрин репозитория, статьи, поста или сайта (пруф «вот источник»). Без Higgsfield.

Готовый вид — как макет `source` в `scripts/render.py` (скрин в тёмной карточке-браузере + штамп «ИСТОЧНИК»).

### Шаг 1: Подготовить скриншот
- Скрин даёт пользователь, либо делаем через WebFetch/браузер по URL.
- `sips -g pixelWidth -g pixelHeight screenshot.png`; если сторона > 2000 → `sips -Z 2000`.

### Шаг 2: Решить раскладку
- **Скрин в карточке** (как референс): тёмная карточка `#0A0A0A` с border-radius, внутри скрин; вокруг — крем-фон с сеткой, kicker, штамп «ИСТОЧНИК» (оранжевый), хук снизу. Скрин читаемый, не на весь кадр.
- **Скрин фоном на весь кадр**: тогда обязателен scrim + светлый текст (как видео-оверлей), иначе текст не читается.

### Шаг 3: HTML-overlay через Playwright
- Скрин — inline base64 (`data:image/png;base64,...`) внутри карточки или как `background-image`.
- Поверх: kicker, хук, ник `{{НИК_АККАУНТА}}`, счётчик, опц. штамп «ИСТОЧНИК».
- Шрифты и цвета — `knowledge/visual_dna_format_B.md`. Техника текста поверх изображения — `workflows/video_backgrounds.md`.
- Рендер — как в шаге 3 ветки B1 (Playwright, 1080×1350).

### Шаг 4: Self-check
Прочитать готовый PNG, проверить читаемость скрина и текста, показать пользователю.

---

## Связано

- `prompts/higgsfield_3d_object.md` — преамбула для bg (B1)
- `knowledge/visual_dna_format_B.md` — цвета и типографика overlay, виды обложки B1/B2
- `workflows/video_backgrounds.md` — техника текста поверх изображения/видео (B2)
- `knowledge/instagram_ui.md` — запретные зоны
