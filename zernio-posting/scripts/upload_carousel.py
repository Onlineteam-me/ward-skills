#!/usr/bin/env python3
"""
Carousel uploader for Zernio.

Загружает одну ИЛИ несколько папок с медиа (jpg/mp4) через эндпоинт
https://zernio.com/api/v1/media/upload?token=<TOKEN>

🔴 ВАЖНО (опыт 2026-06-22):
  - Использует multipart POST с явным MIME-типом per file (без MIME → octet-stream → 400).
  - Авто-детект медиа: ищет файлы в `<folder>/out/`, иначе в `<folder>/`.
  - Не палит токен впустую: проверяет наличие медиа ДО POST.
  - Параллельные uploads (до 4 одновременно) через ThreadPoolExecutor.

Использование:
  # Один upload
  ./upload_carousel.py <TOKEN> <FOLDER>

  # Batch через stdin: каждая строка "<name>|<TOKEN>|<FOLDER>"
  cat pairs.txt | ./upload_carousel.py

Возвращает JSON в stdout:
  - single: {"files": [{"url": ..., "filename": ..., "type": ...}, ...]}
  - batch:  {"<name>": {"files": [...]}, ...}

Stderr: прогресс ("  <name>: N files")
"""
import sys, os, json, warnings, concurrent.futures
warnings.filterwarnings('ignore')
import requests  # pip install requests если нет

API = "https://zernio.com/api/v1/media/upload"

def find_media_dir(folder: str):
    """Авто-детект: сначала <folder>/out/, потом <folder>/. Возвращает None если медиа нет."""
    for cand in (os.path.join(folder, 'out'), folder):
        if not os.path.isdir(cand): continue
        media = [f for f in os.listdir(cand) if f.endswith(('.jpg', '.jpeg', '.png', '.mp4'))]
        if media: return cand
    return None

def upload(token: str, folder: str, name: str = ''):
    media_dir = find_media_dir(folder)
    if not media_dir:
        return name, {'error': f'no media found in {folder}'}

    files = []
    fhs = []
    for fname in sorted(os.listdir(media_dir)):
        path = os.path.join(media_dir, fname)
        ext = fname.lower().rsplit('.', 1)[-1]
        mime = {
            'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
            'png': 'image/png', 'mp4': 'video/mp4'
        }.get(ext)
        if not mime: continue
        fh = open(path, 'rb')
        fhs.append(fh)
        files.append(('files', (fname, fh, mime)))

    try:
        r = requests.post(f"{API}?token={token}", files=files, timeout=300)
        result = r.json()
    finally:
        for fh in fhs: fh.close()
    return name, result

def main():
    if len(sys.argv) == 3:
        # Один upload
        token, folder = sys.argv[1], sys.argv[2]
        _, result = upload(token, folder)
        print(json.dumps(result, ensure_ascii=False))
        return

    # Batch через stdin
    pairs = []
    for line in sys.stdin:
        line = line.strip()
        if not line or line.startswith('#'): continue
        parts = line.split('|', 2)
        if len(parts) != 3:
            print(f"  SKIP malformed line: {line[:60]}", file=sys.stderr)
            continue
        pairs.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(upload, t, f, n): n for n, t, f in pairs}
        for fut in concurrent.futures.as_completed(futs):
            name, r = fut.result()
            results[name] = r
            err = r.get('error')
            if err:
                print(f"  {name}: ✗ {err}", file=sys.stderr)
            else:
                print(f"  {name}: {len(r.get('files',[]))} files", file=sys.stderr)

    print(json.dumps(results, ensure_ascii=False))

if __name__ == '__main__':
    main()
