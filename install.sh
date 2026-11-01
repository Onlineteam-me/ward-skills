#!/usr/bin/env bash
# Устанавливает скиллы пакета в Claude Code: симлинки в ~/.claude/skills/
# Запуск из корня репозитория: bash install.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
mkdir -p "$DEST" "$HOME/.claude/commands"

for item in ward-content-factory parsing-ward threads-writer eman-scenario zernio-posting _ward; do
  if [ -e "$DEST/$item" ] && [ ! -L "$DEST/$item" ]; then
    echo "⚠ $DEST/$item уже существует и это не симлинк — пропускаю, проверь вручную"
    continue
  fi
  ln -sfn "$REPO/$item" "$DEST/$item"
  echo "✓ $item → $DEST/$item"
done

# карусели — отдельный скилл carousel-ward (личную команду /carousel не трогаем)
ln -sfn "$REPO/carousel" "$DEST/carousel-ward"
echo "✓ carousel → $DEST/carousel-ward (команда /carousel-ward)"

echo
echo "Дальше: открой Claude Code и скажи «настрой завод» — мастер проверит подключения."
