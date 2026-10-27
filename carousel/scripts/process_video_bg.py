#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Батч-обработчик видео-фонов для скилла carousel.

Берёт сырые видео из materials/video_bg/raw/, приводит каждое к формату слайда:
  - cover-кроп под 1080x1350 (4:5) из любого исходного соотношения
  - тримминг до MAX_SEC секунд
  - H.264 high + yuv420p + faststart, БЕЗ аудио (`-an`) — совместимо с IG и
    безопасно для автопостинга (когда система не накладывает музыку — не будет
    случайных слов из исходного клипа)
Кладёт готовые клипы в materials/video_bg/<slug>.mp4
И thumbnail среднего кадра в materials/video_bg/.thumbs/<slug>.jpg (для тегирования).

Запуск:  <venv>/bin/python scripts/process_video_bg.py
"""
import argparse, json, pathlib, re, subprocess, sys

MAX_SEC = 15
W, H = 1080, 1350

SKILL = pathlib.Path(__file__).resolve().parent.parent
RAW = SKILL / "materials" / "video_bg" / "raw"
OUT = SKILL / "materials" / "video_bg"
THUMBS = OUT / ".thumbs"
THUMBS.mkdir(parents=True, exist_ok=True)

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".webm", ".mkv", ".avi"}


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return s or "bg"


def probe_duration(path: pathlib.Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def process(src: pathlib.Path, slug: str):
    dst = OUT / f"{slug}.mp4"
    dur = probe_duration(src)
    t = min(MAX_SEC, dur) if dur else MAX_SEC
    # cover: масштабируем чтобы покрыть кадр, потом центр-кроп
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(src), "-t", f"{t:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-crf", "20",
        "-an", "-movflags", "+faststart",
        str(dst)], check=True, capture_output=True)
    # thumbnail среднего кадра, 540px ширина
    thumb = THUMBS / f"{slug}.jpg"
    subprocess.run([
        "ffmpeg", "-y", "-ss", f"{t/2:.2f}", "-i", str(dst),
        "-vframes", "1", "-vf", "scale=540:-1", str(thumb)],
        check=True, capture_output=True)
    return {"file": dst.name, "thumb": thumb.name, "src_duration": round(dur, 1),
            "clip_duration": round(t, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="макс. новых клипов за запуск (0 = все)")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)   # папка-заглушка может отсутствовать
    raws = sorted(p for p in RAW.iterdir() if p.suffix.lower() in VIDEO_EXT)
    if not raws:
        print(f"Нет видео в {RAW}. Закинь файлы туда и запусти снова.")
        sys.exit(0)

    manifest = OUT / "_processed.json"
    results = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
    done_slugs = {r["slug"] for r in results}
    done_sources = {r["src"] for r in results}

    pending = [p for p in raws if p.name not in done_sources]
    print(f"Всего сырья: {len(raws)} | уже готово: {len(results)} | осталось: {len(pending)}")
    if not pending:
        print("Всё обработано.")
        return

    batch = pending if args.limit <= 0 else pending[:args.limit]
    for src in batch:
        slug = slugify(src.stem)
        n = slug; i = 2
        while n in done_slugs:
            n = f"{slug}_{i}"; i += 1
        done_slugs.add(n)
        print(f"-> {src.name}  →  {n}.mp4")
        rec = process(src, n)
        rec["slug"] = n
        rec["src"] = src.name
        results.append(rec)
        manifest.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    left = len(pending) - len(batch)
    print(f"\nОбработано в этом батче: {len(batch)} | осталось: {left}")
    print("Thumbnails в .thumbs/ — теперь нужно протегировать в video_bg_index.json")


if __name__ == "__main__":
    main()
