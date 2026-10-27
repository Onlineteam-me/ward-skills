# workspace/ — рабочие выгрузки скилла (сейчас пусто, это нормально)

Папка заполняется сама при работе скилла. Ничего класть сюда вручную не нужно.
Содержимое (кроме этого README) не коммитится — см. `.gitignore`.

Что здесь появляется:

| Файл / папка | Кто создаёт | Что это |
|---|---|---|
| `fetch_YYYY-MM-DD.json` | `scripts/fetch_sources.py` | свежие позиции из источников + блок `errors` |
| `rows.json` | модель (Шаг 4 `workflows/daily_parse.md`) | отобранные новости для `teable.py write`, формат — `templates/selected_row.example.json` |
| `rejects.json` | модель | 2–3 низких примера для «Отсеяно (калибровка)» |
| `unit.json` | модель (Шаг 5 `workflows/content_batch.md`) | единица контента для `teable.py make_unit` |
| `schedule.json` | модель/редактор | расписание публикаций для `scripts/schedule_batch.py` |
| `.write_lock` | `teable.py write` | защита от повторной записи чаще раза в 20 часов |
| `_teable_backups/` | `scripts/backup.py` | дампы таблиц, если в `config/settings.yml` не задан `storage.backups_dir` |

Если папку удалить — скрипты создадут её заново.
