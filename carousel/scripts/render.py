#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render.py — ЕДИНЫЙ рендер-движок скилла carousel (чистовик v1, 2026-06-02; адаптация Ward).

Заменяет «модель пишет Python каждый раз». Модель готовит slides.json — этот скрипт рендерит.
Все правила дизайн-системы зашиты ЗДЕСЬ (источник: knowledge/slide_layouts.md):
  • один шрифт Inter, единый оранжевый #E85A2C (не красный)
  • объект/фото — edge-to-edge, объект сливается с кремом (НЕ плашка)
  • line-height ≥1.05, зазор заголовок→body ≥32px, мин. размеры шрифтов
  • сетка по умолчанию ВЫКЛ (чистый крем); счётчик/ник/опц. закладка-стрелка
  • CTA (слайд 10) — финальный слайд «Подпишись, чтобы не потерять» (layout "cta"),
    верстается движком, текст — materials/финальный_слайд.md
  • пустые медиа-папки (фото автора, видео-фоны) — НЕ падение, а предупреждение + фолбэк

Запуск (через venv с playwright):
    python3 render.py <slides.json> <output_dir>

Схема slides.json и каталог макетов: knowledge/slide_layouts.md
"""
import sys, json, base64, asyncio, random, subprocess, shutil, unicodedata, os, datetime, re
from pathlib import Path
from playwright.async_api import async_playwright

# --- пути ---
SKILL = Path(__file__).resolve().parent.parent
INTER = SKILL / "materials/шрифты/Inter/Inter.ttf"
PHOTOS_DIR_DEFAULT = SKILL / "materials" / "фото_автора"   # заглушка: см. README.md в папке
SETTINGS = SKILL / "config" / "settings.yml"
IMG_EXT = (".jpg", ".jpeg", ".png")

def load_nickname():
    """Ник аккаунта для слайдов — из config/settings.yml → brand.nickname.
    Без PyYAML: простой regex. Если там ещё заглушка {{...}} — громкое предупреждение."""
    nick = "{{НИК_АККАУНТА}}"
    try:
        m = re.search(r'^\s*nickname:\s*"([^"]+)"', SETTINGS.read_text(encoding="utf-8"), re.M)
        if m: nick = m.group(1)
    except Exception:
        pass
    if "{{" in nick:
        print(f"⚠ ник аккаунта не настроен ({nick}) — впиши его в config/settings.yml → brand.nickname "
              f"(например @ward.cap) или задай \"nick\" в slides.json")
    return nick

DEFAULT_NICK = None   # заполняется в main()

def nick_of(s):
    return s.get("nick") or DEFAULT_NICK or "{{НИК_АККАУНТА}}"

# --- токены дизайн-системы ---
CREAM="#EFEAE0"; BLACK="#1A1A1A"; ORANGE="#E85A2C"; GRAY="#555555"; CHROME="#787878"; GRID="#CFC4A8"; CARD="#0A0A0A"

def b64_file(path, mime):
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()

INTER_B64 = b64_file(INTER, "font/ttf")

# --- BASE CSS (литералы, без f-string) ---
BASE_CSS = """
@font-face { font-family:'Inter'; src:url('__INTER__') format('truetype-variations'); font-weight:100 900; }
* { margin:0; padding:0; box-sizing:border-box; }
html,body { width:1080px; height:1350px; overflow:hidden; font-family:'Inter',sans-serif; }
.slide { position:relative; width:1080px; height:1350px; background:__CREAM__; color:__BLACK__; overflow:hidden; }
.grid { position:absolute; inset:0; opacity:.32; pointer-events:none;
  background:linear-gradient(__GRID__ 1px,transparent 1px) 0 0/40px 40px,
            linear-gradient(90deg,__GRID__ 1px,transparent 1px) 0 0/40px 40px; }
.bookmark { position:absolute; top:0; left:80px; width:46px; height:74px; background:__ORANGE__; z-index:6;
  clip-path:polygon(0 0,100% 0,100% 100%,50% 76%,0 100%); }
