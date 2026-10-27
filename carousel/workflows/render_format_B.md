# Workflow — Рендер формата B (Higgsfield + HTML гибрид)

См. также: `knowledge/visual_dna_format_B.md`, `knowledge/animation_specs.md`.

---

## Предусловия

- Пройдены `workflows/onboarding.md` + `workflows/plan_and_approve.md`
- Апрув от пользователя
- ТЗ на cover (Higgsfield) и контент остальных слайдов готов

---

## Шаг 1: Cover-слайд (Higgsfield)

См. `workflows/build_cover.md` — отдельный воркфлоу для cover с HTML-overlay.

Если cover простой (без overlay) — генерируй напрямую:
```
generate_image(
  model="nano_banana_2",
  prompt="<преамбула из prompts/higgsfield_3d_object.md> + <ТЗ>",
  aspect_ratio="4:5",
  resolution="1k"
)
```
Лимиты итераций → `workflows/safe_higgsfield_iteration.md`.

## Шаг 2: Контентные слайды (HTML+Playwright)

Эталон: спецификация `knowledge/visual_dna_format_B.md` + `knowledge/animation_specs.md` (готовые примеры в пакет не входят).

### 2a. Без анимаций (PNG)
- Используй `templates/slide_format_B_static.html` как стартовый шаблон.
- Подставь контент в `slides.json` и запусти `scripts/render.py`.
- Рендер через Playwright → PNG 1080×1350.

### 2b. С анимациями (MP4)
- Эталон анимации: тайм-лайн в `knowledge/animation_specs.md`
- Спецификация: `knowledge/animation_specs.md` (тайм-лайн, длительность 8.5s)
- Batch HTML→MP4: Playwright + ffmpeg, скрипт пишется под задачу по спецификации
- `DURATION_MS = 8500` для финальных рендеров.

## Шаг 3: Self-check

**ВАЖНО:** Launch preview блокирует `file://` источники (sandbox Chrome) — внешние картинки не подгрузятся.

- Для эталонных HTML встраивай картинки **base64 inline** (`data:image/png;base64,...`)
- Для production-слайдов в `финал/html/` относительные пути ОК — Playwright при batch-рендере их корректно резолвит
- Прежде чем показать пользователю — отрендерь PNG/MP4 через Playwright и прочитай сам.

## Шаг 4: Защита от падения сессии

- Не читай > 5 PNG подряд
- Перед `Read` PNG > 2000px → `sips -Z 2000`
- Готовые слайды 1080×1350 — в пределах лимита, безопасно
- Batch-операции — последовательно (`render.py` и `render_animations.py` уже последовательные)

## Шаг 5: Сдача

- `финал/html/` — HTML с анимациями
- `финал/mp4/` — рендер для постинга
- `подпись_под_пост.md` рядом
