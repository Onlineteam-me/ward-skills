# Workflow 07 — UPDATE TEABLE

**Когда:** последний шаг после публикации и локального mv.

**Цель:** записать результат в таблицу «Публикации» — обновить существующую строку или создать новую.

> Подстановки: `{{TEABLE_URL}}` = `config.yaml → teable.base_url`, `{{TEABLE_BASE_ID}}` = `teable.base_id`, `{{TABLE_PUBLICATIONS}}` = `teable.tables.publications`. Токен — из `config/secrets.yml`.

---

## Алгоритм

```
1. Решить: обновить или создать?

   - Если триггер был #row_id → у нас уже есть target_row_id, идём в UPDATE
   - Если триггер был <путь>:
     - Поиск по «Тема» (имя папки или caption first-line):
       curl GET ?search=<тема>
     - Если нашли точное совпадение → UPDATE
     - Иначе → CREATE

2. UPDATE (PATCH):
   curl -X PATCH {{TEABLE_URL}}/api/table/{{TABLE_PUBLICATIONS}}/record/<row_id> \
     -d '{
       "fieldKeyType": "name",
       "record": {"fields": {
         "Статус": "Опубликовано",                           # если IG публикация
         "Статус Threads": "Опубликовано",                   # если Threads публикация
         "Ссылки на публикации": "<existing>\nInstagram: ...",
         "Папка с медиа": "<локальный путь к папке в архиве>"
       }}
     }'

3. CREATE (POST):
   curl -X POST {{TEABLE_URL}}/api/table/{{TABLE_PUBLICATIONS}}/record \
     -d '{
       "fieldKeyType": "name",
       "records": [{
         "fields": {
           "Тема": "<folder_name или first-line caption>",
           "Статус": "Опубликовано",
           "Формат": ["Карусель"],                # или Рилс
           "Текст": "<caption>",
           "Тредс": "<threads_text>",            # если есть
           "Статус Threads": "Опубликовано",      # если Threads опубликован
           "Ссылки на публикации": "Instagram: ...\nThreads: ...",
           "Папка с медиа": "<локальный путь к папке в архиве>",
           "Когда публикуем": "<ISO>"
         }
       }]
     }'
   ⚠️  POST создаёт запись БЕЗ медиа. Сразу после — шаг 4 (attachments). Не считать шаг завершённым без него!

4. 🔴 Загрузка attachments в колонку «Медиа» — ОБЯЗАТЕЛЬНО для каруселей (и UPDATE, и CREATE):
   3-шаговый presigned-flow (см. подробно ниже).
   Имена слайдов в Teable: slide_01.jpg, slide_02.jpg, ... (с подчёркиванием).

5. Подтвердить успех: GET ?recordId — проверить что поля записались.
```

---

## 📎 Teable Attachments API — 3-шаговый flow (проверено на практике)

### Шаг A — получить upload signature

```bash
POST {{TEABLE_URL}}/api/attachments/signature
Authorization: Bearer <TEABLE_TOKEN>
Content-Type: application/json

{
  "contentType": "image/jpeg",          # MIME файла
  "contentLength": 348975,               # size в байтах (stat -f%z)
  "type": 1,                             # 1 = Table attachment
  "baseId": "{{TEABLE_BASE_ID}}"         # ⚠️ ОБЯЗАТЕЛЕН для type=1
}
```

Ответ:
```json
{
  "token": "HJcu7zcOx8Rc",
  "path": "table/HJcu7zcOx8Rc",
  "url": "/api/attachments/upload/HJcu7zcOx8Rc",   # ← относительный!
  "uploadMethod": "PUT",
  "requestHeaders": {
    "Content-Type": "image/jpeg",
    "Content-Length": 348975
  }
}
```

### Шаг B — залить файл

```bash
# URL = {{TEABLE_URL}} + url из шага A
PUT {{TEABLE_URL}}/api/attachments/upload/HJcu7zcOx8Rc
Authorization: Bearer <TEABLE_TOKEN>
Content-Type: image/jpeg
# body: raw binary файла

# bash:
curl -X PUT \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: image/jpeg" \
  --data-binary @01.jpg \
  "{{TEABLE_URL}}/api/attachments/upload/HJcu7zcOx8Rc"
```

Успех: HTTP 200/201 (без тела).

### Шаг C — notify (Teable забирает метадату)

```bash
POST {{TEABLE_URL}}/api/attachments/notify/{token}?filename=slide_01.jpg
Authorization: Bearer <TEABLE_TOKEN>
# без тела
```

