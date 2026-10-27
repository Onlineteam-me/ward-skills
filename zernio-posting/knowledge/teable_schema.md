# Teable — таблица «Публикации»

**Base:** `{{TEABLE_BASE_ID}}`
**Table:** `{{TABLE_PUBLICATIONS}}` («Публикации»)
**URL:** `{{TEABLE_URL}}/base/{{TEABLE_BASE_ID}}/table/{{TABLE_PUBLICATIONS}}`

> Все значения в `{{...}}` берутся из `config.yaml` (`teable.*`). Field IDs вашей таблицы тоже вписываются туда.
> В запросах удобнее работать **по именам полей** (`fieldKeyType: "name"`) — тогда ID полей нужны только для фильтров.

---

## 14 полей (рекомендуемая схема)

Если таблицы «Публикации» ещё нет — создайте её с этими полями. Если есть своя таблица (у Ward — «Адаптации», см. `README.md`) — сопоставьте поля и поправьте имена в workflows/шаблонах.

| Ключ в config.yaml | Имя | Тип | Назначение |
|---|---|---|---|
| `tema` | **Тема** | singleLineText (primary) | Короткое название-идентификатор. Скилл генерит из имени папки или подсказывает по содержимому. |
| `status` | **Статус** | singleSelect | Статус IG-публикации. См. options ниже. |
| `format` | **Формат** | multipleSelect | Какие форматы публикации содержит эта строка. См. options. |
| `zagolovok` | **Заголовок** | singleLineText | Короткий хедер (для превью/UI). |
| `tekst` | **Текст** | longText | Подпись/caption для Instagram-поста. |
| `media` | **Медиа** | attachment (multi) | Превью слайдов. Имена: `slide_NN.jpg` (с подчёркиванием). |
| `kanal` | **Канал** | link → «Каналы» | Куда постим (manyMany). Необязательно. |
| `kogda` | **Когда публикуем** | date (часовой пояс из `config.yaml → posting.timezone`, `YYYY-MM-DD HH:mm`) | Запланированное время. Если есть и в будущем — скилл предлагает его как слот. |
| `ssylki` | **Ссылки на публикации** | longText | URL поста в IG/Threads после успешной публикации. Скилл дописывает к существующему. |
| `papka` | **Папка с медиа** | singleLineText | Локальный путь к папке с исходниками (в архиве после публикации). |
| `edinica_kontenta` | **Единица контента** | link → «Единицы контента» | manyOne. Необязательно, можно оставить пустым. |
| `kommentariy` | **Комментарий** | longText | Заметки. |
| `treds` | **Тредс** | longText | Текст для Threads-поста (отдельный от «Текст»). |
| `status_threads` | **Статус Threads** | singleSelect | Отдельный статус для Threads. Те же опции, что и обычный «Статус». |

---

## Опции `Статус` и `Статус Threads`

(один и тот же список значений для обоих полей)

| Имя | Смысл |
|---|---|
| К утверждению | черновик ждёт редактора |
| Утвердить | редактор смотрит |
| К публикации | готово, ждёт слота |
| **Опубликовано** | **скилл ставит после успешной публикации** |
| На доработку | вернули на правку |
| Запланировано | (необязательная опция) |

> Если Teable принимает строку «Запланировано» в `Статус Threads` — она допустима. Если опции нет — фоллбэк на «К публикации».
> choiceId опций не нужны: при записи по имени Teable сам сопоставит значение.

---

## Опции `Формат`

Карусель · Рилс · Пост · Статья · Тредс · Сторис

---

## REST API — рабочие шаблоны

`$TEABLE_URL` = `config.yaml → teable.base_url`, `$TEABLE_TOKEN` = `config/secrets.yml → teable_api_token`, `$TBL` = `config.yaml → teable.tables.publications`.

### Auth header (везде)

```
Authorization: Bearer <TEABLE_TOKEN>
```

### Получить запись по ID

```bash
curl -s -H "Authorization: Bearer $TEABLE_TOKEN" \
  "$TEABLE_URL/api/table/$TBL/record/{record_id}"
```

### Найти запись по теме (примерно)

```bash
curl -s -H "Authorization: Bearer $TEABLE_TOKEN" \
  "$TEABLE_URL/api/table/$TBL/record?search=$(printf '%s' '{Tema}' | jq -sRr @uri)"
```

### Создать запись

```bash
curl -s -X POST -H "Authorization: Bearer $TEABLE_TOKEN" -H "Content-Type: application/json" \
  "$TEABLE_URL/api/table/$TBL/record" \
  -d '{
    "fieldKeyType": "name",
    "records": [{
      "fields": {
        "Тема": "...",
        "Статус": "Опубликовано",
        "Формат": ["Карусель"],
        "Текст": "...",
        "Ссылки на публикации": "Instagram: https://...",
        "Папка с медиа": "<локальный путь к папке в архиве>"
      }
    }]
  }'
```

### Обновить запись (PATCH)

```bash
curl -s -X PATCH -H "Authorization: Bearer $TEABLE_TOKEN" -H "Content-Type: application/json" \
  "$TEABLE_URL/api/table/$TBL/record/{record_id}" \
  -d '{
    "fieldKeyType": "name",
    "record": {
      "fields": {
        "Статус": "Опубликовано",
        "Ссылки на публикации": "Instagram: https://..."
      }
    }
  }'
```

### Загрузка attachments (для колонки «Медиа»)

✅ **Подтверждено и протестировано.**

Teable attachments — 3-шаговый presigned-flow:

1. **POST** `/api/attachments/signature` → `{token, url, uploadMethod}`
   Body: `{contentType, contentLength, type:1, baseId}`
2. **PUT** на `$TEABLE_URL{url}` с binary body файла
3. **POST** `/api/attachments/notify/{token}?filename=...` → полный объект metadata
4. **PATCH** записи: `{"record": {"fields": {"Медиа": [{"token":"...", "name":"slide_01.jpg"}, ...]}}}`

**Ключевые детали:**
- `type: 1` = табличный attachment, нужен **обязательно** `baseId` в шаге 1
- `uploadMethod` = **PUT**, не POST
- `url` в ответе шага 1 — относительный, префиксовать host
- В PATCH объект обёрнут в `"record"`, не `"records"` (отличается от CREATE!)
- Минимум для PATCH-элемента: `{token, name}`. Остальные поля Teable подтянет сам.

Полный bash-цикл с пошаговыми примерами — `workflows/07_update_teable.md` раздел «Teable Attachments API».

---

## Логика выбора статусов скиллом

| Что опубликовали | Что обновляем |
|---|---|
| Только IG Carousel | `Статус` = «Опубликовано» |
| Только IG Reel | `Статус` = «Опубликовано» (+ в `Формат` добавляется «Рилс») |
| Только Threads | `Статус Threads` = «Опубликовано» |
| IG + Threads вместе | оба статуса = «Опубликовано» |

---

## Что НЕ трогаем

- «Канал» — лучше не пересоздавать связки через API (рискованно с manyMany). При создании новой строки оставляем пустым, пользователь свяжет вручную.
- «Единица контента» — оставляем пустым, если пользователь не попросил связать.
- «Заголовок» — заполняем только если он явно есть в исходнике (например первая строка `подпись_под_пост.md`).
