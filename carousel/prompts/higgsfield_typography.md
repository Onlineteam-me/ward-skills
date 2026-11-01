# Higgsfield — абстрактный фон под типографику (Ward)

🔴 Без генерации: сначала промпт в чат и цена, генерируем только после «да» (правило 24).

Обычно не нужен: заглушка-градиент движка бесплатна и в бренде. Берём, когда хочется живой фактуры. Шаблон — `_ward/Дизайн-код Ward.md` → 8.2.

```
4:5 abstract background for an Instagram carousel slide. Deep black base with a soft emerald green (#15C865) gradient glow from the top-right corner, very subtle grain, large calm negative space in the lower half for typography. Optional: one rounded frosted-glass shape, softly lit. Minimal, premium-but-honest, no objects competing with text. Color palette strictly black (#000000) and emerald green (#15C865) with white and dim grey accents; deep shadows, soft practical light, subtle film grain; clean, minimal, rounded shapes. No money, no luxury, no casino or gambling imagery, no coins, no exchange logos, no text unless specified.
```

Слайд целиком с текстом в картинке — только GPT Image по шаблону 8.4 дизайн-кода и с проверкой букв глазами. По умолчанию текст кладёт `render.py`.

## Параметры
```
generate_image(model="nano_banana_2", prompt="…", aspect_ratio="4:5", resolution="1k")
```
