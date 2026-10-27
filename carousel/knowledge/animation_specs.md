# Анимации Формата B — Утверждённая финальная версия v2.1

После итераций v2 parallax / v3 typewriter / v4 editorial → FINAL (2026-05-05) → FAST FINAL (2026-05-06).

**Эталон:** описан таблицей ниже (HTML-эталон в пакет не входит)
**Production-генератор:** `scripts/render.py` + `slides.json`
**Batch HTML→MP4:** Playwright `record_video` / покадровый скриншот + ffmpeg (скрипт пишется под задачу по этой спецификации)

---

## Что входит в финальную анимацию (v2.1 — ускоренная)

| Элемент | Эффект | Тайминг | Откуда |
|---|---|---|---|
| **Bookmark** | stampIn rotate −30°→0° + scale 0→1 | 0.4s @ 0.2s | v4 |
| **Counter** "NN/16" | fadeIn, JetBrains Mono | 0.3s @ 0.2s | базовый |
| **Header** (номер + название + tagline) | maskReveal по диагонали 135° | **0.5s @ 0.1s** | v4 |
| **Number** (#1...#12) | num-roll slot-machine, останавливается на финальной + glow pulse | **1.0s @ 0.25s** | v3 |
| **Logos** (фото в центре) | Ken Burns scale 1.0→1.12 + translate, infinite alternate | 8s @ 0.7s | v2 |
| **Nick** (ник аккаунта) | charStagger letter-spacing 30px→1px | 0.8s @ 1.0s | v2 |
| **Card** (Желание/Страх/Бренды) | fadeUp + scale + blur, потом построчный typewriter | 0.5s @ 1.3s | v3 |
| **Typewriter rows** | row1 @ 1.7s / row2 @ 2.4s / row3 @ 3.0s | — | v3 |
| **Footer** | fadeIn + drawLine underline | @ 3.7s + 4.0s | v4 |
| **Arrow** "→" | bounce slide infinite | 1.4s @ 4.5s | v2 |
| **Background** | gridShift 40px drift, infinite | 10s linear | v3 |

## Тайм-лайн (в секундах)

```
0.0  — старт
0.1  — header maskReveal (название появляется почти сразу)
0.2  — bookmark stamps in / counter fades in
0.25 — number начинает прокрутку
0.7  — logos появляются + Ken Burns стартует
1.0  — nick charStagger
1.25 — number останавливается на финале
1.3  — card fadeUp
1.7  — typewriter row 1 (Желание)
2.4  — typewriter row 2 (Страх)
3.0  — typewriter row 3 (Бренды)
3.7  — footer fadeIn
4.0  — drawLine underline под footer
4.5  — arrow начинает бесконечный slide
8.5  — длительность видеозахвата (ТЗ для render_animations.py)
```

## ТЗ для будущих рендеров

**Длительность видеозахвата = 8.5s** (`DURATION_MS = 8500` в `render_animations.py`).
Это даёт 4.5s насыщенной вступительной анимации + 4s на «дыхание» циклов (Ken Burns, arrowSlide).
Партия mp4 (2026-05-06) была отрендерена с `6500` для быстроты — для следующих ререндеров возвращаемся к **8500**.
