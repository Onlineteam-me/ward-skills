#!/usr/bin/env python3
"""
Шаблон для массового создания каруселей.

Использование:
  1. Скопируй этот файл в рабочую папку (напр. <папка готовых каруселей>/batch_ДАТА.py)
  2. Заполни список CAROUSELS (название + слайды + подпись)
  3. python3 batch_ДАТА.py        → создаёт папки + slides.json + подписи
  4. Запусти рендер (команды выведутся в конце)

Путь к скиллу и venv берётся из config/settings.yml автоматически.
"""

import json
import os
import subprocess

# ── Пути ─────────────────────────────────────────────────────────────────────
# Скилл = папка выше scripts/. Python с playwright — из config/settings.yml → env.python_with_playwright.
import re
from pathlib import Path

def _skill_dir() -> str:
    """Где лежит скилл: $CAROUSEL_SKILL_DIR → папка выше этого файла (если запущен из scripts/)
    → ~/.claude/skills/carousel (стандартная установка; файл скопирован в рабочую папку)."""
    env = os.environ.get("CAROUSEL_SKILL_DIR")
    if env:
        return os.path.expanduser(env)
    here = Path(__file__).resolve().parent.parent
    if (here / "scripts" / "render.py").exists():
        return str(here)
    return os.path.expanduser("~/.claude/skills/carousel")


SKILL_DIR  = _skill_dir()
RENDER_PY  = f"{SKILL_DIR}/scripts/render.py"
PHOTOS_DIR = f"{SKILL_DIR}/materials/фото_автора"          # заглушка: см. README.md в папке
OUTPUT_ROOT = os.path.expanduser("{{ПАПКА_ГОТОВЫХ_КАРУСЕЛЕЙ}}")  # например ~/Ward/Карусели/готовые


def _venv_python() -> str:
    """Читает env.python_with_playwright из config/settings.yml (без PyYAML)."""
    try:
        txt = Path(SKILL_DIR, "config", "settings.yml").read_text(encoding="utf-8")
        m = re.search(r'^\s*python_with_playwright:\s*"([^"]+)"', txt, re.M)
        if m and "{{" not in m.group(1):
            return os.path.expanduser(m.group(1))
    except Exception:
        pass
    return "python3"   # фолбэк: системный python (нужен установленный playwright)


VENV_PY = _venv_python()

# ── Данные каруселей ──────────────────────────────────────────────────────────
# Каждый элемент = одна карусель.
# "slides" — список слайдов по схеме knowledge/slide_layouts.md
# Слайд 10 всегда {"n":10,"layout":"cta"} — финальный слайд «Подпишись, чтобы не потерять»
# Фото: "auto" (рандом из materials/фото_автора/) или имя файла оттуда.
# Папка фото пуста → движок предупредит и сверстает обложку без фото.

CAROUSELS = [
    {
        "name": "primer_karuseli",           # slug, без пробелов
        "slides": [
            {
                "n": 1, "layout": "cover-photo",
                "slug": "cover",
                "photo": "auto",             # или имя вертикального фото из materials/фото_автора/
                "kicker": "РАЗБОР",
                "hero": ["Главная мысль —", {"t": "акцент тут", "accent": True}]
            },
            {
                "n": 2, "layout": "poster",
                "slug": "context",
                "hero": ["Контекст", {"t": "одним предложением", "accent": True}],
                "caption": "↓ Что разберём ниже"
            },
            # ... слайды 3–9 по схеме ...
            {
                "n": 10, "layout": "cta"     # «Подпишись, чтобы не потерять»
            }
        ],
        "caption": (
            "Первое предложение контента — сразу суть, без «Я» в начале.\n\n"
            "Текст подписи под пост здесь.\n\n"
            "Подпишись, чтобы не потерять.\n\n"
            "Не финансовая рекомендация.\n"
        )
    },
    # Добавляй следующие карусели по тому же образцу:
    # {
    #     "name": "vторая_карусель",
    #     ...
    # },
]

# ── Генерация slides.json и подписей ─────────────────────────────────────────

def make_slides_json(c: dict) -> dict:
    return {
        "title": c["name"],
        "total": 10,
        "photos_dir": PHOTOS_DIR,
        "chrome": {"bookmark": False, "arrow": False, "grid": False},
        "slides": c["slides"]
    }


def create_all() -> None:
    render_cmds = []
    if "{{" in OUTPUT_ROOT:
        raise SystemExit("Задай OUTPUT_ROOT в начале скрипта (папка для готовых каруселей).")

    for c in CAROUSELS:
        out_dir    = os.path.join(OUTPUT_ROOT, c["name"])
        draft_dir  = os.path.join(out_dir, "черновики")
        json_path  = os.path.join(draft_dir, "slides.json")
        caption_path = os.path.join(out_dir, "подпись_под_пост.md")

        os.makedirs(draft_dir, exist_ok=True)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(make_slides_json(c), f, ensure_ascii=False, indent=2)

        with open(caption_path, "w", encoding="utf-8") as f:
            f.write(c["caption"])

        print(f"✓  {c['name']}/черновики/slides.json")

        render_cmds.append(
            f'"{VENV_PY}" "{RENDER_PY}" '
            f'"{out_dir}/черновики/slides.json" '
            f'"{out_dir}"'
        )

    print(f"\nСоздано {len(CAROUSELS)} каруселей. Рендер:\n")
    for cmd in render_cmds:
        print(cmd)

    # Автозапуск рендера — раскомментируй если хочешь сразу рендерить
    # for cmd in render_cmds:
    #     subprocess.run(cmd, shell=True)


if __name__ == "__main__":
    create_all()
