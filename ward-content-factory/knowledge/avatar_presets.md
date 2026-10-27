# Пресеты AI-аватаров HeyGen

Четыре постоянных персонажа Ward. Каждый закреплён за рубрикой и сегментами — так зритель узнаёт формат с первой секунды. ID аватаров и голосов — `config/settings.yml → heygen.avatars.<ключ>`. Фото-основы аватаров в пакет не входят — `materials/avatars/README.md`.

> Общее для всех: говорят на «ты», спокойно, «свой трейдер за кофе». Глянец только высмеивается. Озвучка — по правилам eman-scenario для HeyGen (без тире, числа словами). Финал — «Подпишись, чтобы не потерять».
> 🔴 Перед первым запуском сверить описания и промпты ниже с финальными версиями из рабочей папки по AI-аватарам и обновить этот файл: здесь — стартовая версия пресетов.

## Как выбрать аватара для пули

| Признак пули | Аватар |
|---|---|
| миф, глянец, «разгон депозита», сигналы, «трейдеры покупают Ламбо» — нужно высмеять | **Бабушка у Ламбо** |
| механика рынка (стакан, стоп, плечо, ликвидации), ответ на вопрос новичка, новость | **Подкастер** |
| разоблачение «жизни трейдера» из ленты, эмиграция, «работа с ноутбуком у моря» | **Девушка в кафе у моря** |
| вечные правила: дисциплина, журнал, риск, психология, история обвалов и пузырей | **Ретро-трейдер 1920-х** |

Поле пули «Аватар» заполняет субагент «пуля». Если не очевидно — Подкастер (универсальный).

| Значение поля «Аватар» в Teable | Ключ в `config/settings.yml → heygen.avatars` |
|---|---|
| Бабушка у Ламбо | `babushka` |
| Подкастер | `podcaster` |
| Девушка в кафе | `cafe_girl` |
| Ретро-трейдер | `retro_trader` |

---

## 1. Бабушка у Ламбо — `babushka`

