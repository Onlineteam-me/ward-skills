# Workflow 04 — POST IG REEL

**Когда:** в папке 1 mp4/mov ИЛИ строка Teable «Формат» содержит «Рилс».

---

## Алгоритм

```
1. Найти видео:
   - В папке: единственный *.mp4 или *.mov
   - В строке: первый файл с type "video" в «Медиа», или видео из локальной «Папка с медиа»

2. Проверка:
   - Размер ≤ 4MB безопасно (большие могут зависнуть в Meta processing)
   - Если > 4MB → ffmpeg сжатие (правило 7, CRF 28)
   - Длительность ≤ 90 сек для Reels (Meta лимит)
   - 9:16 (1080x1920) — рекомендуется

3. Аплоад через Воркфлоу F (presigned URL):
   - media_get_media_presigned_url({mimeType: "video/mp4", fileName, fileSize})
   - curl PUT в R2
   - получить publicUrl

4. Получить caption (подпись_под_пост.md или «Текст»). Reels caption ≤ 2200 chars.
   Прогнать через knowledge/ward_brand_check.md.

5. Спросить пользователя о времени (см. правила из workflow 03):
   - Default 3 часа между IG-постами
   - В строке поле «Когда публикуем»

6. posts_create:
   {
     content: <caption>,
     media_items: [{type: "video", url: <publicUrl>}],  // TOP LEVEL
     platforms: [{
       platform: "instagram",
       accountId: "{{ZERNIO_ACCOUNT_ID_INSTAGRAM}}",   // из config.yaml
       platformSpecificData: {                    // правило 10 — Reel!
         contentType: "reels",
         shareToFeed: true
       }
     }],
     scheduled_for: "<ISO>",  // или publish_now
     timezone: "<config.posting.timezone>"
   }

7. 409 / connection lost → posts_list (правила 1, 8).
```

---

## Проверки

- [ ] type: "video" (не "video/mp4")
- [ ] platformSpecificData.contentType = "reels"
- [ ] platformSpecificData.shareToFeed = true (рекомендация — пост в фид тоже)
- [ ] Видео ≤ 4MB и ≤ 90 сек
- [ ] media_items на TOP LEVEL
- [ ] camelCase в platforms[]

---

## После публикации

→ `workflows/05_archive_local.md` (mv в `Рилсы/`)
→ `workflows/07_update_teable.md`:
   - `Статус` = «Опубликовано»
   - «Ссылки на публикации» += `Instagram: <platformPostUrl>`
   - Если в «Формат» не было «Рилс» — добавить
