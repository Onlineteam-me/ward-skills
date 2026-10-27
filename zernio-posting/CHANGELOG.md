# CHANGELOG — zernio-posting

## v0.9.0 — 2026-10-27 — Адаптация для Ward

**Адаптация для Ward:** скилл подготовлен к передаче клиенту, методика (правила Zernio, workflows, скрипты загрузки, attachments-flow Teable) сохранена полностью.

- **Аккаунты** Instagram/Threads и их Zernio accountId, profile_id → заглушки `{{INSTAGRAM_USERNAME}}`, `{{THREADS_USERNAME}}`, `{{ZERNIO_ACCOUNT_ID_INSTAGRAM}}`, `{{ZERNIO_ACCOUNT_ID_THREADS}}`, `{{ZERNIO_PROFILE_ID}}` (config.yaml, workflows 02/03/04/09, zernio_rules правило 18, шаблоны).
- **Teable** — адрес, база, таблицы, ID полей и choiceId → заглушки `{{TEABLE_URL}}`, `{{TEABLE_BASE_ID}}`, `{{TABLE_PUBLICATIONS}}`, `{{TABLE_CONTENT_UNITS}}`, `{{TABLE_CHANNELS}}`, `{{FLD_...}}`. Добавлены `content_unit_field_names`, `content_unit_ready_status`, `content_unit_rework_status` — чтобы подключить таблицы Ward («Единицы контента», «Адаптации») без правки workflows. Инструкция по связке — в README.
- **Локальные пути** → `{{ARCHIVE_ROOT}}`, `source_hints` пустой; временные файлы batch — в `_tmp/` вместо `/tmp`.
- **Удалены** устаревшие `knowledge/drive_structure.md` и `workflows/06_upload_to_drive.md` (облачный диск не используется, там были личный аккаунт и ID папок). Поле «Drive папка» переименовано в «Папка с медиа».
- **Удалены** ссылки на личную базу знаний, блоки синхронизации и бэкапа, личные аккаунты и имена из примеров.
- **Новое:** шаг BRAND CHECK + `knowledge/ward_brand_check.md` — проверка подписи по голосу Ward (призыв «Подпишись, чтобы не потерять», дисклеймер «Не финансовая рекомендация», красные линии). Часовой пояс по умолчанию — `Europe/Kyiv`.
- **Пустые папки с медиа** → предупреждение и пропуск формата, а не падение (workflows 07/08/09).
- **Исправлено:** карта файлов в SKILL.md (убраны несуществующие `instagram_workflow.md` / `threads_workflow.md`, добавлен `upload_carousel_v2.py`), счётчик правил (9), опечатка в правиле 6 про имена инструментов, ключ фильтра `conjunction` в workflow 08.
- `config/secrets.example.yml` — только примеры `xxx`, реальных токенов в пакете нет.

## v0.8 — Сплиттер тредов (публикация пачки, не одного поста)

**Проблема:** поле «Тред» содержит 2-3 отдельных поста, разделённых `———`. Скилл отправлял всё одним `posts_create` → пост обрезался по 500 символов, первый тезис терялся.

**Фиксы:**
- `workflows/02_post_threads.md` — алгоритм `split_thread_text()`: сплит по `\n\s*———\s*\n`, срез маркера `Пост N/TOTAL`, публикация в цикле с задержкой 30 сек, все `platformPostUrl` → в Teable через `·`.
- Backward compat: без маркеров — сплит по `———`; без разделителя — один пост.
- `SKILL.md` правило 8: «Threads-поле = ПАЧКА, не один пост». Формат согласован с `threads-writer`.

## v0.2.0 — опыт batch-постинга 14 каруселей

- `scripts/upload_carousel.py` — Python multipart uploader (авто-детект `out/`, явные MIME, 4 потока).
- `workflows/09_batch_carousel_upload.md` — pre-flight → tokens → uploads → posts → PATCH.
- `knowledge/zernio_rules.md`: правила 13–17 (URL только из ответа upload, pre-flight до токена, `out/`, параллелизм, Python вместо bash eval); правило 4 исправлено — `media_generate_upload_link` работает.

## v0.1.1 — Teable Attachments API

- 3-шаговый presigned-flow (signature → PUT → notify → PATCH) разобран и описан в `workflows/07_update_teable.md` и `knowledge/teable_schema.md`.

## v0.1.0 — Старт

- Скелет: `SKILL.md`, `config.yaml`, `README`, `CHANGELOG`.
- Workflow: ROUTE → DETECT → ASK TIMING → POST → CONFIRM → ARCHIVE → UPDATE TEABLE.
- Defaults: `min_interval_hours_ig=3`, Threads = `publish_now`, IG = `ask_slot`.