.counter { position:absolute; top:48px; left:150px; font-weight:800; font-size:26px; color:__BLACK__; letter-spacing:2px; z-index:6; }
.counter.nobm { left:90px; }
.nick { position:absolute; bottom:64px; left:90px; font-size:26px; font-weight:800; color:__CHROME__; z-index:6; }
.arrow { position:absolute; bottom:60px; right:80px; font-size:54px; color:__ORANGE__; font-weight:700; z-index:6; }
.light .counter { color:#fff; } .light .nick { color:#EBEBEB; }
.kicker { font-weight:800; font-size:24px; letter-spacing:4px; color:__ORANGE__; text-transform:uppercase; }
.hero { font-weight:900; line-height:1.05; letter-spacing:-1.5px; }
.hero .acc { color:__ORANGE__; }
.body { font-weight:600; line-height:1.25; margin-top:36px; }
.cap  { font-weight:500; line-height:1.3; color:__GRAY__; }
.photo { position:absolute; inset:0; background-size:cover; background-position:center; }
.scrim { position:absolute; inset:0; background:linear-gradient(to bottom,rgba(0,0,0,0) 38%,rgba(0,0,0,.82) 100%); }
.stack { position:absolute; left:90px; right:90px; bottom:150px; z-index:4; }
.bullet { display:flex; gap:20px; align-items:baseline; margin-bottom:22px; }
.bullet .dot { color:__ORANGE__; font-size:22px; line-height:1.2; }
.bullet .txt { font-weight:800; font-size:34px; }
.nick.center { left:0; right:0; bottom:auto; top:930px; text-align:center; font-size:44px; color:__BLACK__; }
""".replace("__INTER__",INTER_B64).replace("__CREAM__",CREAM).replace("__BLACK__",BLACK)\
   .replace("__ORANGE__",ORANGE).replace("__GRAY__",GRAY).replace("__CHROME__",CHROME)\
   .replace("__GRID__",GRID)

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
    return f'<div class="hero" style="font-size:{size}px;{col}">' + "<br>".join(out) + "</div>"

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
        for s in slides:
            if s["n"]>mid_n or (s["n"]==mid_n and s is not content[mid_pos]):
                s["n"]+=1
        vid=pick_random_video()
        if vid:
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
VIDEO_OVERLAY_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
/* 🔴 forcing transparent на html/body/.frame — иначе omit_background не сработает */
html, body, .frame { background: transparent !important; }
@font-face { font-family:'Inter'; src:url('__INTER__') format('truetype-variations'); font-weight:100 900; }
body { width:1080px; height:1350px; overflow:hidden; font-family:'Inter',sans-serif; }
.frame { position:relative; width:1080px; height:1350px; }
.scrim { position:absolute; inset:0; background:linear-gradient(to bottom,
  rgba(10,10,10,.58) 0%, rgba(10,10,10,.46) 38%, rgba(10,10,10,.46) 62%, rgba(10,10,10,.9) 100%); }
.counter { position:absolute; top:48px; left:90px; font-weight:800; font-size:26px;
  color:#FFFFFF; letter-spacing:2px; text-shadow:0 2px 14px rgba(0,0,0,.6); }
.nick { position:absolute; bottom:64px; left:90px; font-weight:800; font-size:26px;
  color:#EBEBEB; text-shadow:0 2px 14px rgba(0,0,0,.6); }
.wrap { position:absolute; left:90px; right:90px; bottom:150px; }
.kicker { font-weight:800; font-size:24px; letter-spacing:4px; color:#FF7A45;
  text-transform:uppercase; margin-bottom:22px; text-shadow:0 2px 16px rgba(0,0,0,.5); }
.hero { font-weight:900; font-size:84px; line-height:1.05; letter-spacing:-1.5px;
  color:#FFFFFF; text-shadow:0 4px 30px rgba(0,0,0,.55); }
.hero .acc { color:#FF7A45; }
.body { font-weight:600; font-size:36px; line-height:1.28; color:#EFEAE0;
  margin-top:36px; text-shadow:0 2px 18px rgba(0,0,0,.6); }
""".replace("__INTER__", INTER_B64)

def build_video_overlay_html(s, total):
    """Прозрачный HTML для оверлея на видео-фон. Тот же контент что у photo-overlay,
    но светлый текст + scrim + text-shadow."""
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
    hero_html='<div class="hero">' + "<br>".join(parts) + '</div>'
    body=f'<div class="body">{s["body"]}</div>' if s.get("body") else ""
    return (f'<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">'
            f'<style>{VIDEO_OVERLAY_CSS}</style></head><body>'
            f'<div class="frame"><div class="scrim"></div>'
            f'<div class="counter">{counter}</div>'
            f'<div class="wrap">{kicker}{hero_html}{body}</div>'
            f'<div class="nick">{nick_of(s)}</div></div></body></html>')

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
    await pg.goto(f"file://{html_path}")
    try: await pg.evaluate("document.fonts.ready")
    except Exception: pass
    await pg.wait_for_timeout(500)
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
    bookmark=s.get("bookmark", s.get("_chrome_bookmark", False))
    arrow=s.get("arrow", False)
    grid=s.get("grid", False)
    kicker=f'<div class="kicker">{s["kicker"]}</div>' if s.get("kicker") else ""

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
              f"рендерю без фото (типографика на креме). Положи фото в materials/фото_автора/.")

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
               f'<div class="stack" style="color:#fff">{kicker}{hero_html(s["hero"],96)}</div>')
    elif layout=="photo-overlay":
        light=True
        inner=(f'<div class="photo" style="background-image:url(\'{img}\')"></div><div class="scrim"></div>'
               f'<div class="stack" style="color:#fff">{hero_html(s["title"],76)}'
               f'<div class="body" style="font-size:38px">{s["body"]}</div></div>')
    elif layout in ("cover-visual","object-list"):
        obj=prep_image(s["object"], out_assets) if s.get("object") and s["object"]!="auto" else None
        objdiv=(f'<div style="position:absolute;top:0;left:0;right:0;height:820px;background-image:url(\'{obj}\');'
                f'background-size:cover;background-position:center top"></div>'
                f'<div style="position:absolute;top:0;left:0;right:0;height:880px;'
                f'background:linear-gradient(0deg,{CREAM} 0%,{CREAM} 16%,transparent 46%)"></div>') if obj else ""
        if layout=="cover-visual":
            body=f'<div class="body" style="font-size:36px">{s["body"]}</div>' if s.get("body") else ""
            inner=objdiv+f'<div class="stack">{kicker}{hero_html(s["hero"],84)}{body}</div>'
        else:  # object-list
            bl="".join(f'<div class="bullet"><span class="dot">●</span><span class="txt">{t}</span></div>' for t in s.get("items",[]))
            inner=(objdiv+f'<div style="position:absolute;left:90px;right:90px;top:760px">{kicker}'
                   f'{hero_html(s["hero"],74)}<div style="margin-top:30px">{bl}</div></div>')
    elif layout=="poster":
        cap=f'<div class="cap" style="margin-top:40px;font-size:34px">{s["caption"]}</div>' if s.get("caption") else ""
        inner=(f'<div style="position:absolute;top:50%;left:90px;right:90px;transform:translateY(-50%);text-align:center">'
               f'{hero_html(s["hero"],104)}{cap}</div>')
    elif layout=="stat":
        # БАГ 4 (фикс): авто-размер большой цифры по длине строки, чтобы $965B / 113K не вылезали
        big=str(s["big"]); L=len(big)
        big_sz = 340 if L<=3 else (280 if L==4 else (230 if L==5 else (200 if L==6 else 170)))
        unit=f'<div class="hero" style="font-size:64px;margin-top:10px">{s["unit"]}</div>' if s.get("unit") else ""
        body=f'<div class="body" style="font-size:36px;margin-top:36px;color:{GRAY}">{s["body"]}</div>' if s.get("body") else ""
        inner=(f'<div style="position:absolute;top:50%;left:90px;right:90px;transform:translateY(-50%);text-align:center">'
               f'<div style="font-size:{big_sz}px;font-weight:900;line-height:.9;color:{ORANGE};letter-spacing:-8px;white-space:nowrap;overflow:visible">{big}</div>'
               f'{unit}{body}</div>')
    elif layout=="insight":
        cap=f'<div class="body" style="font-size:36px;margin-top:36px;color:{GRAY}">{s["caption"]}</div>' if s.get("caption") else ""
        inner=(f'<div style="position:absolute;top:50%;left:90px;right:90px;transform:translateY(-50%);text-align:center">'
               f'<div style="font-size:120px;font-weight:900;color:{ORANGE};letter-spacing:-3px">#{s["insight_no"]}</div>'
               f'{hero_html(s["hero"],88)}{cap}</div>')
    elif layout=="quote":
        dark=s.get("dark",False)
        # БАГ 15: кавычки настраиваемые — русские «ёлочки» по умолчанию,
        # англоязычные карусели (EU2Bali/Younis) передают "marks": ["“","”"].
        lq,rq=s.get("marks",["«","»"])
        inner_q=(f'<div style="font-weight:900;font-size:58px;line-height:1.2;color:{"#fff" if dark else BLACK}">{lq}{s["quote"]}{rq}</div>'
                 f'<div class="cap" style="margin-top:34px;font-size:28px;color:{"#888" if dark else GRAY}">— {s["source"]}</div>')
        if dark:
            inner=(f'<div style="position:absolute;top:50%;left:90px;right:90px;transform:translateY(-50%)">'
                   f'<div style="background:{CARD};border-radius:24px;padding:60px 50px;box-shadow:0 20px 60px rgba(232,90,44,.18)">{inner_q}</div></div>')
        else:
            inner=f'<div style="position:absolute;top:50%;left:90px;right:90px;transform:translateY(-50%)">{inner_q}</div>'
    elif layout=="list":
        rows=""
        for i,it in enumerate(s["items"],1):
            lab=it.get("label","") if isinstance(it,dict) else ""
            val=it.get("value",it) if isinstance(it,dict) else it
            num=f'<span style="color:{ORANGE};font-weight:800;font-size:24px">{i:02d}</span>'
            labh=f'<span style="color:#fff;font-weight:800;font-size:30px;min-width:200px">{lab}</span>' if lab else ""
            rows+=(f'<div style="display:flex;gap:22px;align-items:baseline;padding:20px 0;border-bottom:1px solid #2a2a2a">'
                   f'{num}{labh}<span style="color:#aaa;font-weight:500;font-size:26px">{val}</span></div>')
        # БАГ 14: карточка списка центрируется по вертикали — при 3-5 пунктах жёсткий
        # top:160px оставлял треть кадра пустой снизу (вёрстка читалась как обрыв).
        inner=(f'<div style="position:absolute;top:50%;left:90px;right:90px;transform:translateY(-50%)">{kicker}'
               f'{hero_html(s["hero"],66)}'
               f'<div style="margin-top:34px;background:{CARD};border-radius:24px;padding:34px 44px;box-shadow:0 20px 60px rgba(232,90,44,.18)">{rows}</div></div>')
    elif layout=="compare":
        L,R=s["left"],s["right"]
        li="<br>".join("• "+x for x in L["items"]); ri="<br>".join("• "+x for x in R["items"])
        # БАГ 14 (см. list): две колонки тоже центрируем по вертикали.
        inner=(f'<div style="position:absolute;top:50%;left:90px;right:90px;transform:translateY(-50%)">{kicker}{hero_html(s["hero"],64)}'
               f'<div style="display:flex;gap:26px;margin-top:36px">'
               f'<div style="flex:1;background:{CARD};border-radius:22px;padding:32px"><div style="color:{ORANGE};font-weight:900;font-size:30px;margin-bottom:20px">{L["title"]}</div>'
               f'<div style="color:#eee;font-size:26px;line-height:1.5">{li}</div></div>'
               f'<div style="flex:1;background:#fff;border:2px solid {BLACK};border-radius:22px;padding:32px"><div style="color:{BLACK};font-weight:900;font-size:30px;margin-bottom:20px">{R["title"]}</div>'
               f'<div style="color:{BLACK};font-size:26px;line-height:1.5">{ri}</div></div></div></div>')
    elif layout=="formula":
        cap=f'<div class="cap" style="margin-top:40px;font-size:32px">{s["caption"]}</div>' if s.get("caption") else ""
        inner=(f'<div style="position:absolute;top:50%;left:90px;right:90px;transform:translateY(-50%);text-align:center">{kicker}'
               f'<div class="hero" style="font-size:92px;margin-top:14px">{s["top_block"]}</div>'
               f'<div style="height:6px;background:{ORANGE};margin:44px 0"></div>'
               f'<div class="hero" style="font-size:92px;color:{ORANGE}">{s["bottom_block"]}</div>{cap}</div>')
    elif layout=="source":
        # БАГ 5 (фикс): поддержка реального скриншота вместо серых заглушек.
        # Если в JSON есть "screenshot": "path.png" — вставляем его в мокап браузера.
        url=s.get("url","источник"); cap=s.get("caption","")
        # Штамп настраиваемый: русские карусели — «ИСТОЧНИК» (дефолт),
        # англоязычные (Бали/Younis) — "SOURCE" через поле "stamp".
        stamp=s.get("stamp","ИСТОЧНИК")
        shot_path=s.get("screenshot")
        if shot_path:
            shot_b64=prep_image(shot_path, out_assets, maxpx=1400)
            content=(f'<img src="{shot_b64}" style="width:100%;display:block">' if shot_b64
                     else '<div style="padding:60px;color:#888;text-align:center">[скриншот не найден]</div>')
        else:
            content=('<div style="padding:38px"><div style="height:24px;width:62%;background:#3a3a3a;border-radius:6px;margin-bottom:22px"></div>'
                     '<div style="height:16px;width:100%;background:#262626;border-radius:6px;margin-bottom:12px"></div>'
                     '<div style="height:16px;width:88%;background:#262626;border-radius:6px"></div></div>')
        inner=(f'<div style="position:absolute;top:180px;left:90px;right:90px">{kicker}{hero_html(s.get("hero",["Это не выдумка —",{"t":"вот источник","accent":True}]),58)}'
               f'<div style="margin-top:34px;background:{CARD};border-radius:22px;overflow:hidden;box-shadow:0 24px 60px rgba(0,0,0,.2)">'
               f'<div style="background:#1c1c1e;padding:18px 22px;display:flex;gap:10px;align-items:center">'
               f'<span style="width:13px;height:13px;border-radius:50%;background:#ff5f57"></span>'
               f'<span style="width:13px;height:13px;border-radius:50%;background:#febc2e"></span>'
               f'<span style="width:13px;height:13px;border-radius:50%;background:#28c840"></span>'
               f'<span style="color:#888;font-size:19px;margin-left:14px">{url}</span></div>'
               f'{content}</div>'
               f'<div style="display:inline-block;margin-top:26px;background:{ORANGE};color:#fff;font-weight:900;font-size:24px;padding:11px 24px;transform:rotate(-3deg)">{stamp}</div>'
               f'<div class="cap" style="margin-top:20px;font-size:28px">{cap}</div></div>')
    elif layout=="cta":
        # Финальный слайд Ward: «Подпишись, чтобы не потерять» (materials/финальный_слайд.md).
        # Текст можно переопределить полями hero / caption, но по умолчанию — канон.
        hero=s.get("hero") or ["Подпишись,", {"t":"чтобы не потерять","accent":True}]
        cap=s.get("caption")
        caph=f'<div class="cap" style="margin-top:40px;font-size:34px">{cap}</div>' if cap else ""
        inner=(f'<div style="position:absolute;top:420px;left:90px;right:90px;text-align:center">{kicker}'
               f'{hero_html(hero,104)}{caph}</div>')
    else:
        raise ValueError(f"Неизвестный layout: {layout}")

    cls="slide light" if light else "slide"
    gr='<div class="grid"></div>' if grid else ""
    bm='<div class="bookmark"></div>' if bookmark else ""
    cnt_cls="counter" if bookmark else "counter nobm"
    ar='<div class="arrow">&#8594;</div>' if arrow and layout!="cta" else ""
    nick_cls="nick center" if layout=="cta" else "nick"   # на CTA ник по центру крупно (правило 6)
    return (f'<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><style>{BASE_CSS}</style></head>'
            f'<body><div class="{cls}">{gr}{bm}<div class="{cnt_cls}">{counter}</div>{inner}{ar}'
            f'<div class="{nick_cls}">{nick_of(s)}</div></div></body></html>')

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
                # клипа нет → тот же текст статикой (cover-visual без объекта на креме)
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
