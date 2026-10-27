# carousel — Instagram-карусели для Ward

Скилл для Claude Code: превращает текст, ссылку (статья / YouTube), идею или скриншот в готовую Instagram-карусель до 10 слайдов (1080×1350) в editorial-стиле — с хуками, планом на апрув, рендером слайдов и подписью под пост. Голос и аудитория — бренда **Ward** («профессия без глянца», новички в трейдинге). Финальный слайд — «Подпишись, чтобы не потерять».

## Что внутри

- `SKILL.md` — оркестратор: жёсткие правила + карта, куда идти при каких задачах
- `knowledge/` — дизайн-система, формулы хуков, «холодный читатель», баги и фиксы
- `workflows/` — онбординг, план + апрув, рендер форматов A/B/C, видео-фоны, батч, сдача
- `materials/` — ЦА и позиционирование Ward, финальный слайд, формулы хуков, шрифты (OFL), медиа-папки
- `prompts/` — преамбулы для Higgsfield (фото / типографика / 3D-объект)
- `templates/` — пример `slides.json`, шаблон подписи, HTML-шаблоны
- `scripts/` — `render.py` (единый рендер), `screenshot_url.py` (скрин источника), `process_video_bg.py` (видео-фоны), `create_batch.py` (батч)
- `config/settings.yml` — ник, цвета, путь к Python, лимиты

## Установка

1. Скопировать папку в `~/.claude/skills/carousel` (или сделать симлинк):
   ```bash
   ln -s "/путь/к/ward-skills/carousel" ~/.claude/skills/carousel
   ```
2. Команда `/carousel` (по желанию): в пакете есть `_carousel_command.md` — копия `SKILL.md`:
   ```bash
   cp "/путь/к/ward-skills/_carousel_command.md" ~/.claude/commands/carousel.md
   ```
3. Python с Playwright для рендера (один раз):
   ```bash
   python3 -m venv ~/.venvs/carousel
   ~/.venvs/carousel/bin/pip install playwright
   ~/.venvs/carousel/bin/playwright install chromium
   ```
4. Системные утилиты (macOS): `ffmpeg` (видео-слайды), `exiftool` (порядок слайдов на iPhone) — `brew install ffmpeg exiftool`. `sips` уже есть в macOS.

## Настроить перед первым запуском

1. **`config/settings.yml`** — заменить заглушки:
   - `brand.nickname: "{{НИК_АККАУНТА}}"` → ник аккаунта, например `"@ward.cap"` (печатается на каждом слайде);
   - `env.python_with_playwright: "{{PYTHON_С_PLAYWRIGHT}}"` → например `"~/.venvs/carousel/bin/python"`.
2. **Ключей и токенов скилл не хранит.** Генерация картинок идёт через подключённый к Claude Code сервер Higgsfield MCP (вход — в самом Higgsfield). Отдельного `secrets.yml` нет.
3. **Медиа-папки (сейчас пустые заглушки):**
   - `materials/фото_автора/` — фото лица бренда для обложек (формат A/C);
   - `materials/video_bg/` — клипы для «живых» слайдов.
   Что и в каком формате класть — `README.md` внутри каждой папки. Пока папки пусты, скилл работает: обложки и фото-слайды верстаются типографикой, видео-слайд — статикой, `render.py` пишет предупреждение.
4. **`scripts/create_batch.py`** (только для батча) — задать `OUTPUT_ROOT` (папка готовых каруселей).

Другие заглушки в тексте скилла: `{{НИК_АККАУНТА}}` в HTML-шаблонах и правилах — подставляется из `config/settings.yml` автоматически, вручную менять не нужно.

## Примеры команд

В Claude Code:
```
/carousel
сделай карусель про 5 мифов новичка в трейдинге
карусель из этой статьи: <ссылка>
сделай 3 карусели по мифам из materials/ца.md
```

Рендер вручную (если `slides.json` уже готов):
```bash
~/.venvs/carousel/bin/python ~/.claude/skills/carousel/scripts/render.py \
  "готовые/<название>/черновики/slides.json" "готовые/<название>"
```
Пример `slides.json` — `templates/slides.example.json`.

## История

См. `CHANGELOG.md`.
