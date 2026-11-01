# Higgsfield — слайд с человеком или сценой (Ward)

🔴 Без генерации: сначала промпт в чат и цена, генерируем только после «да» (правило 24). Текста на картинке нет — типографику кладёт `render.py`. Лица Ward пока нет: реальное фото клиента важнее ИИ-персонажа.

Шаблон — `_ward/Дизайн-код Ward.md` → 8.1, адаптированный под 4:5:

```
4:5 image for an Instagram carousel slide about {ТЕМА}. {СЦЕНА: e.g. "over-the-shoulder view of a young man at a home desk looking at a dark trading terminal with an order book"}. Composition: subject in the upper half, calm empty dark area in the lower half for a headline overlay, top-left corner dark and empty. Real-life documentary feel, ordinary apartment, not an office, not luxury. One emerald-green (#15C865) glow from the screen as the only accent. 35mm lens, shallow depth of field. Color palette strictly black (#000000) and emerald green (#15C865) with white and dim grey accents; deep shadows, soft practical light, subtle film grain; clean, minimal, rounded shapes. No money, no luxury, no casino or gambling imagery, no coins, no exchange logos, no text unless specified.
```

## Параметры
```
generate_image(model="nano_banana_2", prompt="…", aspect_ratio="4:5", resolution="1k")
```

## Связано
- `prompts/higgsfield_3d_object.md` — предмет-метафора без людей
- `prompts/higgsfield_typography.md` — абстрактный фон под типографику
