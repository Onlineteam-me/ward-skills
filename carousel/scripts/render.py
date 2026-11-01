#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render.py — ЕДИНЫЙ рендер-движок скилла carousel-ward (дизайн-код Ward, 2026-11-01).

Заменяет «модель пишет Python каждый раз». Модель готовит slides.json — этот скрипт рендерит.
Все правила дизайн-системы зашиты ЗДЕСЬ (источники: _ward/Дизайн-код Ward.md, knowledge/slide_layouts.md):
  • только Montserrat, плотный трекинг; чёрный фон + Emerald #15C865; темы black / green / white
  • логотип накладывается ИЗ ФАЙЛА (_ward/логотип/), нейросетью не генерируется
  • скругления 24–40 px, ярлыки-пилюли, один акцент на кадр
  • фон-картинка из Higgsfield (поле "bg") либо заглушка-градиент бренда ("bg":"placeholder")
  • line-height ≥1.05, зазор заголовок→body ≥32px; заголовок сам ужимается по ширине кадра
  • CTA — финальный слайд «Подпишись, чтобы не потерять» (layout "cta"),
    верстается движком, текст — materials/финальный_слайд.md
  • проверка текста на красные линии Ward — предупреждения в консоль
  • пустые медиа-папки (фото, видео-фоны) — НЕ падение, а предупреждение + фолбэк

Запуск (через Python с playwright из config/settings.yml → env.python_with_playwright):
    python render.py <slides.json> <output_dir>

Схема slides.json и каталог макетов: knowledge/slide_layouts.md
"""
import sys, json, base64, asyncio, random, subprocess, shutil, unicodedata, os, datetime, re
from pathlib import Path
from playwright.async_api import async_playwright

# --- пути ---
SKILL = Path(__file__).resolve().parent.parent
FONTS_DIR = SKILL / "materials/шрифты/Montserrat"
LOGO_DIR = SKILL.parent / "_ward" / "логотип"
PHOTOS_DIR_DEFAULT = SKILL / "materials" / "фото_автора"   # заглушка: см. README.md в папке
SETTINGS = SKILL / "config" / "settings.yml"
IMG_EXT = (".jpg", ".jpeg", ".png")

def load_nickname():
    """Ник аккаунта для слайдов — из config/settings.yml → brand.nickname.
    Без PyYAML: простой regex. Пока там заглушка {{...}} — ник на слайды не печатается."""
    nick = ""
    try:
        m = re.search(r'^\s*nickname:\s*"([^"]+)"', SETTINGS.read_text(encoding="utf-8"), re.M)
        if m: nick = m.group(1)
    except Exception:
        pass
    if not nick or "{{" in nick:
        print("⚠ ник аккаунта не настроен — слайды без ника. Впиши его в config/settings.yml → "
              "brand.nickname или задай \"nick\" в slides.json")
        return ""
    return nick

DEFAULT_NICK = None   # заполняется в main()

def nick_of(s):
    return s.get("nick") or DEFAULT_NICK or ""

# --- токены дизайн-кода Ward ---
BLACK="#000000"; WHITE="#FFFFFF"; EMERALD="#15C865"; DIM="#656565"; SLATE="#738290"; DEEP="#0B3D22"
THEMES=("black","green","white")

def b64_file(path, mime):
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()

def font_links():
    """Montserrat: локальный файл из materials/шрифты/Montserrat/, иначе Google Fonts при рендере.
    Без шрифта рендер не идёт — проверка в assert_font()."""
    files=sorted(FONTS_DIR.glob("*.ttf"))+sorted(FONTS_DIR.glob("*.woff2")) if FONTS_DIR.exists() else []
    if files:
        fmt="woff2" if files[0].suffix==".woff2" else "truetype"
        src=b64_file(files[0], "font/"+files[0].suffix[1:])
        return f"<style>@font-face{{font-family:'Montserrat';src:url('{src}') format('{fmt}');font-weight:100 900;}}</style>"
    print("⚠ локального Montserrat нет (materials/шрифты/Montserrat/) — беру с Google Fonts, нужен интернет")
    return ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
            'family=Montserrat:wght@400;500;600;700&display=block&subset=cyrillic">')

FONT_LINKS = font_links()

_logos={}
def logo_of(color):
    """Логотип только из файла. Файла нет → без логотипа + предупреждение (генерировать нельзя)."""
    if color not in _logos:
        p=LOGO_DIR/f"WARD_logo_{color}.png"
        if p.exists():
            _logos[color]=b64_file(p,"image/png")
        else:
            print(f"⚠ нет файла логотипа {p} — слайд без логотипа")
            _logos[color]=None
    return _logos[color]

def top_chrome(counter, color):
    src=logo_of(color)
    img=f'<img class="logo" src="{src}" alt="WARD">' if src else ""
    return f'<div class="top">{img}<div class="counter">{counter}</div></div>'

GRAIN=("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E"
       "%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2'/%3E"
       "%3CfeColorMatrix values='0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 .5 0'/%3E%3C/filter%3E"
       "%3Crect width='300' height='300' filter='url(%23n)'/%3E%3C/svg%3E\")")

GLOW_AT={"tr":"100% 0%","tl":"0% 0%","br":"100% 100%","bl":"0% 100%"}
def placeholder_bg(s):
    """Заглушка на месте картинки Higgsfield: градиент бренда + зерно (дизайн-код, раздел 1)."""
    at=GLOW_AT.get(s.get("glow","tr"),"100% 0%")
    print(f"🟡 слайд {s['n']}: фон-заглушка (градиент бренда) — заменить картинкой Higgsfield перед публикацией")
    return (f'<div class="photo" style="background:radial-gradient(115% 80% at {at},'
            f'rgba(21,200,101,.9) 0%,{DEEP} 44%,{BLACK} 80%)"></div>'
            f'<div class="photo" style="background-image:{GRAIN};opacity:.09"></div>')

# --- BASE CSS (литералы, без f-string) ---
BASE_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
html,body { width:1080px; height:1350px; overflow:hidden; font-family:'Montserrat',sans-serif; }
.slide { --bg:#000000; --fg:#FFFFFF; --acc:#15C865; --chrome:#738290; --card:rgba(115,130,144,.16); --line:rgba(115,130,144,.3);
  position:relative; width:1080px; height:1350px; background:var(--bg); color:var(--fg); overflow:hidden; }
.slide.t-green { --bg:#15C865; --fg:#000000; --acc:#000000; --chrome:#0B3D22; --card:rgba(0,0,0,.12); --line:rgba(0,0,0,.25); }
.slide.t-white { --bg:#FFFFFF; --fg:#000000; --acc:#15C865; --chrome:#656565; --card:rgba(115,130,144,.14); }
.slide.light { --chrome:#FFFFFF; }
.top { position:absolute; top:60px; left:90px; display:flex; align-items:center; gap:36px; z-index:6; }
.logo { height:34px; width:auto; display:block; }
.counter { font-weight:600; font-size:24px; color:var(--chrome); font-variant-numeric:tabular-nums; }
.nick { position:absolute; bottom:64px; left:90px; font-size:24px; font-weight:500; color:var(--chrome); z-index:6; }
.arrow { position:absolute; bottom:56px; right:80px; font-size:54px; color:var(--acc); font-weight:600; z-index:6; }
.kicker { display:inline-block; padding:10px 26px; border-radius:999px; background:var(--acc); color:var(--bg);
  font-weight:700; font-size:24px; text-transform:uppercase; margin-bottom:30px; }
.hero { font-weight:700; line-height:1.08; letter-spacing:-.06em; white-space:nowrap; }
.hero .acc { color:var(--acc); }
.body { font-weight:500; line-height:1.3; margin-top:36px; letter-spacing:-.01em; }
.cap  { font-weight:400; line-height:1.35; }
.photo { position:absolute; inset:0; background-size:cover; background-position:center; }
.scrim { position:absolute; inset:0; background:linear-gradient(to bottom,rgba(0,0,0,.25) 0%,rgba(0,0,0,0) 22%,rgba(0,0,0,0) 38%,rgba(0,0,0,.62) 62%,rgba(0,0,0,.92) 100%); }
.stack { position:absolute; left:90px; right:90px; bottom:150px; z-index:4; }
.mid { position:absolute; top:50%; left:90px; right:90px; transform:translateY(-50%); z-index:4; }
.bullet { display:flex; gap:20px; align-items:baseline; margin-bottom:22px; }
.bullet .dot { color:var(--acc); font-size:22px; line-height:1.2; }
.bullet .txt { font-weight:600; font-size:34px; }
.card { background:var(--card); border-radius:32px; }
"""