Ответ — полный объект attachment, который дальше используется в PATCH:
```json
{
  "token": "HJcu7zcOx8Rc",
  "size": 348975,
  "mimetype": "image/jpeg",
  "width": 1080,
  "height": 1350,
  "path": "table/HJcu7zcOx8Rc",
  "url": "/api/attachments/read/private/table/HJcu7zcOx8Rc?token=...",
  "presignedUrl": "{{TEABLE_URL}}/api/attachments/read/private/..."
}
```

### Шаг D — прицепить к записи (PATCH)

```bash
PATCH {{TEABLE_URL}}/api/table/{tableId}/record/{recordId}
Authorization: Bearer <TEABLE_TOKEN>
Content-Type: application/json

{
  "record": {                                # ⚠️ обернуто в "record" (не "records"!)
    "fields": {
      "Медиа": [
        {"token": "HJcu7zcOx8Rc", "name": "slide_01.jpg"},
        {"token": "<token_2>",    "name": "slide_02.jpg"},
        ...
      ]
    }
  }
}
```

Минимум для каждого элемента: `{token, name}`. Teable сам подтянет size/mimetype/width/height/presignedUrl на основе token.

**Имена слайдов:** `slide_NN.jpg` (с подчёркиванием, NN = 01..10).

### Полный bash-цикл для карусели

```bash
TOKEN="$TEABLE_API_TOKEN"          # из config/secrets.yml или env, в чат не выводить
HOST="{{TEABLE_URL}}"
BASE_ID="{{TEABLE_BASE_ID}}"
TBL="{{TABLE_PUBLICATIONS}}"
REC_ID="<recordId>"
FOLDER="/path/to/local/folder"

# собираем массив attachments
ATTS="["
FIRST=1
for f in "$FOLDER"/*.jpg; do
  # пустая папка → предупреждение, а не падение
  [ -e "$f" ] || { echo "⚠️ В $FOLDER нет .jpg — загрузку в «Медиа» пропускаю"; break; }
  N=$(basename "$f" .jpg)
  SIZE=$(stat -f%z "$f")
  # 1. signature
  SIG=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "{\"contentType\":\"image/jpeg\",\"contentLength\":$SIZE,\"type\":1,\"baseId\":\"$BASE_ID\"}" \
    "$HOST/api/attachments/signature")
  TKN=$(echo "$SIG" | python3 -c "import json,sys;print(json.load(sys.stdin)['token'])")
  URL=$(echo "$SIG" | python3 -c "import json,sys;print(json.load(sys.stdin)['url'])")
  # 2. upload
  curl -s -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: image/jpeg" \
    --data-binary "@$f" "${HOST}${URL}" > /dev/null
  # 3. notify
  curl -s -X POST -H "Authorization: Bearer $TOKEN" \
    "$HOST/api/attachments/notify/$TKN?filename=slide_${N#0}.jpg" > /dev/null
  # добавляем в массив
  [ $FIRST -eq 0 ] && ATTS+=","
  ATTS+="{\"token\":\"$TKN\",\"name\":\"slide_${N}.jpg\"}"
  FIRST=0
done
ATTS+="]"

# 4. PATCH
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"record\":{\"fields\":{\"Медиа\":$ATTS}}}" \
  "$HOST/api/table/$TBL/record/$REC_ID"
```

---

---

## Логика статусов

| Какие публикации прошли | Какие статусы обновить |
|---|---|
| Только IG (Carousel/Reel) | `Статус` = «Опубликовано» |
| Только Threads | `Статус Threads` = «Опубликовано» |
| IG + Threads | оба статуса = «Опубликовано» |
| IG Carousel + IG Reel | `Статус` = «Опубликовано» (одно поле, оба формата выходят) |

---

## Формат поля «Ссылки на публикации»

Многострочное longText. Скилл добавляет новые строки в конец, разделитель `\n`:

```
Instagram: https://www.instagram.com/p/...
Threads: https://www.threads.com/@{{THREADS_USERNAME}}/post/...
```

При повторной публикации (например пере-постинг) — добавлять, не перезаписывать.

---

## Проверки

- [ ] target_row_id или новый row создан
- [ ] Все статусы и ссылки записаны
- [ ] «Папка с медиа» = корректный локальный путь
- [ ] Attachments залиты (для каруселей)
- [ ] Финальный GET показывает корректные данные

---

## Finalize

После успешного 07 — финальный отчёт пользователю (шаблон в `templates/post_confirm.md`).
