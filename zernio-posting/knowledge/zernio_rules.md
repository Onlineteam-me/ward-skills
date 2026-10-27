# Zernio — 17 правил (выжимка)

**Здесь:** сжатый чек-лист всех правил работы с Zernio MCP, собранный на реальных публикациях и факапах. Это первоисточник для скилла.

---

## 🔴 Правило 1 — после 409 НИКОГДА не retry

```
Error: [409] This exact content is already scheduled, publishing, or was posted...
```

→ Пост **уже создан** (race-condition Zernio). Сразу `posts_list` или `posts_get`.
**Что было:** 3 дубля в фиде IG от ретраев.

## 🔴 Правило 2 — scheduled_for в прошлом = публикация немедленно

Zernio не двигает на завтра — публикует сразу.
**Always:** `scheduled_for > now() + 5 min`.

## 🔴 Правило 3 — IG карусель: API лимит 10 слайдов

In-app 20, через API закрыто. Threads = 20. Все планировщики упираются в одно.

## 🔴 Правило 4 — Аплоад медиа: ДВА рабочих пути (исправлено 2026-06-22)

### Путь A — Workflow F (presigned URL, для ОДНОГО файла)

```
1. media_get_media_presigned_url(filename, content_type, size)
   → {uploadUrl, publicUrl, key, expiresIn: 3600}
2. curl -X PUT --data-binary @file.jpg -H "Content-Type: image/jpeg" "<uploadUrl>"
3. использовать publicUrl в media_items
```

Каждый файл = отдельный токен. Хорошо для одиночных Reels или иногда коротких карусели.

### Путь B — `media_generate_upload_link` (для ПАЧКИ файлов — карусель)

🔴 **Опровержение методологии:** этот путь **РАБОТАЕТ**, обкатано 22.06.2026 на 14 каруселях. Старая запись «возвращает HTML страницу» была неверной.

```
1. media_generate_upload_link() → {token, expiresIn: 3600}
2. curl -X POST -F "files=@01.jpg;type=image/jpeg" -F "files=@02.jpg;type=image/jpeg" ... \
       "https://zernio.com/api/v1/media/upload?token=<TOKEN>"
3. Ответ: {"success":true,"files":[{"url":"...","filename":"..."}, ...]}
4. использовать url'ы из ответа в media_items
```

🔴 **MIME обязательны** в каждом `-F` через `;type=…`. Без MIME → `400 "File type 'application/octet-stream' is not supported"`.

🔴 **Токен одноразовый.** Один неуспешный POST = токен «сожжён» (повтор → `409 Upload token has already been used`). Pre-flight check перед получением токена. См. `workflows/09_batch_carousel_upload.md`.

🔴 **Bash `eval` ломается** на `;` в MIME-типах (zsh). Используй `scripts/upload_carousel.py` (Python `requests` с tuples).

## 🔴 Правило 5 — Multi-account → ОБЯЗАТЕЛЬНО accountId

`accounts_list` → копировать ID → передать в `platforms[].accountId`.

## 🔴 Правило 6 — Поля в `platforms[]` = camelCase

- ✅ `accountId`, `customMedia`, `scheduledFor`, `platformSpecificData`
- ❌ `account_id`, `custom_media` → 400 missing_required_field

## 🔴 Правило 7 — Видео > 4MB → сжимать перед аплоадом

```bash
ffmpeg -y -i input.mp4 -c:v libx264 -preset slow -crf 28 -an -movflags +faststart output.mp4
```

CRF 28, без аудио для карусельных слайдов. Проверка: `stat -f%z output.mp4`.

**Исключение:** CTA-видео из библиотеки скилла `carousel` (если она заполнена) уже предсжаты — не трогать. Если библиотека пустая — правило просто не применяется.

## 🔴 Правило 8 — Connection lost ≠ ошибка

MCP connection lost при `posts_create` → пост **скорее всего создан**. Следующий retry получит 409.
**Действие:** то же что при 409 — `posts_list` → проверить.

## 🔴 Правило 9 — `media_items` ОБЯЗАТЕЛЬНО на TOP LEVEL

✅ Правильно:
```json
{
  "content": "...",
  "media_items": [{"type": "video", "url": "..."}],
  "platforms": [{"platform": "instagram", "accountId": "...", "platformSpecificData": {...}}]
}
```

❌ Запрет (Zernio примет без ошибки, но UI покажет «Missing media content»):
```json
"platforms": [{"customMedia": [{"url":"...","type":"video"}]}]
```

## 🔴 Правило 10 — IG Reels = platformSpecificData

```json
"platformSpecificData": {"contentType": "reels", "shareToFeed": true}
```

Без этого Zernio создаёт Feed-пост, не Reel.

## 🔴 Правило 11 — `type` в media_items = строка, не MIME

- ✅ `{"type": "video", "url": "..."}`
- ✅ `{"type": "image", "url": "..."}`
- ❌ `{"type": "video/mp4", ...}` → invalid_field_value

MIME-тип нужен ТОЛЬКО в Content-Type при `curl PUT` (правило 4).

## 🔴 Правило 12 — MOV без конвертации

Instagram через Zernio принимает `.MOV` напрямую. Meta конвертирует.
Content-Type при curl PUT для MOV: `video/quicktime`.

---

## 🆕 Правила 13-17 — batch-постинг каруселей (опыт 22.06.2026)

