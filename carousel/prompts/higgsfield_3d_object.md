# Higgsfield — предмет-метафора (Ward)

🔴 Без генерации: сначала промпт в чат и цена, генерируем только после «да» (правило 24).

Для обложек формата B и визуальных слотов. Шаблон — `_ward/Дизайн-код Ward.md` → 8.3. Предмет — бытовой и честный: журнал сделок, секундомер, стеклянная пешка, ноутбук с чистым графиком. 3D-монеты и биткоин-эмблемы запрещены.

```
Studio still life, 4:5, of {ПРЕДМЕТ-МЕТАФОРА}. Matte black surface and background, soft top light, emerald green (#15C865) rim light, rounded soft forms, realistic materials (paper, glass, matte plastic). Object in the upper half of the frame, the lower half fades to pure black and stays empty for text, top-left corner dark and empty. Color palette strictly black (#000000) and emerald green (#15C865) with white and dim grey accents; deep shadows, soft practical light, subtle film grain; clean, minimal, rounded shapes. No money, no luxury, no casino or gambling imagery, no coins, no exchange logos, no text unless specified.
```

## Параметры
```
generate_image(model="nano_banana_2", prompt="…", aspect_ratio="4:5", resolution="1k")
```

Готовый файл — путь в `"bg"` или `"object"` в `slides.json`, движок ставит его на весь кадр. Текст не внутри картинки: кириллица у нейросети плывёт (`knowledge/known_bugs.md`, баг 2).

## Связано
- `prompts/higgsfield_photo.md` — сцена с человеком
- `workflows/build_cover.md` — сборка обложки
