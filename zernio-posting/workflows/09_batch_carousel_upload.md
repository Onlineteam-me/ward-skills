# Workflow 09 — Batch-постинг карусели (Единицы контента)

**Когда:** триггер «опубликуй принятые» или массовый постинг из «Единиц контента» (2/день, например).

**Цель:** запланировать N IG-каруселей разом без потерь токенов и без копипасты URL.

> 🔴 Этот воркфлоу обкатан на пачке из 14 каруселей. Все грабли, которые встретились, разобраны в соответствующих правилах ниже.
>
> Временные файлы (`pairs.txt`, `batch.json`, `post_*.json`) кладём в рабочую папку `_tmp/` рядом с контентом и удаляем после батча. В них есть одноразовые upload-токены — в чат не выводить.

---

## ⚠️ Грабли, которые ты сейчас НЕ повторишь

### 1. Тoкены `media_generate_upload_link` — одноразовые

Каждый токен живёт **60 минут**, но даже один **частичный** или **неуспешный** POST его «сжигает». Повторный запрос → 409 "Upload token has already been used".

**Правило:** ОДИН токен = ОДИН POST со всеми файлами карусели. **Не палить токены на пробу.** Делай pre-flight check (см. шаг 1) ДО получения токена.

### 2. Папка может быть в `<folder>/out/`, не в корне

Часть пайплайнов (например `content-factory`) кладёт слайды в подпапку `out/`. Часть — в корень папки.

**Правило:** перед получением токена сделать `find_media_dir(folder)` — сначала `out/`, потом корень. Если нигде нет — `SKIP` эту единицу контента, помечать в Teable как пропущенную.

`scripts/upload_carousel.py` делает это автоматически.

### 3. Multipart нуждается в **явном MIME**

`curl -F "files=@x.jpg"` без `;type=image/jpeg` → Zernio отдаст `400 "File type 'application/octet-stream' is not supported"`.

**Правило:** всегда указывать MIME (image/jpeg, image/png, video/mp4). Python `requests` с tuples `(filename, fh, mime)` делает это сам.

### 4. **НИКОГДА** не копировать URL в MCP-вызов вручную

В одной из сессий я перепутал URL между разными upload-ответами (`98u96c2u` vs `pcbmspuc`) — и 3 поста упали с `400 Image not found`. Файла по тому URL просто не было.

**Правило:** URL для `posts_create` берутся **ТОЛЬКО** из ответа upload-эндпоинта, парсятся программно и подставляются в шаблон. Никаких ручных копипаст.

### 5. Bash `eval` ломается на `;` в типах файлов

`for f; do ARGS="$ARGS -F files=@$f;type=image/jpeg"; done` + `eval curl $ARGS` → zsh интерпретирует `;` как разделитель команд.

**Правило:** для multipart-uploads используй **Python uploader** (`scripts/upload_carousel.py`), не shell-eval.

---

## ✅ Алгоритм batch-постинга N каруселей

```
Шаг 1 — PRE-FLIGHT: проверить все папки
Шаг 2 — GET TOKENS: N токенов параллельно
Шаг 3 — UPLOAD: N папок через Python uploader (concurrent)
Шаг 4 — POST: N постов через MCP (параллельные tool calls)
Шаг 5 — PATCH TEABLE: per-format статусы
```

---

## Шаг 1 — Pre-flight

Для каждой единицы контента проверить:

```python
import os
def find_media_dir(folder):
    for cand in (os.path.join(folder, 'out'), folder):
        if not os.path.isdir(cand): continue
        media = [f for f in os.listdir(cand) if f.endswith(('.jpg','.jpeg','.png','.mp4'))]
        if media: return cand
    return None
```

- Если `find_media_dir` вернул `None` → **SKIP** эту единицу (в финальном отчёте перечислить).
- Если медиа есть, посчитать кол-во — должно быть ≤10 (Meta API лимит). Если >10 — спросить какой выкинуть.
- Прочитать `Подпись к карусели` из Teable записи — проверить что не пустая.

