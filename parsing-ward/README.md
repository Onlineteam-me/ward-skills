# parsing-ward

Конвейер «свежие новости крипторынка → контент Ward для новичков-скальперов».

## Что делает
1. **По расписанию** (по умолчанию пн и пт, 11:00 Киев) тянет свежее из Teable-реестра «Источники», оценивает по рубрике «Охват × Конверсия» под ЦА Ward (ликвидации, листинги и решения бирж, регулирование крипты в Украине/ЕС, скам и разводы, мифы новичков) и пишет отобранное (≥7) в «Отобранные новости» (Статус=Новое).
2. Редактор утверждает строки (Статус=Утверждено) и правит форматы в «Рекомендация».
3. По команде «бери утверждённое» скилл делает контент (карусели/треды/статьи/видео) через скиллы `carousel`, `threads-writer`, `eman-scenario` → «Единицы контента» → (опц.) публикация через `/zernio-posting`.

## Установка
Скопировать папку скилла в `~/.claude/skills/parsing-ward/` или сделать симлинк:
```bash
ln -s "<путь к пакету>/ward-skills/parsing-ward" ~/.claude/skills/parsing-ward
```
Рядом должны стоять скиллы пакета: `carousel`, `threads-writer`, `eman-scenario`, `zernio-posting`.
Зависимости — только Python 3 (стандартная библиотека). Сеть нужна для RSS и Teable.

## 🔴 Перед первым запуском
1. **Teable.** Создать базу и 5 таблиц с полями из `knowledge/pipeline_architecture.md` → раздел «Что создать в Teable».
2. **Конфиг.** В `config/settings.yml` заменить все заглушки `{{...}}`:
   - `{{TEABLE_API_URL}}`, `{{TEABLE_BASE_ID}}`, `{{TEABLE_TABLE_*}}`, `{{TEABLE_VIEW_*}}` — адрес API и ID таблиц/вью;
   - `{{CONTENT_FACTORY_DIR}}` — абсолютный путь к папке, где будут лежать медиа единиц контента;
   - `{{ZERNIO_ACCOUNT_ID_INSTAGRAM}}` — только если планируете публиковать через `schedule_batch.py`;
   - расписание `schedule` и часовой пояс — по желанию.
3. **Ключ.** `cp config/secrets.example.yml config/secrets.yml` и вписать токен Teable (или задать env `TEABLE_API_TOKEN`). Файл `secrets.yml` в `.gitignore`, никуда не отправлять.
4. **Источники.** Заполнить реестр «Источники». Примеры (10–15 типов, все с пометкой «проверить») — `knowledge/sources_and_fetching.md`.
5. **Проверка:** `cd scripts && python3 teable.py check` — покажет, что не настроено, и доступ к каждой таблице.
6. **Расписание (опц.).** Создать scheduled task `parsing-ward-mon-fri` (cron `0 11 * * 1,5`) с промптом «/parsing-ward — парсинг по workflows/daily_parse.md».

Пока заглушки не заполнены, скрипты останавливаются с понятным сообщением, а не падают.

## Запуск — примеры команд
- В чате: `/parsing-ward`, «спарси крипто-новости», «что нового на рынке для Ward», «иди бери утверждённое», «возьми первые 3 и сделай карусели».
- Движки (из папки `scripts/`):
```bash
python3 teable.py check                             # проверка настройки
python3 fetch_sources.py [--hours N] [--no-dedup]   # добыть свежее → JSON + workspace/
python3 teable.py write  ../workspace/rows.json     # записать отобранное (Новое)
python3 teable.py reject ../workspace/rejects.json  # низкие примеры → Отсеяно
python3 teable.py sweep                              # Отклонённое → Отсеяно
python3 teable.py queue                             # очередь утверждённого на контент
python3 teable.py make_unit ../workspace/unit.json  # перенос в «Единицы контента»
python3 teable.py add_source "Имя" "URL" "RSS" 1    # добавить источник
python3 backup.py                                   # дамп таблиц
python3 schedule_batch.py ../workspace/schedule.json  # запланировать карусели в Instagram (Zernio)
bash sync_backup.sh "<папка>"                       # склейка скилла + снапшот в папку-бэкап
```

## Структура
```
SKILL.md             тонкий оркестратор (20 жёстких правил + карта)
config/settings.yml  ID таблиц, пороги, расписание, пути (заглушки {{...}})
config/secrets.yml   токен Teable (🔴 в .gitignore, создать по образцу secrets.example.yml)
knowledge/           рубрика оценки · ЦА Ward из ДНК · архитектура таблиц · источники
workflows/           daily_parse · content_batch
scripts/             fetch_sources.py · teable.py · backup.py · cleanup_zombies.py · schedule_batch.py · sync_backup.sh
templates/           пример строки для записи
workspace/           рабочие выгрузки (сейчас пусто, см. workspace/README.md)
```

Голос и аудитория Ward — `knowledge/audience_dna.md` (выжимка); полные файлы — `_ward/` в пакете.
