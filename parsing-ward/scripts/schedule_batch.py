#!/usr/bin/env python3
"""Планирую пачку каруселей в Instagram через Zernio и отмечаю «Post Insta = Опубликован» в Teable.

Использование:
  python3 schedule_batch.py schedule.json

schedule.json — список строк «Единиц контента» и времени публикации (UTC, ISO):
  [
    {"rec_id": "recXXXXXXXXXXXXXXX", "unit_id": 20261027001, "when": "2026-10-28T16:00:00.000Z"},
    {"rec_id": "recYYYYYYYYYYYYYYY", "unit_id": 20261027002, "when": "2026-10-29T16:00:00.000Z"}
  ]
Медиа берётся из локальной папки в поле «Drive папка» юнита (файлы 01_*.jpg/mp4 …),
подпись — из поля «Подпись к карусели».

Настройки: config/settings.yml → zernio.instagram_account_id, teable.*, schedule.timezone.
Ключи: Teable — config/secrets.yml или env TEABLE_API_TOKEN;
       Zernio — env ZERNIO_API_KEY или ../../zernio-posting/config/secrets.yml.
"""
import os, sys, json, subprocess, datetime, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from teable import CFG, T, BASE, TOKEN, require_config, is_placeholder

# 🔴 Ключ не в коде: env ZERNIO_API_KEY → иначе zernio-posting/config/secrets.yml (соседний скилл)
def _zernio_key():
    k = os.environ.get("ZERNIO_API_KEY")
    if k:
        return k
    sec = os.path.join(HERE, "..", "..", "zernio-posting", "config", "secrets.yml")
    try:
        for line in open(sec, encoding="utf-8"):
            if line.strip().startswith("zernio_api_key:"):
                return line.split(":", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    raise SystemExit("Нет ключа Zernio: задай ZERNIO_API_KEY или заполни zernio-posting/config/secrets.yml")

if len(sys.argv) < 2:
    raise SystemExit(__doc__)
require_config()
ZCFG = CFG.get("zernio", {})
IG_ACCOUNT_ID = ZCFG.get("instagram_account_id")
if is_placeholder(IG_ACCOUNT_ID):
    raise SystemExit("Не настроен zernio.instagram_account_id в config/settings.yml (заглушка {{ZERNIO_ACCOUNT_ID_INSTAGRAM}})")
ZERNIO_API = ZCFG.get("api_url") or "https://zernio.com/api/v1"
ZERNIO_KEY = _zernio_key()
TEABLE_TOKEN = TOKEN
UNITS_TABLE = T["content_units"]
TZ = CFG.get("schedule", {}).get("timezone", "UTC")
SCHEDULE = [(x["rec_id"], x["unit_id"], x["when"]) for x in json.load(open(sys.argv[1], encoding="utf-8"))]

def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def compress_video(path):
    """Сжимает mp4 in-place через ffmpeg, CRF 32, без аудио. Бэкап в черновики/."""
    size = os.path.getsize(path)
    if size <= 4 * 1024 * 1024:
        return
    folder = os.path.dirname(path)
    drafts = os.path.join(folder, "черновики")
    os.makedirs(drafts, exist_ok=True)
    backup = os.path.join(drafts, "_orig_" + os.path.basename(path))
    if not os.path.exists(backup):
        os.rename(path, backup)
    else:
        os.remove(path)
    r = sh(["ffmpeg","-y","-i",backup,"-c:v","libx264","-preset","slow","-crf","32","-an",
            "-movflags","+faststart","-vf","scale=1080:1350",path])
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr[:300]}")

def get_teable_unit(rec_id):
    r = sh(["curl","-sS",f"{BASE}/table/{UNITS_TABLE}/record/{rec_id}?fieldKeyType=name",
            "-H", f"Authorization: Bearer {TEABLE_TOKEN}"])
    return json.loads(r.stdout).get("fields", {})

def presign(filename, content_type):
    r = sh(["curl","-sS","--max-time","30","-X","POST",f"{ZERNIO_API}/media/presign",
            "-H", f"Authorization: Bearer {ZERNIO_KEY}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"filename":filename,"contentType":content_type})])
    return json.loads(r.stdout)

def put_file(url, path, content_type):
    r = sh(["curl","-sS","--max-time","120","-X","PUT","--data-binary",f"@{path}",
            "-H", f"Content-Type: {content_type}", url, "-w","\n%{http_code}"])
    code = r.stdout.strip().split("\n")[-1]
    if code != "200":
        raise RuntimeError(f"PUT {path} → HTTP {code}")

def upload_folder(folder):
    files = sorted([x for x in os.listdir(folder) if x[:2].isdigit() and x.endswith(('.jpg','.mp4'))])
    media_items = []
    for fn in files:
        ext = fn.rsplit('.',1)[-1].lower()
        mime = "image/jpeg" if ext == "jpg" else "video/mp4"
        typ  = "image"      if ext == "jpg" else "video"
        # compress if needed
        path = os.path.join(folder, fn)
        if ext == "mp4" and os.path.getsize(path) > 4*1024*1024:
            compress_video(path)
        p = presign(fn, mime)
        put_file(p["uploadUrl"], path, mime)
        media_items.append({"type":typ,"url":p["publicUrl"]})
    return media_items

def create_post(caption, media_items, scheduled_for, idem_key):
    payload = {
        "content": caption,
        "mediaItems": media_items,
        "platforms": [{"platform":"instagram","accountId":IG_ACCOUNT_ID,"scheduledFor":scheduled_for}],
        "scheduledFor": scheduled_for,
        "timezone": TZ,
    }
    r = sh(["curl","-sS","--max-time","90","-X","POST",f"{ZERNIO_API}/posts",
            "-H", f"Authorization: Bearer {ZERNIO_KEY}",
            "-H", "Content-Type: application/json",
            "-H", f"X-Request-Id: {idem_key}",
            "-d", json.dumps(payload)])
    return json.loads(r.stdout)

def patch_teable_published(rec_id):
    r = sh(["curl","-sS","-X","PATCH",
            f"{BASE}/table/{UNITS_TABLE}/record/{rec_id}?fieldKeyType=name",
            "-H", f"Authorization: Bearer {TEABLE_TOKEN}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"record":{"fields":{"Post Insta":"Опубликован"}}})])
    return r.returncode == 0

for rec_id, unit_id, when in SCHEDULE:
    fields = get_teable_unit(rec_id)
    folder = fields.get("Drive папка")
    if not folder or not os.path.isdir(folder):
        print(f"\n=== {unit_id}: ⚠ локальная папка медиа не найдена ({folder}) — пропускаю")
        continue
    caption = fields.get("Подпись к карусели") or ""
    title = (fields.get("Заголовок (RU)") or "")[:70]
    print(f"\n=== {unit_id} · {when} ===")
    print(f"    {title}")
    try:
        media_items = upload_folder(folder)
        print(f"    ✓ upload: {len(media_items)} files")
        idem = f"schedule-{unit_id}-v1"
        resp = create_post(caption, media_items, when, idem)
        post_id = resp.get("post",{}).get("_id") or resp.get("existingPostId") or ""
        if resp.get("error"):
            print(f"    ⚠ create: {resp.get('error')} — existing={resp.get('details',{}).get('existingPostId')}")
        else:
            print(f"    ✓ scheduled: {post_id}")
        if patch_teable_published(rec_id):
            print(f"    ✓ Teable: Post Insta = «Опубликован»")
    except Exception as e:
        print(f"    ✗ FAIL: {e}")
