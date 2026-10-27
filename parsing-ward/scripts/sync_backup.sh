#!/usr/bin/env bash
# Снапшот скилла в одну папку-бэкап (например, в вашу базу знаний или общий диск).
# Запуск: bash scripts/sync_backup.sh "<папка-назначения>"
# Что кладёт:
#   - parsing-ward — SKILL.md: полная склейка скилла в один .md (токены маскируются, secrets.yml пропускается)
#   - _teable_snapshot_latest/: последний дамп таблиц из backup.py (storage.backups_dir)
#   - content_factory — индекс.md: что лежит в локальной папке медиа (storage.local_root), без самих файлов

set -e
DEST="${1:?Укажи папку назначения: bash scripts/sync_backup.sh \"<папка>\"}"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
NAME="$(basename "$SKILL_DIR")"
mkdir -p "$DEST"

# простое чтение ключа из settings.yml (значение в кавычках)
cfg() { grep -E "^[[:space:]]*$1:" "$SKILL_DIR/config/settings.yml" | head -1 | sed -E 's/^[^:]*:[[:space:]]*"?([^"#]*)"?.*/\1/' | sed -E 's/[[:space:]]+$//'; }

# 1) склейка скилла
OUT="$DEST/$NAME — SKILL.md"
(
  cd "$SKILL_DIR"
  echo "# 🛡 $NAME — полный бэкап (standalone)"
  echo
  echo "> Обновлено $(date +%Y-%m-%d)."
  for f in SKILL.md README.md CHANGELOG.md; do
    [ -f "$f" ] && { echo; echo "---"; echo; echo "## 📄 $f"; echo; cat "$f"; }
  done
  for d in knowledge workflows templates config scripts; do
    [ -d "$d" ] || continue
    for f in "$d"/*; do
      [ -f "$f" ] || continue
      case "$f" in *secrets.yml|*.pyc) continue ;; esac
      echo; echo "---"; echo; echo "## 📁 $f"; echo
      case "$f" in
        *.py) echo '```python'; cat "$f"; echo '```' ;;
        *.yml|*.yaml) echo '```yaml'; cat "$f"; echo '```' ;;
        *.json) echo '```json'; cat "$f"; echo '```' ;;
        *.sh) echo '```bash'; cat "$f"; echo '```' ;;
        *) cat "$f" ;;
      esac
    done
  done
) | sed -E 's/teable_[A-Za-z0-9/+=]{20,}/teable_***МАСКИРОВАНО***/g' > "$OUT"
echo "✓ $NAME → $(du -h "$OUT" | cut -f1)"

# 2) последний снапшот таблиц
BK="$(cfg backups_dir)"
[ -z "$BK" ] && BK="$SKILL_DIR/workspace/_teable_backups"
if [ -d "$BK" ]; then
  LATEST=$(ls -t "$BK" 2>/dev/null | head -1)
  if [ -n "$LATEST" ]; then
    mkdir -p "$DEST/_teable_snapshot_latest"
    rm -f "$DEST/_teable_snapshot_latest"/*.json
    cp "$BK/$LATEST"/*.json "$DEST/_teable_snapshot_latest/" 2>/dev/null || true
    echo "✓ снапшот таблиц ($LATEST) → $DEST/_teable_snapshot_latest"
  fi
else
  echo "⚠ бэкапов таблиц ещё нет ($BK) — запусти python3 scripts/backup.py"
fi

# 3) индекс локальной папки медиа
CF="$(cfg local_root)"
if [ -n "$CF" ] && [ "${CF#\{\{}" = "$CF" ] && [ -d "$CF" ]; then
  IDX="$DEST/content_factory — индекс.md"
  {
    echo "# 🛡 Content Factory — индекс готовых единиц"
    echo
    echo "> Тяжёлые JPG/MP4 не копируются. Обновлено $(date +%Y-%m-%d)."
    echo
    cd "$CF"
    for d in */; do
      [ -d "$d" ] || continue
      echo "## ${d%/}"; echo
      ls "$d" 2>/dev/null | grep -vE "^черновики" | sed 's/^/- /'
      echo
    done
  } > "$IDX"
  echo "✓ индекс медиа → $IDX"
else
  echo "⚠ storage.local_root не настроен или папки нет — индекс медиа пропущен"
fi

echo "📂 Готово: $DEST"