# Ужать заголовок, если строка шире кадра; подсветить вылеты в консоль.
FIT_JS = """() => {
  const issues=[]; const W=900;
  for (const h of document.querySelectorAll('.hero')) {
    const box=h.closest('.card')||h.parentElement;
    const maxW=Math.min(W, box.clientWidth||W);
    let size=parseFloat(getComputedStyle(h).fontSize);
    const start=size;
    h.style.display='inline-block';
    while (h.getBoundingClientRect().width>maxW && size>44) { size-=2; h.style.fontSize=size+'px'; }
    h.style.display='';
    if (size<start) issues.push(`заголовок ужат ${start}→${size}px`+(size<start*.8?' — лучше разбей строку на две':''));
    if (size<=44) { h.style.whiteSpace='normal'; issues.push('🔴 заголовок не лезет — сократи текст'); }
  }
  const top=document.querySelector('.top'); const topB=top?top.getBoundingClientRect().bottom:0;
  for (const b of document.querySelectorAll('.stack,.mid')) {
    const r=b.getBoundingClientRect();
    if (r.top<topB+16) issues.push('🔴 текст наезжает на логотип/счётчик сверху — сократи');
    if (r.bottom>1350-100) issues.push('🔴 текст уходит в зону ника снизу — сократи');
  }
  for (const e of document.querySelectorAll('.stack *,.mid *')) {
    const r=e.getBoundingClientRect();
    if (r.right>1080-70) { issues.push('🔴 текст вылезает за правое поле — сократи'); break; }
  }
  return issues;
}"""

async def assert_font(pg):
    """Без Montserrat с кириллицей браузер молча подставит засечки — такой слайд сдавать нельзя."""
    ok=await pg.evaluate("""async()=>{await document.fonts.load('700 40px Montserrat','Жж');
        await document.fonts.ready; return document.fonts.check('700 40px Montserrat','Жж')}""")
    if not ok:
        print("🔴 ABORT: Montserrat с кириллицей не загрузился. Положи шрифт в materials/шрифты/Montserrat/ "
              "или проверь интернет."); sys.exit(1)

# Красные линии Ward (голос бренда + дизайн-код): проверка текста слайдов перед рендером
RED_LINES=[(r"заработ|доход|быстр\w*\s+деньг","теневой бан: заработок / доход / быстрые деньги"),
           (r"без\s+риска|гарантир","обещание: «без риска» / «гарантированно»"),
           (r"₽|\bруб","валюта только $ или USDT"),
           (r"binance|bybit|\bokx\b|бинанс|байбит","названия бирж нельзя"),
           (r"\+\s?\d+\s?%","стрелки и проценты в плюс как обещание"),
           (r"https?://|www\.","внешние ссылки нельзя")]
def lint_copy(slides):
    for s in slides:
        if s["layout"]=="source": continue
        txt=json.dumps({k:v for k,v in s.items() if k not in ("bg","photo","object","video","slug","layout")},ensure_ascii=False)
        for pat,why in RED_LINES:
            m=re.search(pat,txt,re.I)
            if m: print(f"🔴 красная линия, слайд {s['n']}: «{m.group(0)}» — {why}")