## 🔴 Правило 13 — НИКОГДА не копировать URL в MCP вручную

В сессии 22.06 я перепутал URL между разными upload-ответами (`98u96c2u` vs `pcbmspuc`) — 3 поста упали с `400 "Image not found at provided URL"`. Файла по тому URL просто не существовало.

**Правило:** URL для `posts_create` берутся **ТОЛЬКО** из ответа upload-эндпоинта программно. Собирай payload в Python/JSON-файл, потом скопируй целиком. Никаких «на память».

## 🔴 Правило 14 — Pre-flight check перед получением токена

**Сначала проверяем что папка с медиа существует, ТОЛЬКО потом запрашиваем токен.**

```python
def find_media_dir(folder):
    for cand in (os.path.join(folder, 'out'), folder):
        if os.path.isdir(cand):
            media = [f for f in os.listdir(cand) if f.endswith(('.jpg','.png','.mp4'))]
            if media: return cand
    return None
```

Если `None` → SKIP единицу контента, **токен не запрашивать**. Пустая папка ≈ потерянный токен.

## 🔴 Правило 15 — Медиа может быть в `<folder>/out/`, а не в корне

Пайплайн `content-factory` кладёт в `out/`. Ручные карусели — в корень. Авто-детект: сначала `out/`, потом корень. См. `scripts/upload_carousel.py:find_media_dir`.

## 🔴 Правило 16 — Параллелить, но осознанно

Структура batch (N каруселей):
1. **Pre-flight** N папок (1 шаг)
2. **Get tokens** — N параллельных MCP-вызовов в ОДНОМ сообщении
3. **Upload** — Python uploader с ThreadPoolExecutor (max_workers=4)
4. **Create posts** — N параллельных `posts_create` MCP-вызовов
5. **PATCH Teable** — последовательно через curl

Не запрашивай токены «впрок» — строго столько, сколько прошло pre-flight.

## 🔴 Правило 17 — Python uploader > bash curl для multipart

Bash `eval` ломается на `;` в MIME, требует ручного quoting массивов, не имеет нормальной error handling. Python `requests` с tuples `(filename, fh, mime)` делает всё чисто.

**Готовый скрипт:** `scripts/upload_carousel.py`. Использование: см. `workflows/09_batch_carousel_upload.md`.

## 🔴 Правило 18 — `platform` обязателен в каждом объекте platforms

```
# ❌ Падает с 400 "platforms.0.platform is invalid"
{"accountId": "{{ZERNIO_ACCOUNT_ID_THREADS}}"}

# ✅ Правильно — явно указать платформу
{"accountId": "{{ZERNIO_ACCOUNT_ID_THREADS}}", "platform": "threads"}
{"accountId": "{{ZERNIO_ACCOUNT_ID_INSTAGRAM}}", "platform": "instagram"}
```

Допустимые значения: `"threads"`, `"instagram"`, `"tiktok"`, `"youtube"`, `"linkedin"`, `"facebook"`, `"bluesky"`.

## 🔴 Правило 19 — Правильные имена MCP-инструментов (открыто 2026-07-09)

Инструменты Zernio MCP для постинга называются **БЕЗ суффикса `_post`:**

```
# ✅ Правильно
posts_create          (НЕ posts_create_post)
posts_list            (НЕ posts_list_posts)
posts_get             (НЕ posts_get_post)
```

**Что было:** 2026-07-09 потратили ~30 минут на ToolSearch по несуществующим именам `posts_create_post` / `posts_list_posts` / `posts_get_post`. Инструменты были доступны, но под другими именами (без суффикса `_post`).

## 🔴 Правило 20 — После реконнекта MCP инструменты могут «пропасть» из списка (2026-07-09)

Zernio MCP экспортирует 300+ инструментов. Claude имеет лимит на видимые инструменты. После реконнекта `posts_*` могут не показываться в ToolSearch, **но они всё равно вызываемые напрямую по имени**.

**Что делать при «tool not found» после реконнекта:**
1. Проверить что ищешь ПРАВИЛЬНОЕ имя (правило 19)
2. Попробовать вызвать инструмент напрямую — он может работать даже если не виден в списке
3. Отключить ненужные категории (analytics, comments, comment automations) чтобы posting-инструменты вместились в лимит

**Fallback:** REST API `https://zernio.com/api/v1/posts` с Bearer-токеном (API key в `config/secrets.yml → zernio_api_key`). Работающие REST-эндпоинты: `GET /accounts`, `GET/POST /posts`, `POST /media/upload?token=`. НЕ работают через REST: `/media/generate-upload-link`, `/media/presigned-url` (только MCP).

---

## 💸 Дедуп 24h (отдельный риск)

Zernio считает hash содержимого. Тот же текст в течение 24h на тот же аккаунт → 409.

**Не помогает обойти:**
- Удаление предыдущего поста
- Trailing whitespace
- Перефразировка концовки
- Смена медиа-URL

**Помогает:**
- Серьёзная переписка опенера
- Подождать 24h

---

## 🚨 Лимиты Meta (актуально на 2026-06)

| Платформа | Карусель | Постов/24ч | Caption |
|---|---|---|---|
| Instagram | 10 | 50 | 2200 chars |
| Threads | 20 | ? | 500 chars |
| TikTok | 35 photo carousel | ? | — |
| LinkedIn | 20 images + 1 PDF | ? | — |

Rate: 200 Graph API calls/час на 1 аккаунт.
