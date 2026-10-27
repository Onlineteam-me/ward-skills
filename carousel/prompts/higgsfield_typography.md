# Higgsfield — Преамбула для слайдов БЕЗ ФОТО (типографика / UI / формулы)

Используй для слайдов с текстом, формулами, UI-элементами — без людей и фотографий.

```
FLAT 2D digital graphic, displayed on screen. NO physical mockups. NO 3D effects. NO book pages. NO magazine physical objects. NO product photos. NO people. NO photographs.
TYPOGRAPHY — ALL text uses ONE font only: ultra-bold condensed grotesque sans-serif, weight 900 (Black/Heavy). Use: Druk Wide Heavy, Helvetica Neue Black (900), Impact, or Anton. ZERO serif. ZERO italic. ZERO thin/light. ZERO decorative. Letter-spacing tight. All large text in ALL CAPS.
```

## Когда использовать
- Слайды с текстом / формулой / equation
- UI-mockup'ы для иллюстрации
- Типографские слайды

## Параметры
```
generate_image(
  model="nano_banana_2",
  prompt="<эта преамбула> + <контент>",
  aspect_ratio="4:5",
  resolution="1k"
)
```

## Связано
- `prompts/higgsfield_photo.md` — для слайдов С фото/людьми
- `knowledge/known_bugs.md` (Баг 2) — почему преамбулу копируем в каждый промпт
