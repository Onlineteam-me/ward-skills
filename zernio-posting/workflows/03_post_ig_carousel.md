# Workflow 03 — POST IG CAROUSEL

**Когда:** в папке ≥2 файла (mix jpg/mp4) ИЛИ в строке Teable «Формат» содержит «Карусель».

---

## Алгоритм

```
1. Собрать media: список файлов в порядке 01, 02, ..., NN.
   - Проверить лимит: ≤ 10 файлов (правило 3). Если >10:
     → спросить пользователя «обрезать какие?» или «перевести в Threads (20 ок)?»
   - Каждый файл: размер jpg ≤ 4MB, mp4 ≤ 4MB.
     mp4 > 4MB → сжать ffmpeg (правило 7).

2. Загрузить медиа через Воркфлоу F (presigned URL):
   for each file:
     a. media_get_media_presigned_url({mimeType, fileName, fileSize})
        → {uploadUrl, publicUrl}
     b. curl -X PUT --data-binary @file -H "Content-Type: <mime>" "<uploadUrl>"
     c. сохранить publicUrl в массив

3. Получить caption: подпись_под_пост.md или из строки «Текст».
   - Длина ≤ 2200 chars
   - Прогнать через knowledge/ward_brand_check.md (призыв, дисклеймер, красные линии)

4. Спросить пользователя о времени (правило диалога):
   - Если в строке «Когда публикуем» есть и в будущем → предложить его
   - Проверить через posts_list конфликт в ± 3 часа на Instagram-аккаунте из config.yaml
     → если конфликт: предложить свободный слот
   - Иначе: спросить «когда?»

5. posts_create:
   {
     content: <caption>,
     media_items: [<10 объектов>],   // ⚠️ TOP LEVEL (правило 9)
                                       // Каждый: {type: "image"|"video", url: <publicUrl>}
     platforms: [{
       platform: "instagram",
       accountId: "{{ZERNIO_ACCOUNT_ID_INSTAGRAM}}"  // из config.yaml, camelCase (правило 6)
     }],
     scheduled_for: "<ISO в поясе config.posting.timezone>",  // или publish_now: true
     timezone: "<config.posting.timezone>"
   }

6. 409 / connection lost → posts_list (правило 1, 8).

7. Запомнить post._id → workflow 05 CONFIRM.
```

---

## Проверки перед отправкой

- [ ] Количество файлов от 2 до 10
- [ ] media_items на TOP LEVEL (не в customMedia!)
- [ ] platformы[].accountId camelCase
- [ ] type = "image"/"video" (не MIME)
- [ ] scheduled_for > now + 5 мин (если используется)
- [ ] Caption ≤ 2200 chars
- [ ] Все файлы успешно залиты в R2 (presignedUrl → publicUrl)

---

## После публикации

→ `workflows/05_archive_local.md` (mv в `Карусели/`)
→ `workflows/07_update_teable.md`:
   - `Статус` = «Опубликовано»
   - В «Ссылки на публикации» дописать: `Instagram: <platformPostUrl>`
   - `Папка с медиа` = локальный путь к папке в архиве
   - `Медиа` = загрузить attachments (имена `slide_NN.jpg`)
