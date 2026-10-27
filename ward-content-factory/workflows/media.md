# Workflow — Медиа: видео HeyGen, карусели, визуал Higgsfield

Шаг «Тексты готовы → Медиа готовы». Всё медиа пули — в одной папке `{storage.media_root}/П-NN <2–4 слова>/`:

```
П-12 скальпинг-сменами/
├── texts/        heygen.txt · threads.txt · carousel.txt (то, что ушло в Teable)
├── video/        heygen.mp4 · cover.png
├── carousel/     01_….png … 10_….png · подпись_под_пост.md
└── черновики/    тесты Higgsfield, отбракованное
```

---

## A. Видео HeyGen (AI-аватар)

Делает оркестратор сам (не субагент): это 2–3 HTTP-запроса. Ключ — `secrets.yml → heygen.api_key`, заголовок `X-Api-Key`. Документация — docs.heygen.com (если ответ API отличается от описанного — свериться с ней, не гадать).

1. **Текст** — ровно то, что между `▼ ТЕКСТ ДЛЯ ОЗВУЧКИ ▼` и `▲ КОНЕЦ ТЕКСТА ▲` в ячейке «Сценарий HeyGen». Ничего не дописывать.
2. **Аватар** — поле пули «Аватар» → ключ пресета (`knowledge/avatar_presets.md`) → `heygen.avatars.<ключ>`: `avatar_id`, `voice_id`, `avatar_type`.
3. **Запрос** `POST {heygen.api_base}/v2/video/generate`:
   ```json
   {
     "video_inputs": [{
       "character": {"type": "talking_photo", "talking_photo_id": "<avatar_id>"},
       "voice": {"type": "text", "input_text": "<текст озвучки>", "voice_id": "<voice_id>", "speed": 1.0}
     }],
     "dimension": {"width": 1080, "height": 1920}
   }
   ```
   Для `avatar_type: avatar` — `"character": {"type": "avatar", "avatar_id": "<avatar_id>", "avatar_style": "normal"}`. Ответ — `video_id`.
4. **Опрос** `GET {heygen.api_base}/v1/video_status.get?video_id=<id>` раз в 30–60 секунд (через `sleep` в shell, не чаще), пока статус не `completed` (или `failed` → показать ошибку человеку). Скачать `video_url` в `video/heygen.mp4`.
5. **Проверка:** длительность (`ffprobe`) в пределах длины из инструкции ячейки ±20%; если сильно длиннее — проверить, не попала ли служебная часть в озвучку.
6. Субтитры и монтаж (таймкоды из «ДЛЯ МОНТАЖА») — человек/монтажёр; оркестратор только кладёт рядом `video/монтаж.md` с этой частью ячейки.

Квота HeyGen кончилась / avatar_id не найден → пуля остаётся «Тексты готовы», сообщить человеку.

## B. Карусели (исполнитель carousel)

🔴 1 карусель = 1 субагент, рендер — последовательно. Бриф — `templates/brief_executor.md`, блок carousel, задача «рендер по утверждённому тексту». В брифе обязательно:
- текст карусели из ячейки (уже прошёл QC — слова не менять, только вёрстка);
- `../_ward/Дизайн-код Ward.md` — палитра, шрифт, правила;
- папка вывода `П-NN …/carousel/`;
- сдать: PNG/MP4 слайдов + `подпись_под_пост.md` (подпись — из ячейки).
Если carousel для визуала зовёт Higgsfield — промпты по шаблонам дизайн-кода (раздел «Шаблоны промптов»).

## C. Обложки и визуал Higgsfield

Делает оркестратор (или субагент carousel внутри своей задачи). Higgsfield — MCP-инструменты в Claude.

1. Источник стиля — только `../_ward/Дизайн-код Ward.md`: палитра, свет, «чего нельзя», шаблоны промптов (обложка Reels/TikTok, фон слайда, предметный кадр).
2. Модель: `higgsfield.image_model_default` (nano_banana_2) для фото и предметки; `image_model_text` (GPT Image) — когда в кадре нужен читаемый текст.
3. Тест — `higgsfield.test_resolution` (1k), не больше `max_retries_per_image` (3) попыток на картинку; потом — показать человеку лучший вариант и спросить.
4. Логотип WARD в генерацию не просим «нарисовать» — модели искажают буквы. Логотип накладывается при вёрстке из файла (`../_ward/логотип/`), либо в кадре — неоновая вывеска из промпта подкастера, проверенная глазами.
5. Сохранить: `video/cover.png` (9:16) или в `черновики/` для отбракованного.

## D. Запись в Teable

```bash
python3 scripts/factory.py set N --field "Папка с медиа" --value "<абсолютный путь к П-NN …>"
python3 scripts/factory.py adapt-list N
python3 scripts/factory.py adapt-set <rec> --field "Файлы" --value "video/heygen.mp4, video/cover.png"
python3 scripts/factory.py adapt-set <rec> --field "Статус" --value "Готово"
python3 scripts/factory.py status N "Медиа готовы"
```
Статус пули повышаем, только когда медиа есть у **всех** адаптаций, которым оно нужно (Threads — не нужно).
