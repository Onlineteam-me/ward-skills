# carousel-ward — Instagram-карусели для Ward

Скилл для Claude Code: превращает текст, ссылку (статья / YouTube), идею или скриншот в готовую Instagram-карусель до 10 слайдов (1080×1350) в дизайн-коде Ward — с хуками, планом на апрув, рендером слайдов и подписью под пост. Голос и аудитория — бренда **Ward** («профессия без глянца», новички в трейдинге). Финальный слайд — «Подпишись, чтобы не потерять».

## Что внутри

- `SKILL.md` — оркестратор: жёсткие правила + карта, куда идти при каких задачах
- `knowledge/` — дизайн-система, формулы хуков, «холодный читатель», баги и фиксы
- `workflows/` — онбординг, план + апрув, рендер форматов A/B/C, видео-фоны, батч, сдача
- `materials/` — ЦА и позиционирование Ward, финальный слайд, формулы хуков, шрифты (OFL), медиа-папки
- `prompts/` — преамбулы для Higgsfield (фото / типографика / 3D-объект)
- `templates/` — пример `slides.json`, шаблон подписи
- `scripts/` — `render.py` (единый рендер), `screenshot_url.py` (скрин источника), `process_video_bg.py` (видео-фоны), `create_batch.py` (батч)
- `config/settings.yml` — ник, цвета, путь к Python, лимиты
- Обязательные материалы бренда лежат в `../_ward/`: дизайн-код, голос, ДНК, логотип

## Установка

1. Сделать симлинк скилла и материалов бренда (логотип и дизайн-код движок читает из `_ward/`):
   ```bash
   ln -s "/путь/к/ward-skills/carousel" ~/.claude/skills/carousel-ward
   ln -s "/путь/к/ward-skills/_ward" ~/.claude/skills/_ward
   ```
2. Команда `/carousel-ward` появляется сама из `SKILL.md`, отдельный файл команды не нужен. `install.sh` из корня пакета делает оба симлинка.
3. Python с Playwright для рендера (один раз):
   ```bash
   python3 -m venv ~/.venvs/carousel
   ~/.venvs/carousel/bin/pip install playwright
   ~/.venvs/carousel/bin/playwright install chromium
   ```
4. Системные утилиты (macOS): `ffmpeg` (видео-слайды), `exiftool` (порядок слайдов на iPhone) — `brew install ffmpeg exiftool`. `sips` уже есть в macOS.

## Настроить перед первым запуском

1. **`config/settings.yml`** — заменить заглушки:
   - `brand.nickname: "{{НИК_АККАУНТА}}"` → ник аккаунта (пока заглушка — ник на слайды не печатается);
   - `env.python_with_playwright` → путь к Python с Playwright, например `"~/.venvs/carousel/bin/python"`. Можно держать значение в `config/settings.local.yml`: он не идёт в git.
2. **Ключей и токенов скилл не хранит.** Генерация картинок идёт через подключённый к Claude Code сервер Higgsfield MCP (вход — в самом Higgsfield). Отдельного `secrets.yml` нет.
3. **Медиа-папки (сейчас пустые заглушки):**
   - `materials/фото_автора/` — фото лица бренда для обложек (формат A/C);
   - `materials/video_bg/` — клипы для «живых» слайдов.
   Что и в каком формате класть — `README.md` внутри каждой папки. Пока папки пусты, скилл работает: обложки и фото-слайды идут на заглушке-градиенте, видео-слайд — статикой, `render.py` пишет предупреждение.
4. **Логотип и шрифт:** официальный логотип — в `../_ward/логотип/` (там README), Montserrat — в `materials/шрифты/Montserrat/`. Без файла шрифта движок берёт Google Fonts, нужен интернет.
5. **`scripts/create_batch.py`** (только для батча) — задать `OUTPUT_ROOT` (папка готовых каруселей).

## Примеры команд

В Claude Code:
```
/carousel-ward
/carousel-ward 5 мифов новичка в трейдинге
карусель Ward из этой статьи: <ссылка>
```

Рендер вручную (если `slides.json` уже готов):
```bash
~/.venvs/carousel/bin/python ~/.claude/skills/carousel-ward/scripts/render.py \
  "готовые/<название>/черновики/slides.json" "готовые/<название>"
```
Пример `slides.json` — `templates/slides.example.json`.

## История

См. `CHANGELOG.md`.
