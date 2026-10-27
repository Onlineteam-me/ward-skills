# Workflow — Рендер формата A (Бренд-личность)

См. также: `knowledge/visual_dna_format_A.md`, `templates/slide_format_A.html`.

---

## Предусловия

- Пройден `workflows/onboarding.md` + `workflows/plan_and_approve.md`
- Апрув от пользователя получен
- Выбраны имена фото для визуальных слотов по таблице из `knowledge/visual_dna_format_A.md` (varied `outfit_set`)

---

## Шаг 1: Подбор фото — читать готовый индекс

**Фото лежат в `materials/фото_автора/`** (🟡 сейчас заглушка — см. `README.md` в папке). Если там есть `photos_index.json` — читай его и выбирай; если нет — движок сам берёт все JPG/PNG папки. НЕ переописывай фото заново, НЕ запускай ничего перед рендером. **Папка пуста** → пропусти шаги 1–3: движок сверстает обложку и фото-слайды типографикой и предупредит.

1. **Выбирай фото СЛУЧАЙНО через shell** (см. сниппет в `knowledge/visual_dna_format_A.md` → «Подбор фото — РАНДОМ»). Обложка = `random.choice` среди `format: vertical`; контентные слоты = `random.sample`, без повторов внутри карусели. НЕ открывай JPG/PNG через `Read`.
2. Рандом размазывает повторы сам — НЕ выбирай «самое подходящее» вручную (так появляются одинаковые карусели).
3. Если один кадр лежит в нескольких кропах — не брать два подряд (рандом-сэмпл исключает только дубли по имени).
4. Нужен визуальный ре-скан конкретного кадра — сделай превью `sips -Z 700` в черновики, не открывай оригинал.
5. Перед `Read` любого PNG/JPG > 2000px → `sips -Z 2000 file.jpg`.

> **Обслуживание индекса (РЕДКО, не перед каждым рендером).** `photos_index.json` актуален, пока ты не трогал папку. Обновлять его нужно **только если реально добавил или удалил фото** в `materials/фото_автора/`: дописать записи новых файлов (`filename`, `format`, теги) и убрать удалённые. Индекс необязателен — без него движок берёт все картинки папки.

## Шаг 2: Загрузка фото в Higgsfield (если новое)

```
media_upload(filename, content_type="image/jpeg")
→ curl -X PUT "{upload_url}" --data-binary @"/path/to/photo.jpg"
→ media_confirm(media_id)
```

## Шаг 3: Генерация фото-слайдов (1, 5, 9)

```
generate_image(
  model="nano_banana_2",
  prompt="<преамбула из prompts/higgsfield_photo.md> + <контент слайда>",
  aspect_ratio="4:5",
  resolution="1k",
  medias=[{"value": "<media_id>", "role": "image"}]
)
→ job_display(job_id)
→ curl -o "готовые/<название>/0N_*.png" "{image_url}"
```

См. лимиты итераций → `workflows/safe_higgsfield_iteration.md`.

## Шаг 4: Рендер через ЕДИНЫЙ движок `scripts/render.py` (НЕ писать Python!)

🔴 **НЕ создавай свой `generate_slides.py`/`render_pack.py` каждый раз.** Движок один и уже написан. Ты пишешь только **`slides.json`** (контент + выбор макета), движок рендерит.

1. Составь `slides.json` по схеме и каталогу макетов → `knowledge/slide_layouts.md`. Эталон-пример: `templates/slides.example.json`. 10 слайдов = 9 контентных + `{"layout":"cta"}` на 10-й (финал «Подпишись, чтобы не потерять»).
   - Макеты: `cover-photo`, `cover-visual`, `object-list`, `poster`, `photo-overlay`, `stat`, `list`, `insight`, `quote`, `compare`, `formula`, `source`.
   - Фото — `"photo":"auto"` (движок берёт рандомное вертикальное из `materials/фото_автора/`; пусто → типографский фолбэк). Объект Higgsfield — путь в `"object"` (генерится отдельно, на креме; промпт `prompts/higgsfield_3d_object.md`).
   - `accent:true` на куске hero = оранжевый.
2. Положи `slides.json` в `готовые/<название>/черновики/`.
3. Рендер одной командой:
   ```bash
   "<python с playwright>" "<папка скилла>/scripts/render.py" "готовые/<название>/черновики/slides.json" "готовые/<название>"
   ```
   (python с playwright — путь из `config/settings.yml → env.python_with_playwright`; установка — `README.md` скилла.)

Все правила дизайн-системы (Inter, оранжевый `#E85A2C`, line-height ≥1.05, зазоры, объект edge-to-edge, сетка off, счётчик/ник) **зашиты в движок** — в JSON их задавать не нужно. Источник правды по макетам — `knowledge/slide_layouts.md`.

> Объекты Higgsfield (для `cover-visual`/`object-list`) генерируй ОТДЕЛЬНО на креме (`prompts/higgsfield_3d_object.md`), путь к PNG передай в `"object"`. Движок поставит его full-bleed.

## Шаг 5: Self-check

Прочитать 1-2 ключевых PNG (1080×1350, в пределах лимита 2000px → безопасно). Не более 5 за раз.

## Шаг 6: Сдача

- Файлы в `готовые/<название>/` с именами `01_*.png` … `NN_*.png`
- `подпись_под_пост.md` рядом
- Показать сетку (1-2 ключевых через preview, остальное путём)