В результате получить чистый список:
```
[
  {"rec_id": "rec...", "folder": "/path/to/folder", "media_dir": "/path/.../out", "caption": "...", "slot": "2026-06-22T18:00:00"},
  ...
]
```

## Шаг 2 — Get tokens

Получить N токенов параллельно через MCP. Один токен на одну карусель.

```python
# Псевдокод (выполняется как N параллельных MCP tool calls в одном сообщении)
tokens = [media_generate_upload_link() for _ in range(N)]
```

🔴 НЕ запрашивай токены заранее «впрок» — получи СТРОГО столько, сколько чистых каруселей после pre-flight.

## Шаг 3 — Upload через Python

Создать `_tmp/pairs.txt`:
```
1|<TOKEN_1>|/path/to/carousel_1
2|<TOKEN_2>|/path/to/carousel_2
...
```

Запустить:
```bash
mkdir -p _tmp
python3 ~/.claude/skills/zernio-posting/scripts/upload_carousel.py < _tmp/pairs.txt > _tmp/batch.json
# stderr не глушим: там прогресс и предупреждения «no media found» по пустым папкам
```

Скрипт сам:
- авто-детектит `out/`
- ставит правильный MIME
- параллельно (до 4) загружает
- возвращает JSON `{"1": {"files":[...]}, "2": {"files":[...]}, ...}`

Парсить:
```python
import json
batch = json.load(open('_tmp/batch.json'))
for name, result in batch.items():
    if 'error' in result:
        print(f"SKIP {name}: {result['error']}")   # пустая папка → предупреждение, не падение
        continue
    urls = [(f['url'], f['filename']) for f in result['files']]
    # сохранить URL в финальный план для шага 4
```

## Шаг 4 — Создать N постов через MCP

🔴 **URLs берём СТРОГО из batch.json**. Никаких ручных копий. Лучше всего собрать payload в Python и распечатать готовый media_items[] JSON, потом скопировать в MCP-вызов целиком.

```python
# Готовим payload-файлы для каждого поста
for name, result in batch.items():
    plan_entry = plan[name]
    media_items = [
        {'type': 'video' if f['url'].endswith('.mp4') else 'image', 'url': f['url']}
        for f in result['files']
    ]
    payload = {
        'content': plan_entry['caption'],
        'platforms': [{'platform': 'instagram', 'accountId': '<config.zernio.accounts.instagram.account_id>'}],
        'media_items': media_items,
        'scheduled_for': plan_entry['slot'],
        'timezone': '<config.posting.timezone>'
    }
    with open(f'_tmp/post_{name}.json','w') as out:
        json.dump(payload, out, ensure_ascii=False)
```

Далее — N параллельных `posts_create` MCP-вызовов, каждый берёт payload из соответствующего файла.

## Шаг 5 — PATCH Teable

После каждого успешного `posts_create` (status = scheduled):

```bash
curl -X PATCH -H "Authorization: Bearer $TKN" -H "Content-Type: application/json" \
  "{{TEABLE_URL}}/api/table/{{TABLE_CONTENT_UNITS}}/record/<rec_id>" \
  -d '{"fieldKeyType":"name","record":{"fields":{"Post Insta":"Опубликован"}}}'
```

(см. правила пути B — статус строки НЕ трогать, только per-format)

---

## Финальный отчёт пользователю

```
✅ Запланировано N каруселей (<даты>, 2/день в 08:00/18:00)
⚠️ Пропущено M (нет медиа): <концепты>
📊 Teable обновлён: Post Insta = «Опубликован» для N единиц
```

---

## Связанные

- `scripts/upload_carousel.py` — uploader (запускается из этого workflow)
- `workflows/08_path_B_content_units.md` — общий путь B
- `workflows/03_post_ig_carousel.md` — детали одного IG-поста
- `knowledge/zernio_rules.md` — все 20 правил Zernio
