# Higgsfield — Преамбула для 3D-объектов (БЕЗ текста внутри)

Используется для cover'ов формата B и для иконок-элементов внутри слайдов.

```
Editorial 3D render. Photorealistic 3D object on cream-beige background #EFEAE0. Negative space, minimal composition. Soft natural lighting from top-left. Subtle shadow. Studio product photography aesthetic.
NO TEXT inside image. NO logos. NO captions. NO labels.
NO cartoon. NO illustration. NO flat 2D. NO physical mockups with text.
Center the object, leave breathing room around it.
```

## 🔴 Вариант для контентных слайдов с текстом (объект сверху, низ пустой)

Когда объект идёт **на весь экран** (full-bleed), а снизу нужно место под заголовок + список (ниша-слайды, листиклы) — генерируй с композицией «объект вверху, низ чистый под текст». Иначе объект встанет по центру и текст ляжет прямо на него.

```
Editorial 3D render. Cream-beige background #EFEAE0 fills the ENTIRE frame edge to edge.
Photorealistic 3D object positioned in the UPPER HALF of the frame, with large empty
cream-beige negative space in the LOWER HALF reserved for text. Object: <ТЗ объекта>,
subtle warm red #E63A1F accents. Soft natural lighting from top-left, subtle shadow,
studio product photography. NO TEXT. NO logos. NO captions. NO cartoon. NO illustration. NO flat 2D.
```

Дальше: full-bleed `<img object-fit:cover; object-position:50% 18%>` + кремовый fade снизу (`linear-gradient(0deg,#EFEAE0 0%,#EFEAE0 30%,transparent 56%)`) + тёмный текст в нижней зоне. Эталон-генератор: `examples/` каруселей формата A (`build_niche_v2.py`). **НЕ ужимать объект в угол** (см. SKILL.md правило 25).

## Когда использовать
- Cover-слайды формата B (статуя / 3D-объект / символ)
- Иконки-элементы для вставки в HTML-слайды
- Slide 02 «приземление» — визуальный объект, обозначающий тему
- **Контентные ниша-слайды формата A** — объект-символ на весь экран + текст снизу (вариант выше)

## Параметры
```
generate_image(
  model="nano_banana_2",
  prompt="<эта преамбула> + <описание объекта>",
  aspect_ratio="4:5",
  resolution="1k"
)
```

## Принцип
- Текст НЕ внутри картинки. Текст накладываем HTML/CSS поверх через `workflows/build_cover.md`.
- Это решает баг 2 (Cyrillic плывёт) и даёт полный контроль над типографикой.

## Связано
- `workflows/build_cover.md` — как накладывать HTML-overlay поверх Higgsfield-генерации
- `knowledge/visual_dna_format_B.md` — цвета и сетка