- **Роль:** мудрая ироничная бабушка ~70 лет, которая стоит у чужого блестящего Ламбо и спокойно разбирает, почему «трейдеры на Ламбо» — это реклама, а не профессия.
- **Рубрика:** «Бабушка объясняет» — разбор мифов и глянца одним житейским сравнением.
- **Сегменты:** Н-5 Обжёгшийся на глянце, Н-4 Крипто-хомяк, массовый охват (TOFU).
- **Темы:** «разгон депозита», сигналы и «гарантии», скрины без минусов, «трейдинг = казино», почему брокер не обещает доход.
- **Голос:** тёплый пожилой женский, неспешный, с улыбкой в голосе; скорость 0.95–1.0.
- **Манера:** житейские сравнения (рынок, огород, сберкнижка, «внучек»), самоирония, никакой злости; поучает без морали. Ламбо — реквизит для иронии, не мечта.
- **Риск:** не превращать в мем ради мема — в каждом ролике одна полезная мысль про риск/дисциплину.
- **Стартовый промпт (nano_banana_2, 9:16):** Photorealistic vertical 9:16 portrait of a warm, witty Ukrainian grandmother around 70 standing next to a glossy parked supercar on an ordinary city street, looking into the camera with a knowing half-smile, one hand resting on a worn shopping bag. Knitted cardigan, simple headscarf around the shoulders, reading glasses on a cord. The supercar is a prop she clearly does not care about. Overcast natural daylight, muted tones with a subtle emerald accent (#15C865) on a small detail like her scarf. No money, no logos, no luxury styling. 35mm lens, shallow depth of field, natural skin texture, candid documentary feel.

## 2. Подкастер в домашней студии — `podcaster`

- **Роль:** практикующий трейдер ~32 лет, ведёт подкаст из домашней студии; на стене — неоновая вывеска **WARD** в фирменном зелёном.
- **Рубрика:** «Честно про трейдинг» — механика рынка простыми словами, ответы на комментарии, разбор новостей из parsing-ward.
- **Сегменты:** Н-1 Застрявший в найме, Н-4 Крипто-хомяк, Б Буксующие (TOFU/MOFU).
- **Темы:** стакан и плотности, стоп-лосс, плечо и ликвидации, «сколько нужно на старт», новости рынка, вопросы новичков.
- **Голос:** мужской 30–35, энергичный, дружелюбный, чуть ироничный; скорость 1.0–1.05.
- **Манера:** «давай честно», разговорные паузы, наклоняется к микрофону на главной мысли; показывает, а не убеждает.
- **Риск:** неон + микрофон не должны выглядеть как лудо-стример: свет мягкий, неона один акцент.
- **Стартовый промпт (nano_banana_2, 9:16):** Photorealistic vertical 9:16 portrait of a 32-year-old Ukrainian man hosting a podcast at home, looking straight into the camera with a friendly confident grin, leaning slightly toward a black podcast microphone on a boom arm. Short dark hair, light stubble, black t-shirt under an open charcoal overshirt, headphones around his neck. On the wall behind him a glowing emerald-green neon sign with the bold word "WARD" in a heavy geometric sans-serif (Montserrat-like). Dark room, soft warm practical lamps, bookshelf, plant, a side monitor with a clean dark trading chart. Black and emerald palette (#000000, #15C865), no other neon colors. 35mm lens, shallow depth of field, cinematic but homey.

## 3. Девушка в кафе у моря — `cafe_girl`

- **Роль:** девушка ~27 лет сидит в «той самой» картинке из рекламы трейдинга — кафе у моря, ноутбук, — и спокойно разоблачает, что это постановка, а настоящая работа выглядит иначе.
- **Рубрика:** «Глянец vs реальность» — разоблачение образа «лёгкой жизни трейдера».
- **Сегменты:** Н-5 Обжёгшийся на глянце, Н-3 Эмигрант не по уровню, Н-1 (TOFU/MOFU).
- **Темы:** «ноутбук у моря», «свобода с первого месяца», реальный день трейдера (рутина, журнал, стоп), трейдинг как навык, который едет с тобой в любую страну.
- **Голос:** женский 25–30, спокойный, ироничный, тёплый; скорость 1.0.
- **Манера:** «посмотри на эту картинку — а теперь правда», поворачивает ноутбук к камере (в кадре — скучный журнал сделок), самоирония без снисхождения.
- **Риск:** не превратиться в «крипто-красотку» — без гламура, украшений и позирования; море — фон для разоблачения, не мечта.
- **Стартовый промпт (nano_banana_2, 9:16):** Photorealistic vertical 9:16 portrait of a 27-year-old Ukrainian woman at a small seaside café table, looking into the camera with a calm, slightly ironic smile as if about to reveal a secret. Natural minimal makeup, hair in a loose low bun, plain dark linen shirt. Laptop turned slightly toward the camera showing a plain spreadsheet-style trading journal with both green and red rows. Overcast sea in the background, not a postcard sunset; muted natural colors with a single emerald accent (#15C865) on the laptop sticker or cup. No cocktails, no jewelry, no luxury. 35mm lens, shallow depth of field, honest documentary look.

## 4. Ретро-трейдер 1920-х со смартфоном — `retro_trader`

- **Роль:** трейдер в стилистике биржи 1920-х (костюм-тройка, подтяжки, шляпа, тикерная лента), но в руке — современный смартфон с терминалом. «Правила рынка не изменились за сто лет».
- **Рубрика:** «Сто лет одних и тех же ошибок» — вечные принципы, психология, история обвалов и пузырей.
- **Сегменты:** Б Буксующие, Н-2 Вернувшийся, Н-3 (MOFU/BOFU).
- **Темы:** дисциплина и план, журнал сделок, риск на сделку, жадность и страх, исторические обвалы как урок про плечо, «если бы начинал с нуля».
- **Голос:** мужской 40–50, низкий, размеренный, чуть театральный; скорость 0.95.
- **Манера:** короткие афористичные фразы, пауза перед выводом, сравнение «тогда / сейчас» (лента → смартфон, слухи → Telegram-сигналы).
- **Риск:** не скатиться в «костюмированное шоу»: одна мысль, применимая сегодня.
- **Стартовый промпт (nano_banana_2, 9:16):** Photorealistic vertical 9:16 portrait of a 45-year-old man styled as a 1920s stock trader: three-piece tweed suit, suspenders, white shirt with rolled sleeves, flat cap, neat moustache. He looks calmly into the camera holding a modern smartphone showing a clean dark trading chart with a single emerald-green candle (#15C865). Background: dim vintage trading floor with a brass ticker-tape machine and paper tape, chalkboard with blurred prices, warm tungsten light with deep black shadows. Film grain, sepia-leaning tones except the phone screen glow. No money piles, no gold, no luxury. 50mm lens, shallow depth of field.

---

## Настройки видео (HeyGen) для всех пресетов

- Формат 1080×1920 (9:16), фон — из фото-основы аватара.
- Длина: 30–60 сек (Shorts/Reels/TikTok), 90–140 слов.
- Субтитры — добавляются при монтаже (Montserrat, по дизайн-коду), не в HeyGen.
- Генерация — `workflows/media.md` → «HeyGen».
