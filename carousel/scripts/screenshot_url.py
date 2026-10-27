#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
screenshot_url.py — URL → чистый скриншот для layout `source` карусели.

Главная задача: убить cookie/consent/paywall попапы, чтобы скрин был пригоден.
Эталон: размер 1280×900, формат PNG. Используется в layout `source` (slides.json).

Запуск:
    "<venv>/bin/python" screenshot_url.py <URL> <output.png> [--width 1280] [--height 900]
    "<venv>/bin/python" screenshot_url.py <URL> <output.png> --validate
    "<venv>/bin/python" screenshot_url.py <URL> <output.png> --validate --max-retries 3

Флаги:
    --validate       после скриншота проверить на оверлеи/затемнение, ретраить при проблемах
    --max-retries N  макс попыток при --validate (default: 3)
    --json-report F  записать результат валидации в JSON-файл (для batch-режима)

Зависимости: playwright (python из config/settings.yml → env.python_with_playwright).
"""
import sys, asyncio, argparse, re, json, os
from pathlib import Path
from playwright.async_api import async_playwright

# Хост-домены consent-провайдеров (блокируем сетевые запросы к ним = попап не загрузится)
BLOCK_HOSTS = [
    r"onetrust", r"cookielaw", r"cookiebot", r"trustarc",
    r"didomi", r"quantcast", r"usercentrics", r"sourcepoint",
    r"consensu\.org", r"privacy-mgmt", r"truste",
    r"googletagmanager.*consent", r"iubenda",
    r"cc\.cdn\.civiccomputing", r"termly\.io", r"securiti\.ai",
    r"osano\.com", r"complianz", r"moove",
]
BLOCK_RE = re.compile("|".join(BLOCK_HOSTS), re.I)

# Селекторы попапов/баннеров (удаляем через JS после загрузки)
# ⚠ Обновление 2026-07-10: расширено под типовые издания — Substack, Reddit, крупные СМИ.
KILL_SELECTORS = [
    # === Cookie / consent (универсально) ===
    "[id*='cookie' i]", "[class*='cookie' i]",
    "[id*='consent' i]", "[class*='consent' i]",
    "[id*='gdpr' i]", "[class*='gdpr' i]",
    "[id*='banner' i][class*='cookie' i]",
    "[role='dialog']", "[role='alertdialog']",
    "#onetrust-consent-sdk", "#onetrust-banner-sdk",
    "[data-testid*='cookie' i]", "[data-testid*='consent' i]",
    ".cmp-container", ".cmp__container",
    "[class*='privacy' i][class*='banner' i]",

    # === Paywall / subscribe walls ===
    "[class*='Subscribe' i][class*='wall' i]",
    "[class*='paywall' i]",
    "[class*='overlay' i][class*='modal' i]",
    "[id*='modal' i][style*='fixed']",

    # === Substack (Latent Space, Every, One Useful Thing) ===
    ".subscribe-widget", ".subscribe-widget-form",
    ".tp-container", ".tp-modal", ".tp-close",
    "[class*='freeSubscribePrompt']",
    "[class*='subscribePrompt']",
    "[aria-label*='Subscribe' i]",

    # === Reddit (old + new) ===
    ".infobar", ".header-bottom-right .login-form",
    "[class*='CookiesInformation']",
    "shreddit-async-loader[bundlename='snoo_action_bar_login_prompt']",
    "faceplate-tracker[noun='email_collection']",
    ".old-reddit-cookie-consent",

    # === Крупные СМИ (Telegraph, Reuters, NYT, FT) ===
    "[data-testid*='sn-onboarding' i]",  # NYT
    "[class*='newsletter-signup' i]",
    "[class*='register-wall' i]",
    "[class*='meter-wall' i]",
    "#hp-app-messaging-toolkit",  # WSJ

    # === Twitter/X ===
    "[data-testid='sheetDialog']",
    "[data-testid='LoginForm_Login_Button']",
    "[aria-label='Sign in' i][role='button']",

    # === LinkedIn (обычно нельзя пройти без логина, но убираем модалку) ===
    ".artdeco-modal-overlay",
    ".modal__overlay--login",
]

# Селекторы кнопок «Accept / Принять / Agree» — кликаем ПЕРЕД удалением
ACCEPT_SELECTORS = [
    "button[id*='accept' i]",
    "button[class*='accept' i]",
    "button[data-testid*='accept' i]",
    "a[id*='accept' i]",
    "[class*='cookie' i] button:first-of-type",
    "[id*='consent' i] button:first-of-type",
    "button:has-text('Accept')",
    "button:has-text('Accept all')",
    "button:has-text('Accept All')",
    "button:has-text('Agree')",
    "button:has-text('I agree')",
    "button:has-text('Allow')",
    "button:has-text('Allow all')",
    "button:has-text('OK')",
    "button:has-text('Got it')",
    "button:has-text('Принять')",
    "button:has-text('Согласен')",
    "button:has-text('Понятно')",
    "button:has-text('Continue')",
    "button:has-text('Dismiss')",
    "button:has-text('Close')",
]

KILL_JS = """
() => {
  const sels = %s;
  // 1) Удалить элементы попапов
  sels.forEach(s => {
    try { document.querySelectorAll(s).forEach(el => el.remove()); } catch(e) {}
  });
  // 2) Снять любые fixed/sticky overlay, перекрывающие контент
  document.querySelectorAll('*').forEach(el => {
    const cs = getComputedStyle(el);
    if ((cs.position==='fixed' || cs.position==='sticky') && el.offsetHeight > 80) {
      const rect = el.getBoundingClientRect();
      if (rect.width >= window.innerWidth*0.5) el.remove();
    }
  });
  // 3) Разблокировать прокрутку (попапы часто ставят overflow:hidden на body)
  document.documentElement.style.overflow='auto';
  document.body.style.overflow='auto';
  document.body.style.position='static';
}
""" % repr(KILL_SELECTORS)

# JS для валидации: проверяем наличие оверлеев и затемнения ПЕРЕД скриншотом
VALIDATE_JS = """
() => {
  const issues = [];

  // 1) Остались ли fixed/sticky элементы шириной >50% экрана?
  let fixedCount = 0;
  document.querySelectorAll('*').forEach(el => {
    const cs = getComputedStyle(el);
    if ((cs.position === 'fixed' || cs.position === 'sticky') && el.offsetHeight > 80) {
      const rect = el.getBoundingClientRect();
      if (rect.width >= window.innerWidth * 0.5) {
        fixedCount++;
      }
    }
  });
  if (fixedCount > 0) issues.push(`fixed_overlays:${fixedCount}`);

  // 2) Есть ли полупрозрачный backdrop (часто z-index 9999+)?
  let backdropCount = 0;
  document.querySelectorAll('*').forEach(el => {
    const cs = getComputedStyle(el);
    const zi = parseInt(cs.zIndex) || 0;
    if (zi > 999 && cs.position === 'fixed') {
      const bg = cs.backgroundColor;
      const match = bg.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([\\d.]+))?\\)/);
      if (match && match[4] && parseFloat(match[4]) > 0.2 && parseFloat(match[4]) < 1) {
        backdropCount++;
      }
    }
  });
  if (backdropCount > 0) issues.push(`backdrop_overlays:${backdropCount}`);

  // 3) body всё ещё overflow:hidden? (скорее всего от попапа)
  const bodyOverflow = getComputedStyle(document.body).overflow;
  const htmlOverflow = getComputedStyle(document.documentElement).overflow;
  if (bodyOverflow === 'hidden' || htmlOverflow === 'hidden') {
    issues.push('body_overflow_hidden');
  }

  // 4) Есть ли диалоги [role=dialog] / [role=alertdialog]?
  const dialogs = document.querySelectorAll('[role="dialog"]:not([aria-hidden="true"]), [role="alertdialog"]:not([aria-hidden="true"])');
  if (dialogs.length > 0) issues.push(`dialogs:${dialogs.length}`);

  return { clean: issues.length === 0, issues };
}
"""

# Пиксельная валидация: анализ затемнения через canvas
PIXEL_VALIDATE_JS = """
async () => {
  // Рендерим viewport в canvas и проверяем % тёмных пикселей
  // Оверлей = много полупрозрачных тёмных пикселей
  const w = window.innerWidth;
  const h = window.innerHeight;

  // Проверяем центральную область (overlay обычно закрывает центр)
  const centerX = Math.floor(w * 0.25);
  const centerY = Math.floor(h * 0.25);
  const centerW = Math.floor(w * 0.5);
  const centerH = Math.floor(h * 0.5);

  // Считаем элементы с opacity < 1 и высоким z-index в центре
  let suspiciousElements = 0;
  const centerRect = { left: centerX, top: centerY, right: centerX + centerW, bottom: centerY + centerH };
  document.querySelectorAll('*').forEach(el => {
    const cs = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    const zi = parseInt(cs.zIndex) || 0;
    if (zi > 100 && cs.position === 'fixed' &&
        rect.left < centerRect.right && rect.right > centerRect.left &&
        rect.top < centerRect.bottom && rect.bottom > centerRect.top &&
        rect.width > w * 0.3 && rect.height > h * 0.3) {
      suspiciousElements++;
    }
  });

  return { suspiciousElements, viewportWidth: w, viewportHeight: h };
}
"""


async def try_click_accept(page):
    """Стратегия 1: найти и кликнуть кнопку Accept/Agree."""
    clicked = False
    for sel in ACCEPT_SELECTORS:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=500):
                await btn.click(timeout=2000)
                clicked = True
                await page.wait_for_timeout(800)
                break
        except Exception:
            continue
    return clicked


async def run_kill_js(page):
    """Стратегия 2: удалить попапы через JS."""
    try:
        await page.evaluate(KILL_JS)
    except Exception as e:
        print(f"  ⚠ kill_js: {e}")


async def validate_page(page):
    """Проверить страницу на остатки попапов. Возвращает (clean: bool, issues: list)."""
    try:
        result = await page.evaluate(VALIDATE_JS)
        if result["clean"]:
            pixel_result = await page.evaluate(PIXEL_VALIDATE_JS)
            if pixel_result["suspiciousElements"] > 0:
                return False, [f"suspicious_center_elements:{pixel_result['suspiciousElements']}"]
        return result["clean"], result.get("issues", [])
    except Exception as e:
        return True, [f"validate_error:{e}"]


async def take(url, out_path, w, h, validate=False, max_retries=3, json_report=None):
    result = {"url": url, "output": out_path, "status": "unknown", "attempts": 0, "issues": []}

    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(
            viewport={"width": w, "height": h},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            locale="en-US",
        )

        async def route_handler(route, req):
            if BLOCK_RE.search(req.url):
                await route.abort()
            else:
                await route.continue_()
        await ctx.route("**/*", route_handler)

        page = await ctx.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"  ⚠ goto: {e} (продолжаю с тем, что успело загрузиться)")

        # === СТРАТЕГИЯ ОЧИСТКИ (3 попытки с эскалацией) ===
        attempts = 0
        is_clean = False

        for attempt in range(max_retries if validate else 1):
            attempts = attempt + 1
            strategy = ""

            if attempt == 0:
                # Попытка 1: ждём загрузку → click accept → kill JS × 2
                strategy = "click_accept + kill_js"
                await page.wait_for_timeout(2000)
                clicked = await try_click_accept(page)
                if clicked:
                    print(f"  ✓ попытка {attempts}: кликнул Accept")
                    await page.wait_for_timeout(1000)
                await run_kill_js(page)
                await page.wait_for_timeout(500)
                await run_kill_js(page)

            elif attempt == 1:
                # Попытка 2: подождать дольше (ленивые попапы) → агрессивный kill
                strategy = "wait_longer + aggressive_kill"
                await page.wait_for_timeout(3000)
                await try_click_accept(page)
                await page.wait_for_timeout(500)
                await run_kill_js(page)
                await page.wait_for_timeout(500)
                # Агрессивный проход: убить ВСЁ fixed/sticky без проверки ширины
                try:
                    await page.evaluate("""
                    () => {
                      document.querySelectorAll('*').forEach(el => {
                        const cs = getComputedStyle(el);
                        if (cs.position === 'fixed' || cs.position === 'sticky') {
                          const zi = parseInt(cs.zIndex) || 0;
                          if (zi > 10 && el.offsetHeight > 50) el.remove();
                        }
                      });
                      document.documentElement.style.overflow='auto';
                      document.body.style.overflow='auto';
                      document.body.style.position='static';
                    }
                    """)
                except Exception:
                    pass

            elif attempt == 2:
                # Попытка 3: полный reload без route-блокировки consent (некоторые сайты ломаются)
                # + клик accept + kill всего
                strategy = "reload_unblocked + accept + nuke_all"
                await ctx.unroute("**/*")
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    pass
                await page.wait_for_timeout(3000)
                await try_click_accept(page)
                await page.wait_for_timeout(1000)
                await run_kill_js(page)
                await page.wait_for_timeout(500)
                try:
                    await page.evaluate("""
                    () => {
                      document.querySelectorAll('*').forEach(el => {
                        const cs = getComputedStyle(el);
                        if (cs.position === 'fixed' || cs.position === 'sticky') {
                          if (el.offsetHeight > 40) el.remove();
                        }
                      });
                      document.querySelectorAll('[role="dialog"], [role="alertdialog"], [aria-modal="true"]').forEach(el => el.remove());
                      document.documentElement.style.overflow='auto';
                      document.body.style.overflow='auto';
                      document.body.style.position='static';
                    }
                    """)
                except Exception:
                    pass

            if validate:
                is_clean, issues = await validate_page(page)
                result["issues"] = issues
                if is_clean:
                    print(f"  ✓ попытка {attempts} ({strategy}): чисто")
                    break
                else:
                    print(f"  ⚠ попытка {attempts} ({strategy}): проблемы — {issues}")
            else:
                is_clean = True
                break

        # === ПРИНУДИТЕЛЬНО в самый верх страницы ===
        # 🔴 Правило 2026-07-10: слайд-источник должен показывать ЛОГОТИП издания + ЗАГОЛОВОК статьи
        # (это и есть пруф «я реально читал материал»). Без scroll(0,0) страница могла уехать
        # вниз после kill_overlays / scrollIntoView, и viewport забирал середину статьи без хедера.
        try:
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(600)
        except Exception:
            pass

        # === СКРИНШОТ ===
        await page.screenshot(path=out_path, full_page=False)

        # === ВАЛИДАЦИЯ: «пустой скрин» (>60% одного цвета = SPA не загрузился) ===
        blank_detected = await _check_blank_screenshot(out_path)
        if blank_detected:
            print(f"  ⚠ скрин пустой (>60% одного цвета). Пробую прокрутить к контенту и переснять...")
            # 🔴 Аккуратно: небольшой доскролл вниз (не 400+ сразу), чтобы не потерять заголовок.
            # Многие SPA (Substack) держат верх пустым до гидрации — короткий скролл на 200px
            # + повторный wait обычно даёт первый экран с уже отрисованным заголовком.
            for scroll_attempt in range(3):
                scroll_px = 200 * (scroll_attempt + 1)  # 200, 400, 600
                try:
                    await page.evaluate(f"window.scrollTo(0, {scroll_px})")
                    await page.wait_for_timeout(1500)
                    # После доскролла возвращаемся в 0 — чтобы viewport снова забрал верх.
                    await page.evaluate("window.scrollTo(0, 0)")
                    await page.wait_for_timeout(500)
                    await page.screenshot(path=out_path, full_page=False)
                    if not await _check_blank_screenshot(out_path):
                        print(f"  ✓ триггер гидрации ({scroll_px}px и назад в 0) помог — скрин ОК")
                        blank_detected = False
                        break
                except Exception:
                    pass
            if blank_detected:
                result["issues"].append("blank_screenshot")
                result["status"] = "warning"
                print(f"  ⚠ скрин по-прежнему пустой после прокрутки. Проверить вручную!")

        await b.close()

    result["attempts"] = attempts
    if validate:
        result["status"] = "clean" if is_clean else "warning"
    else:
        result["status"] = "no_validation"

    # Вывод
    status_icon = "✓" if result["status"] == "clean" else ("⚠" if result["status"] == "warning" else "—")
    print(f"{status_icon} {out_path} [{result['status']}, {attempts} попыток]")
    if result["status"] == "warning":
        print(f"  ⚠ ВНИМАНИЕ: скриншот может содержать оверлей. Проверить вручную!")
        print(f"  Проблемы: {result['issues']}")

    # Реминдер печатается из main() через _print_review_reminder()
    # — единая точка для playwright-пути и GitHub OG-card пути.

    # JSON-отчёт (для batch)
    if json_report:
        report_path = Path(json_report)
        existing = []
        if report_path.exists():
            try:
                existing = json.loads(report_path.read_text())
            except Exception:
                existing = []
        existing.append(result)
        report_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

    return result


async def _check_blank_screenshot(path, threshold=0.60):
    """Проверяет PNG/JPG — если >threshold пикселей одного цвета (белый/кремовый/серый), считаем пустым.
    Работает без PIL — читаем raw bytes через subprocess (sips на macOS)."""
    try:
        import subprocess as sp
        r = sp.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
                   capture_output=True, text=True, timeout=5)
        lines = r.stdout.strip().split("\n")
        w = int([l for l in lines if "pixelWidth" in l][0].split(":")[-1].strip())
        h = int([l for l in lines if "pixelHeight" in l][0].split(":")[-1].strip())
        total = w * h
        if total == 0:
            return True
        # Конвертируем в raw bitmap и считаем доминирующий цвет
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp:
            tmp_path = tmp.name
        sp.run(["sips", "-s", "format", "bmp", str(path), "--out", tmp_path],
               capture_output=True, timeout=10)
        with open(tmp_path, "rb") as f:
            data = f.read()
        os.unlink(tmp_path)
        # BMP pixel data starts at offset in header (bytes 10-13)
        if len(data) < 54:
            return False
        offset = int.from_bytes(data[10:14], "little")
        pixels = data[offset:]
        # Sample every 100th pixel (RGB), count near-white (R>240, G>240, B>240)
        near_white = 0
        sampled = 0
        step = 300  # 3 bytes per pixel * 100
        for i in range(0, len(pixels) - 2, step):
            b_val, g_val, r_val = pixels[i], pixels[i+1], pixels[i+2]
            sampled += 1
            if r_val > 235 and g_val > 235 and b_val > 235:
                near_white += 1
        if sampled == 0:
            return False
        ratio = near_white / sampled
        if ratio > threshold:
            return True
        return False
    except Exception as e:
        print(f"  ⚠ blank-check error: {e}")
        return False


# ── 🔴 Special-source shortcuts (правило 2026-07-09) ─────────────────
# Для доменов, где обычный playwright-скрин снимает футер вместо контента
# (SPA-ленивая загрузка, пейволл), сразу берём готовый чистый пруф.
# GitHub-репо → OG-карточка (1200×600, всегда с автором/★/описанием).
# HN-обсуждение → чистый HTML без SPA.
_GITHUB_REPO_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/#?]+)/?$", re.I)


def _try_special_source(url, output):
    """Возвращает result-dict если URL особый — обошли playwright. Иначе None."""
    import urllib.request as _u
    m = _GITHUB_REPO_RE.match(url)
    if m:
        owner, repo = m.group(1), m.group(2).rstrip("/")
        og = f"https://opengraph.githubassets.com/1/{owner}/{repo}"
        try:
            with _u.urlopen(og, timeout=20) as r:
                data = r.read()
            os.makedirs(os.path.dirname(os.path.abspath(output)) or ".", exist_ok=True)
            with open(output, "wb") as f:
                f.write(data)
            print(f"✓ special-source: GitHub OG-card {owner}/{repo} → {output} ({len(data)//1024} KB)")
            return {"status": "clean", "source_type": "github_og", "url": url, "output": output}
        except Exception as e:
            print(f"⚠ GitHub OG fallback failed: {e} — падаю обратно на playwright")
            return None
    # HN item — снимается идеально playwright'ом, никакого фолбэка не надо.
    return None


def main():
    ap = argparse.ArgumentParser(description="URL → чистый скриншот (без cookies/popups)")
    ap.add_argument("url")
    ap.add_argument("output")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--validate", action="store_true",
                    help="проверить скриншот на оверлеи и ретраить при проблемах")
    ap.add_argument("--max-retries", type=int, default=3,
                    help="макс попыток при --validate (default: 3)")
    ap.add_argument("--json-report", type=str, default=None,
                    help="путь к JSON-файлу отчёта (для batch-режима)")
    ap.add_argument("--no-special-source", action="store_true",
                    help="отключить авто-фолбэк на OG-карточку GitHub и т.п.")
    args = ap.parse_args()

    # 🔴 Special-source shortcut ДО playwright — GitHub всегда через OG.
    if not args.no_special_source:
        special = _try_special_source(args.url, args.output)
        if special is not None:
            if args.json_report:
                with open(args.json_report, "w") as f:
                    json.dump(special, f, ensure_ascii=False, indent=2)
            _print_review_reminder(args.output)
            return

    result = asyncio.run(take(
        args.url, args.output, args.width, args.height,
        validate=args.validate,
        max_retries=args.max_retries,
        json_report=args.json_report,
    ))

    _print_review_reminder(args.output)

    if result["status"] == "warning":
        sys.exit(2)


def _print_review_reminder(path):
    """🔴 РЕМИНДЕР 2026-07-10 (правило в момент действия, не в SKILL.md).
    Печатается в stdout после каждого скриншота — GitHub OG-card и обычные.
    Задача — напомнить проверить скрин глазами перед рендером карусели.
    Правило было текстом в SKILL.md — модель часто пропускала. Теперь оно в момент действия.
    """
    print("")
    print("  ⚠  ОТКРОЙ ФАЙЛ ЧЕРЕЗ Read ПЕРЕД РЕНДЕРОМ КАРУСЕЛИ.")
    print(f"     → {path}")
    print("     Признак правильного скрина (виден 2+ из 3):")
    print("       1. Логотип издания/сайта (Latent Space, EL PAIS, GitHub OG-card, HN)")
    print("       2. Заголовок статьи или название репо")
    print("       3. Автор или подзаголовок")
    print("     Ни один не виден = скрин с середины/футера, брак → переснять.")


if __name__ == "__main__":
    main()