# --- утилиты ---
def hero_html(parts, size, color=None):
    """parts: список строк или {'t':..,'accent':True}. Возвращает <br>-разделённый hero."""
    out=[]
    for p in parts:
        if isinstance(p,dict):
            cls="acc" if p.get("accent") else ""
            out.append(f'<span class="{cls}">{p["t"]}</span>')
        else:
            out.append(str(p))
    col=f"color:{color};" if color else ""
    # трекинг дизайн-кода −60: на кегле меньше 80 px кириллица слипается — там −45
    track="" if size>=80 else "letter-spacing:-.045em;"
    return f'<div class="hero" style="font-size:{size}px;{track}{col}">' + "<br>".join(out) + "</div>"

def prep_image(src, out_assets, maxpx=1500):
    """Копирует+ужимает картинку в _assets, возвращает base64.
    БАГ 1 (фикс): macOS хранит кириллицу в именах в NFD, но индекс может содержать NFC
    (или наоборот). Перебираем варианты нормализации + listdir-фолбэк, чтобы фото
    всегда находились и обложка не рендерилась пустой."""
    if src is None: return None
    p=Path(src)
    candidates=[p]
    if not p.is_absolute():
        # пробуем относительно фотобанка
        for base in (PHOTOS_DIR_DEFAULT, Path.cwd()):
            for form in ("NFC","NFD"):
                candidates.append(base/unicodedata.normalize(form,str(src)))
    else:
        for form in ("NFC","NFD"):
            candidates.append(p.parent/unicodedata.normalize(form,p.name))
    real=next((c for c in candidates if c.exists()), None)
    # последний шанс — listdir с матчингом по нормализованному имени
    if real is None:
        for base in (PHOTOS_DIR_DEFAULT,):
            if not base.exists(): continue
            want=unicodedata.normalize("NFC", Path(src).name)
            for fn in os.listdir(base):
                if unicodedata.normalize("NFC", fn)==want:
                    real=base/fn; break
            if real: break
    if real is None:
        print(f"⚠ prep_image: не нашёл файл «{src}» (NFC/NFD/listdir — все варианты)")
        return None
    out_assets.mkdir(parents=True, exist_ok=True)
    tmp=out_assets/("img_"+real.stem+real.suffix)
    subprocess.run(["sips","-Z",str(maxpx),str(real),"--out",str(tmp)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    mime="image/png" if real.suffix.lower()==".png" else "image/jpeg"
    return b64_file(tmp if tmp.exists() else real, mime)

def load_video_usage(skill_dir=None):
    """Usage-log для видео-клипов (между каруселями), аналогично фото."""
    base=skill_dir or SKILL
    p=base/"materials"/"video_bg"/"_video_usage.json"
    if not p.exists(): return []
    try: return json.loads(p.read_text(encoding="utf-8")).get("recent",[])
    except Exception: return []

def save_video_usage(recent, skill_dir=None, keep=25):
    """25 последних видео = ~25 каруселей (по 1 видео). При пуле 46 клипов —
    расход половины пула перед возможным повтором."""
    base=skill_dir or SKILL
    p=base/"materials"/"video_bg"/"_video_usage.json"
    try:
        p.write_text(json.dumps({"recent":recent[-keep:]}, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    except Exception as e:
        print(f"⚠ save_video_usage: {e}")

def pick_random_video(skill_dir=None, recent=None):
    """Рандомное видео с памятью между каруселями (usage-log).
    Если recent не передан — подгружает лог сам (ленивый режим).
    Возвращает путь к клипу или None."""
    base=skill_dir or SKILL
    vdir=base/"materials"/"video_bg"
    idx=vdir/"video_bg_index.json"
    try:
        clips=[]
        if idx.exists():
            d=json.loads(idx.read_text(encoding="utf-8"))
            clips=[c["file"] for c in d.get("clips",[]) if c.get("file")]
        # берём только реально существующие файлы; индекс пуст → просто *.mp4 из папки
        clips=[c for c in clips if (vdir/c).exists()]
        if not clips and vdir.exists():
            clips=sorted(p.name for p in vdir.glob("*.mp4"))
        if not clips: return None
        if recent is None: recent=load_video_usage(base)
        # Строгий фильтр: не в recent
        pool=[c for c in clips if c not in recent]
        if not pool: pool=clips   # весь пул использован — берём любое
        choice=random.choice(pool)
        return str(base/"materials"/"video_bg"/choice)
    except Exception as e:
        print(f"⚠ pick_random_video: {e}"); return None

def ensure_one_video(slides):
    """РОВНО 1 видео на карусель. Если 0 — авто-вставляем layout='video-bg'
    (текст поверх видео, см. workflows/video_backgrounds.md).
    video-clip (голый mp4 без текста) считаем тоже за «видео», но не форсим его.
    Если >1 — предупреждаем."""
    video_slides=[s for s in slides if s.get("layout") in ("video-bg","video-clip")]
    if len(video_slides)==0:
        content=[s for s in slides if s["layout"]!="cta"]
        if len(content)<3: return
        mid_pos=len(content)//2
        mid_n=content[mid_pos]["n"]
        vid=pick_random_video()
        if vid:
            for s in slides:
                if s["n"]>mid_n or (s["n"]==mid_n and s is not content[mid_pos]):
                    s["n"]+=1
            neighbor=content[mid_pos]
            new_slide={"n":mid_n+1,"layout":"video-bg","slug":"video","video":vid,
                       "kicker":"суть",
                       "hero":["Живой","момент"],
                       "body":""}
            slides.insert(slides.index(neighbor)+1, new_slide)
            print(f"🔴 auto-video: вставлен video-bg {Path(vid).name} слайдом {mid_n+1} с ПУСТЫШКОЙ «Живой момент».")
            print(f"   ЭТО АВАРИЙНЫЙ FALLBACK — модель ДОЛЖНА была задать video-bg в slides.json с уникальным текстом!")
            slides.sort(key=lambda x:x["n"])
        else:
            print("⚠ auto-video: в materials/video_bg/ нет клипов (заглушка) — карусель без видео")
    elif len(video_slides)>1:
        print(f"⚠ {len(video_slides)} видео-слотов (правило: ровно 1). Не режу — проверь сам.")

# HTML для прозрачного оверлея (текст поверх видео) — см. workflows/video_backgrounds.md
VIDEO_OVERLAY_CSS = BASE_CSS + """
/* 🔴 forcing transparent на html/body/.slide — иначе omit_background не сработает */
html, body, .slide { background: transparent !important; }
.scrim { background:linear-gradient(to bottom,rgba(0,0,0,.58) 0%,rgba(0,0,0,.46) 38%,rgba(0,0,0,.46) 62%,rgba(0,0,0,.9) 100%); }
.hero { font-size:84px; }
.body { font-size:36px; }
"""

def build_video_overlay_html(s, total):
    """Прозрачный HTML для оверлея на видео-фон. Тот же контент что у photo-overlay,
    светлый текст + scrim."""
    counter=f'{s["n"]:02d}/{total:02d}'
    kicker=f'<div class="kicker">{s["kicker"]}</div>' if s.get("kicker") else ""
    # hero может быть строкой или списком (с accent)
    hero=s.get("hero") or s.get("title") or []
    if isinstance(hero, str): hero=[hero]
    parts=[]
    for p in hero:
        if isinstance(p, dict):
            cls="acc" if p.get("accent") else ""
            parts.append(f'<span class="{cls}">{p["t"]}</span>')
        else: parts.append(str(p))
    hero_block='<div class="hero">' + "<br>".join(parts) + '</div>'
    body=f'<div class="body">{s["body"]}</div>' if s.get("body") else ""
    nick=f'<div class="nick">{nick_of(s)}</div>' if nick_of(s) else ""
    return (f'<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">{FONT_LINKS}'
            f'<style>{VIDEO_OVERLAY_CSS}</style></head><body>'
            f'<div class="slide light"><div class="scrim"></div>{top_chrome(counter,"white")}'
            f'<div class="stack">{kicker}{hero_block}{body}</div>{nick}</div></body></html>')

async def render_video_bg_slide(s, total, out_dir, pg):
    """Рендер layout='video-bg': прозрачный PNG-оверлей + ffmpeg композит с mp4.
    На выходе: NN_<slug>.mp4 в out_dir. См. workflows/video_backgrounds.md.
    Возвращает True, если видео собрано; False — клипа нет (вызывающий код
    отрендерит слайд статикой, текст не теряется)."""
    if s.get("video") and s["video"]!="auto":
        src=Path(s["video"])
        if not src.is_absolute() and not src.exists():
            src=SKILL/"materials"/"video_bg"/s["video"]
    else:
        picked=pick_random_video()
        src=Path(picked) if picked else None
    if src is None or not src.is_file():
        print(f"⚠ video-bg слайд {s['n']}: клип не найден (materials/video_bg/ пуст?) — "
              f"рендерю этот слайд статикой, текст сохранён")
        return False
    s["video"]=str(src)   # фиксируем выбранный клип для usage-log

    drafts=out_dir/"черновики"; drafts.mkdir(parents=True, exist_ok=True)
    overlay=drafts/f'{s["n"]:02d}_{s.get("slug","video")}_overlay.png'
    html_path=drafts/f'{s["n"]:02d}_{s.get("slug","video")}_overlay.html'
    final=out_dir/f'{s["n"]:02d}_{s.get("slug","video")}.mp4'

    # 1) Прозрачный PNG через Playwright
    html=build_video_overlay_html(s, total)
    html_path.write_text(html, encoding="utf-8")
    await pg.goto(f"file://{html_path}", wait_until="networkidle")
    await assert_font(pg)
    for msg in await pg.evaluate(FIT_JS): print(f"  слайд {s['n']}: {msg}")
    await pg.wait_for_timeout(300)
    await pg.screenshot(path=str(overlay), omit_background=True)

    # 2) Предохранитель: PNG должен иметь альфа-канал
    with open(overlay,"rb") as _f: ct=_f.read(26)[25]
    if ct not in (4,6):
        print(f"⚠ {overlay.name} без альфа-канала (color type={ct}) — оверлей перекроет видео")

    # 3) ffmpeg композит
    cmd=["ffmpeg","-y","-i",str(src),"-i",str(overlay),
         "-filter_complex","[0:v]scale=1080:1350:force_original_aspect_ratio=increase,crop=1080:1350[bg];[bg][1:v]overlay=0:0:format=auto",
         "-c:v","libx264","-profile:v","high","-pix_fmt","yuv420p","-crf","24",
         "-preset","medium","-an","-movflags","+faststart",str(final)]
    r=subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if r.returncode==0 and final.exists():
        size_mb=final.stat().st_size/1024/1024
        print(f"✓ {final.name} (video-bg с overlay, {size_mb:.1f}MB)")
    else:
        print(f"⚠ ffmpeg упал для {final.name}: {r.stderr.decode()[:200]}")
        return False
    return True

def load_usage_log(photos_dir):
    """История использования фото (между каруселями). Хранит последние N фото
    в порядке использования, чтобы исключать их в новых каруселях и максимизировать
    разнообразие ленты Instagram."""
    p=photos_dir/"_photos_usage.json"
    if not p.exists(): return []
    try: return json.loads(p.read_text(encoding="utf-8")).get("recent",[])
    except Exception: return []

def save_usage_log(photos_dir, recent, keep=60):
    """Пишем последние `keep` использований в лог (по умолчанию 60 = ~7 каруселей)."""
    p=photos_dir/"_photos_usage.json"
    try:
        p.write_text(json.dumps({"recent":recent[-keep:]}, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    except Exception as e:
        print(f"⚠ save_usage_log: {e}")

def pick_random_photo(used, photos_dir, recent=None):
    """Рандом с памятью:
    - `used` — фото уже в ТЕКУЩЕЙ карусели (не повторять внутри)
    - `recent` — фото из ПРЕДЫДУЩИХ каруселей (не повторять пока не прошло N)
    Если под фильтрами не осталось фото — плавно ослабляем ограничения."""
    if not photos_dir.exists(): return None
    idx=photos_dir/"photos_index.json"
    if idx.exists():
        d=json.loads(idx.read_text(encoding="utf-8"))
        vert=[x["filename"] for x in d.get("photos",[]) if x.get("format")=="vertical"
              and (photos_dir/x["filename"]).exists()]
    else:
        # индекса нет — берём все картинки из папки (кроме служебных, начинающихся с «_» / «.»)
        d={"photos":[]}
        vert=sorted(p.name for p in photos_dir.iterdir()
                    if p.suffix.lower() in IMG_EXT and not p.name.startswith(("_",".")))
    recent=recent or []
    # 1) Строгий фильтр: не в used + не в recent
    pool=[f for f in vert if f not in used and f not in recent]
    # 2) Если пусто — ослабляем recent (только used-фильтр)
    if not pool: pool=[f for f in vert if f not in used]
    # 3) Если совсем пусто — весь пул
    if not pool: pool=vert
    if not pool: return None
    # Дополнительный anti-monotony: не два подряд одного outfit_set
    if used:
        outfit_by_file={x["filename"]:x.get("outfit_set") for x in d.get("photos",[])}
        last_outfit=outfit_by_file.get(next(reversed(list(used))), None) if used else None
        if last_outfit:
            diff_outfit=[f for f in pool if outfit_by_file.get(f)!=last_outfit]
            if diff_outfit: pool=diff_outfit
    choice=random.choice(pool); used.add(choice); return choice

# --- сборка одного слайда ---
def build_slide(s, total, out_assets, photos_dir, used, recent_photos=None):
    layout=s["layout"]
    counter=f'{s["n"]:02d}/{total:02d}'
    arrow=s.get("arrow", False)
    kicker=f'<div class="kicker">{s["kicker"]}</div>' if s.get("kicker") else ""
    theme=s.get("theme") or ("green" if layout=="cta" else "black")
    if theme not in THEMES:
        print(f"⚠ слайд {s['n']}: неизвестная тема «{theme}» — ставлю black"); theme="black"

    def resolve_photo(val):
        if val=="auto" or val is None:
            f=pick_random_photo(used, photos_dir, recent_photos)
            return prep_image(str(photos_dir/f), out_assets) if f else None
        if not Path(val).is_absolute() and (photos_dir/val).exists():
            val=str(photos_dir/val)       # имя файла из папки фото автора
        return prep_image(val, out_assets)

    light=False; inner=""

    def no_photo(kind):
        """Фото нет. Явно указанный файл не найден → ABORT (опечатка в пути).
        "auto" при пустой папке фото автора → предупреждение + типографский фолбэк."""
        val=s.get("photo","auto")
        if val not in ("auto", None):
            print(f"🔴 ABORT: slide {s['n']} ({kind}) — фото не найдено: «{val}». Проверь путь.")
            sys.exit(1)
        print(f"⚠ slide {s['n']} ({kind}): папка фото автора пуста ({photos_dir}) — "
              f"рендерю без фото (заглушка-градиент). Положи фото в materials/фото_автора/.")

    if layout in ("cover-photo","photo-overlay"):
        img=resolve_photo(s.get("photo","auto"))
        if img is None:
            no_photo(layout)
            if layout=="cover-photo":
                layout="cover-visual"
            else:
                layout="cover-visual"; s=dict(s, hero=s.get("title") or s.get("hero") or [])

    if layout=="cover-photo":
        light=True
        inner=(f'<div class="photo" style="background-image:url(\'{img}\')"></div><div class="scrim"></div>'
               f'<div class="stack" style="color:#fff">{kicker}{hero_html(s["hero"],92)}</div>')
    elif layout=="photo-overlay":
        light=True
        inner=(f'<div class="photo" style="background-image:url(\'{img}\')"></div><div class="scrim"></div>'
               f'<div class="stack" style="color:#fff">{hero_html(s["title"],74)}'
               f'<div class="body" style="font-size:36px">{s["body"]}</div></div>')
    elif layout in ("cover-visual","object-list"):
        # object = картинка Higgsfield (объект сверху, низ чёрный). Нет файла → заглушка-градиент бренда.
        src=s.get("object") if s.get("object") not in (None,"auto") else None
        src=src or (s.get("bg") if s.get("bg") not in (None,"placeholder") else None)
        obj=prep_image(src, out_assets) if src else None
        if obj:
            objdiv=(f'<div class="photo" style="background-image:url(\'{obj}\')"></div>'
                    f'<div class="scrim"></div>')
            light=True
        else:
            objdiv=placeholder_bg(s)
        if layout=="cover-visual":
            body=f'<div class="body" style="font-size:36px">{s["body"]}</div>' if s.get("body") else ""
            inner=objdiv+f'<div class="stack">{kicker}{hero_html(s["hero"],88)}{body}</div>'
        else:  # object-list
            bl="".join(f'<div class="bullet"><span class="dot">●</span><span class="txt">{t}</span></div>' for t in s.get("items",[]))
            inner=(objdiv+f'<div class="stack">{kicker}'
                   f'{hero_html(s["hero"],70)}<div style="margin-top:32px">{bl}</div></div>')
    elif layout=="poster":
        cap=f'<div class="cap" style="margin-top:40px;font-size:34px">{s["caption"]}</div>' if s.get("caption") else ""
        inner=f'<div class="mid">{kicker}{hero_html(s["hero"],100)}{cap}</div>'
    elif layout=="stat":
        # БАГ 4 (фикс): авто-размер большой цифры по длине строки, чтобы $965B / 113K не вылезали
        big=str(s["big"]); L=len(big)
        big_sz = 340 if L<=3 else (270 if L==4 else (220 if L==5 else (190 if L==6 else 160)))
        unit=f'<div class="hero" style="font-size:64px;margin-top:10px">{s["unit"]}</div>' if s.get("unit") else ""
        body=f'<div class="body" style="font-size:36px">{s["body"]}</div>' if s.get("body") else ""
        inner=(f'<div class="mid">{kicker}'
               f'<div style="font-size:{big_sz}px;font-weight:700;line-height:1;color:var(--acc);letter-spacing:-.06em;white-space:nowrap">{big}</div>'
               f'{unit}{body}</div>')
    elif layout=="insight":
        cap=f'<div class="body" style="font-size:36px">{s["caption"]}</div>' if s.get("caption") else ""
        inner=(f'<div class="mid"><div style="font-size:120px;font-weight:700;color:var(--acc);letter-spacing:-.06em;margin-bottom:16px">#{s["insight_no"]}</div>'
               f'{hero_html(s["hero"],84)}{cap}</div>')
    elif layout=="quote":
        # БАГ 15: кавычки настраиваемые — русские «ёлочки» по умолчанию.
        lq,rq=s.get("marks",["«","»"])
        inner_q=(f'<div style="font-weight:600;font-size:56px;line-height:1.22;letter-spacing:-.03em">{lq}{s["quote"]}{rq}</div>'
                 f'<div class="cap" style="margin-top:34px;font-size:28px">— {s["source"]}</div>')
        if s.get("dark",False):
            inner=f'<div class="mid"><div class="card" style="padding:60px 50px">{inner_q}</div></div>'
        else:
            inner=f'<div class="mid">{inner_q}</div>'
    elif layout=="list":
        rows=""
        items=s["items"]
        for i,it in enumerate(items,1):
            lab=it.get("label","") if isinstance(it,dict) else ""
            val=it.get("value",it) if isinstance(it,dict) else it
            num=f'<span style="color:var(--acc);font-weight:700;font-size:26px;min-width:44px">{i:02d}</span>'
            labh=f'<div style="font-weight:700;font-size:34px;letter-spacing:-.02em">{lab}</div>' if lab else ""
            sep="border-bottom:1px solid var(--line);" if i<len(items) else ""
            rows+=(f'<div style="display:flex;gap:26px;align-items:baseline;padding:24px 0;{sep}">'
                   f'{num}<div>{labh}<div style="font-weight:400;font-size:30px;line-height:1.3;margin-top:6px">{val}</div></div></div>')
        # БАГ 14: карточка списка центрируется по вертикали — при 3-5 пунктах жёсткий
        # top:160px оставлял треть кадра пустой снизу (вёрстка читалась как обрыв).
        inner=(f'<div class="mid">{kicker}{hero_html(s["hero"],78)}'
               f'<div class="card" style="margin-top:36px;padding:20px 44px">{rows}</div></div>')
    elif layout=="compare":
        L,R=s["left"],s["right"]
        li="".join(f'<div style="margin-bottom:14px">{x}</div>' for x in L["items"])
        ri="".join(f'<div style="margin-bottom:14px">{x}</div>' for x in R["items"])
        # БАГ 14 (см. list): две колонки тоже центрируем. Левая — приглушённая (дизайн-код: Dim Grey-колонка).
        inner=(f'<div class="mid">{kicker}{hero_html(s["hero"],76)}'
               f'<div style="display:flex;gap:24px;margin-top:36px">'
               f'<div class="card" style="flex:1;padding:34px;color:{SLATE}"><div style="font-weight:700;font-size:34px;margin-bottom:22px">{L["title"]}</div>'
               f'<div style="font-weight:500;font-size:29px;line-height:1.3">{li}</div></div>'
               f'<div class="card" style="flex:1;padding:31px;border:3px solid var(--acc)"><div style="color:var(--acc);font-weight:700;font-size:34px;margin-bottom:22px">{R["title"]}</div>'
               f'<div style="font-weight:500;font-size:29px;line-height:1.3">{ri}</div></div></div></div>')
    elif layout=="formula":
        cap=f'<div class="cap" style="margin-top:40px;font-size:32px">{s["caption"]}</div>' if s.get("caption") else ""
        inner=(f'<div class="mid">{kicker}'
               f'<div class="hero" style="font-size:88px;margin-top:14px">{s["top_block"]}</div>'
               f'<div style="height:6px;border-radius:3px;background:var(--acc);margin:44px 0"></div>'
               f'<div class="hero" style="font-size:88px;color:var(--acc)">{s["bottom_block"]}</div>{cap}</div>')
    elif layout=="source":
        # БАГ 5 (фикс): поддержка реального скриншота вместо серых заглушек.
        # Если в JSON есть "screenshot": "path.png" — вставляем его в мокап браузера.
        url=s.get("url","источник"); cap=s.get("caption","")
        stamp=s.get("stamp","ИСТОЧНИК")
        shot_path=s.get("screenshot")
        if shot_path:
            shot_b64=prep_image(shot_path, out_assets, maxpx=1400)
            content=(f'<img src="{shot_b64}" style="width:100%;display:block">' if shot_b64
                     else f'<div style="padding:60px;color:{SLATE};text-align:center">[скриншот не найден]</div>')
        else:
            content=(f'<div style="padding:38px"><div style="height:24px;width:62%;background:{DIM};border-radius:8px;margin-bottom:22px"></div>'
                     f'<div style="height:16px;width:100%;background:var(--line);border-radius:8px;margin-bottom:12px"></div>'
                     f'<div style="height:16px;width:88%;background:var(--line);border-radius:8px"></div></div>')
        dot=f'<span style="width:13px;height:13px;border-radius:50%;background:{SLATE}"></span>'
        inner=(f'<div style="position:absolute;top:150px;left:90px;right:90px">{kicker}{hero_html(s.get("hero",["Это не выдумка —",{"t":"вот источник","accent":True}]),58)}'
               f'<div class="card" style="margin-top:34px;overflow:hidden">'
               f'<div style="padding:18px 22px;display:flex;gap:10px;align-items:center;border-bottom:1px solid var(--line)">'
               f'{dot}{dot}{dot}<span style="color:{SLATE};font-size:20px;margin-left:14px">{url}</span></div>'
               f'{content}</div>'
               f'<div class="kicker" style="margin-top:26px;margin-bottom:0">{stamp}</div>'
               f'<div class="cap" style="margin-top:20px;font-size:28px">{cap}</div></div>')
    elif layout=="cta":
        # Финальный слайд Ward: «Подпишись, чтобы не потерять» (materials/финальный_слайд.md).
        # Текст можно переопределить полями hero / caption, но по умолчанию — канон.
        hero=s.get("hero") or ["Подпишись,", {"t":"чтобы", "accent":True}, {"t":"не потерять","accent":True}]
        cap=s.get("caption")
        caph=f'<div class="cap" style="margin-top:40px;font-size:34px">{cap}</div>' if cap else ""
        nk=f'<div style="margin-top:56px;font-weight:600;font-size:44px;letter-spacing:-.02em">{nick_of(s)}</div>' if nick_of(s) else ""
        inner=f'<div class="mid">{kicker}{hero_html(hero,128)}{caph}{nk}</div>'
    else:
        raise ValueError(f"Неизвестный layout: {layout}")

    # фон-картинка для типографских макетов: "bg": путь к файлу Higgsfield | "placeholder"
    if layout in ("poster","stat","insight","quote","list","compare","formula","cta") and s.get("bg"):
        if s["bg"]=="placeholder":
            inner=placeholder_bg(s)+inner
        else:
            img=prep_image(s["bg"], out_assets)
            if img is None:
                print(f"🔴 ABORT: слайд {s['n']} — фон не найден: «{s['bg']}»"); sys.exit(1)
            inner=f'<div class="photo" style="background-image:url(\'{img}\')"></div><div class="scrim"></div>'+inner
            light=True

    cls=f"slide t-{theme}"+(" light" if light else "")
    logo="black" if theme in ("green","white") and not light else "white"
    ar='<div class="arrow">&#8594;</div>' if arrow and layout!="cta" else ""
    nick=f'<div class="nick">{nick_of(s)}</div>' if nick_of(s) and layout!="cta" else ""   # на CTA ник крупно в блоке (правило 6)
    return (f'<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">{FONT_LINKS}<style>{BASE_CSS}</style></head>'
            f'<body><div class="{cls}">{inner}{top_chrome(counter,logo)}{ar}{nick}</div></body></html>')

# --- БАГ 7 (фикс): возрастающие EXIF-даты, чтобы iPhone сохранил порядок карусели ---
def stamp_exif_order(out_dir):
    """iPhone сортирует слайды карусели по EXIF дате съёмки, не по имени.
    Прописываем 01 раньше → NN позже. Если exiftool не установлен — мягкое предупреждение."""
    if not shutil.which("exiftool"):
        print("⚠ exiftool не установлен — порядок на iPhone может сбиться. Установить: brew install exiftool")
        return
    images=sorted([p for p in out_dir.iterdir() if p.suffix.lower() in (".jpg",".jpeg",".png")])
    base=datetime.datetime(2024,1,1,12,0,0)
    for i,p in enumerate(images):
        dt=(base+datetime.timedelta(minutes=i)).strftime("%Y:%m:%d %H:%M:%S")
        subprocess.run(["exiftool","-overwrite_original","-q","-q",
                        f"-AllDates={dt}", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"✓ EXIF-даты проставлены (порядок для iPhone, {len(images)} файлов)")

# --- main ---
def _parse_argv():
    """Принимает: <slides.json> <output_dir>  ИЛИ  <slides.json> --outdir <output_dir>.
    Второй вариант — на случай, если агент запускает по привычке через флаг."""
    args = [a for a in sys.argv[1:] if a]
    if len(args) < 2:
        print("Usage: python3 render.py <slides.json> <output_dir>"); sys.exit(1)
    slides_path = args[0]
    outdir = None
    for i, a in enumerate(args[1:], 1):
        if a == "--outdir":
            if i+1 < len(args):
                outdir = args[i+1]; break
            print("ERR: --outdir без значения"); sys.exit(1)
        if not a.startswith("--"):
            outdir = a; break
    if not outdir or outdir.startswith("--"):
        print(f"ERR: не резолвится output_dir из argv={sys.argv[1:]}"); sys.exit(1)
    p = Path(outdir).expanduser().resolve()
    return slides_path, p

async def main():
    global DEFAULT_NICK
    slides_path, out_dir = _parse_argv()
    spec=json.loads(Path(slides_path).read_text(encoding="utf-8"))
    DEFAULT_NICK=spec.get("nick") or load_nickname()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_assets=out_dir/"черновики"/"_assets"
    photos_dir=Path(spec.get("photos_dir") or PHOTOS_DIR_DEFAULT)
    if not photos_dir.is_absolute(): photos_dir=(SKILL/photos_dir)
    slides=spec["slides"]; total=spec.get("total", len(slides))
    if len(slides)>10:
        print(f"🔴 ABORT: {len(slides)} слайдов — лимит 10 (правило 1)"); sys.exit(1)
    lint_copy(slides)
    greens=[s["n"] for s in slides if s.get("theme")=="green" or (s["layout"]=="cta" and not s.get("theme"))]
    if len(greens)>2:
        print(f"⚠ зелёная заливка на слайдах {greens} — дизайн-код: не чаще 1–2 раз на карусель")
    chrome=spec.get("chrome",{})
    used=set()
    # БАГ 12: usage-log между каруселями — исключаем последние N использованных
    # фото, чтобы лента Instagram не выглядела монотонной.
    recent_photos=load_usage_log(photos_dir)
    if recent_photos:
        print(f"📸 usage-log: избегаю последние {len(recent_photos)} фото из прошлых каруселей")
    recent_videos=load_video_usage()
    if recent_videos:
        print(f"🎬 video usage-log: избегаю последние {len(recent_videos)} клипов из прошлых каруселей")

    # БАГ 10: обязательное 1 видео на карусель (формат A/C) — если модель забыла, подставим
    if spec.get("format","A") in ("A","C"):
        ensure_one_video(slides)

    # БАГ 12: детекция соседних слайдов с одинаковым hero-текстом (дубликат = брак)
    def _hero_text(s):
        h=s.get("hero") or s.get("title") or []
        if isinstance(h,str): return h.strip()
        parts=[]
        for p in (h if isinstance(h,list) else [h]):
            parts.append(p["t"] if isinstance(p,dict) else str(p))
        return " ".join(parts).strip()
    for i in range(len(slides)-1):
        a,b=slides[i],slides[i+1]
        if a["layout"]=="cta" or b["layout"]=="cta": continue
        ha,hb=_hero_text(a),_hero_text(b)
        if ha and hb and ha==hb:
            print(f"🔴 ДУБЛИКАТ: слайды {a['n']} ({a['layout']}) и {b['n']} ({b['layout']}) имеют одинаковый hero: «{ha[:60]}»")
            print(f"   Это баг: video-bg не должен копировать текст соседа. Проверь slides.json.")

    # БАГ 11: чистка «AI · дата» кикеров на обложках (правило 31 SKILL.md)
    # Оставляем: тематические ярлыки. Убираем: паттерны типа "AI · 8 июля 2026", "AI · дата".
    KICKER_JUNK = re.compile(r"^(AI|тренд|разбор)\s*[·•\-—]\s*\d.*(20\d{2}|январ|феврал|март|апрел|мая|июн|июл|август|сентябр|октябр|ноябр|декабр)", re.I)
    for s in slides:
        k=s.get("kicker")
        if k and s["layout"] in ("cover-photo","cover-visual") and KICKER_JUNK.match(k):
            print(f"✂ убран мусорный kicker «{k}» со слайда {s['n']} (правило 10)")
            s["kicker"]=None
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await b.new_page(viewport={"width":1080,"height":1350}, device_scale_factor=1)
        # БАГ 9: формат вывода — JPEG q=88 по умолчанию (5-10× меньше PNG, Instagram
        # всё равно перекодирует в JPEG; влезает в 1 запрос автопостинга < 4MB).
        # Чтобы PNG — `"output_format":"png"` в slides.json.
        fmt=spec.get("output_format","jpeg").lower()
        ext="jpg" if fmt=="jpeg" else "png"
        screenshot_kw={"type":"jpeg","quality":88} if fmt=="jpeg" else {"type":"png"}
        for s in slides:
            if s["layout"]=="video-bg":
                if await render_video_bg_slide(s, total, out_dir, pg): continue
                # клипа нет → тот же текст статикой (cover-visual с заглушкой-градиентом)
                s=dict(s, layout="cover-visual", object=None,
                       hero=s.get("hero") or s.get("title") or [])
            if s["layout"]=="video-clip":
                print(f"🔴 ЗАПРЕЩЁН: layout 'video-clip' (слайд {s['n']}). Голое видео без текста = потерянный слайд.")
                print(f"   Используй layout 'video-bg' с уникальным текстом. См. SKILL.md правило 17.")
                sys.exit(1)
            for k,v in chrome.items():           # дефолты хрома на уровень карусели
                s.setdefault(k, v)
            html=build_slide(s, total, out_assets, photos_dir, used, recent_photos)
            outname=f'{s["n"]:02d}_{s.get("slug",s["layout"])}.{ext}'
            await pg.set_content(html, wait_until="networkidle")
            await assert_font(pg)
            for msg in await pg.evaluate(FIT_JS): print(f"  слайд {s['n']}: {msg}")
            await pg.screenshot(path=str(out_dir/outname), **screenshot_kw)
            print(f"✓ {outname}")
        await b.close()
    stamp_exif_order(out_dir)   # БАГ 7: порядок iPhone
    # БАГ 12: обновляем usage-log фото — добавляем использованные в этой карусели
    if used:
        new_recent=[f for f in recent_photos if f not in used] + list(used)
        save_usage_log(photos_dir, new_recent)
        print(f"📸 usage-log обновлён: +{len(used)} фото (буфер {min(len(new_recent),60)}/60)")
    # БАГ 13: usage-log для видео — собираем какие клипы реально вошли в карусель
    used_videos=set()
    for s in slides:
        v=s.get("video")
        if s.get("layout")=="video-bg" and v and v!="auto" and Path(v).is_file():
            used_videos.add(Path(v).name)
    if used_videos:
        new_v_recent=[f for f in recent_videos if f not in used_videos] + list(used_videos)
        save_video_usage(new_v_recent)
        print(f"🎬 video usage-log обновлён: +{len(used_videos)} клипов (буфер {min(len(new_v_recent),25)}/25)")
    print("Готово →", out_dir)

if __name__=="__main__":
    asyncio.run(main())
