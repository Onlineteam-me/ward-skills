# Higgsfield — Преамбула для слайдов С ФОТО / человеком

Используй эту преамбулу в начале промпта для слайдов, где должен быть человек или фотореалистичный объект (cover-слайды с лицом автора, photo-overlay).

```
PHOTOREALISTIC editorial design. NO cartoon. NO illustration. NO vector art. NO flat 2D style. NO physical mockups. NO 3D page-fold effects. NO magazine physical objects.
TYPOGRAPHY — ALL text uses ONE font only: ultra-bold condensed grotesque sans-serif, weight 900 (Black/Heavy). Use: Druk Wide Heavy, Helvetica Neue Black (900), Impact, or Anton. ZERO serif. ZERO italic. ZERO thin/light. ZERO decorative. Letter-spacing tight. All large text in ALL CAPS.
```

## Когда использовать
- Cover-слайды с лицом бренда (фото из `materials/фото_автора/`)
- Слайды с фото-референсом через `medias: [{value: media_id, role: "image"}]`
- Photo-overlay композиции

## Параметры вызова
```
generate_image(
  model="nano_banana_2",
  prompt="<эта преамбула> + <конкретный контент слайда>",
  aspect_ratio="4:5",
  resolution="1k",
  medias=[{"value": "<media_id>", "role": "image"}]
)
```

## Связано
- `prompts/higgsfield_typography.md` — для слайдов БЕЗ людей
- `prompts/higgsfield_3d_object.md` — для 3D-объектов БЕЗ текста
- `knowledge/known_bugs.md` (Баг 2) — почему преамбулу копируем в каждый промпт
