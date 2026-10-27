#!/usr/bin/env python3
"""Upload carousel files to Zernio via presign → PUT R2 → complete flow."""

import argparse
import json
import mimetypes
import os
import sys
import time
from pathlib import Path

import requests

BASE = "https://zernio.com/api/v1/media/upload"


def get_token(api_key: str) -> str:
    """Generate upload token via Zernio API."""
    r = requests.post(
        "https://zernio.com/api/v1/media/upload-token",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    r.raise_for_status()
    return r.json()["token"]


def presign(token: str, filename: str, content_type: str, size: int) -> dict:
    """Get presigned upload URL for a file."""
    r = requests.post(
        f"{BASE}/presign",
        params={"token": token},
        json={"filename": filename, "contentType": content_type, "size": size},
    )
    r.raise_for_status()
    return r.json()


def put_file(upload_url: str, file_path: Path, content_type: str) -> int:
    """PUT file to presigned R2 URL. Returns status code."""
    with open(file_path, "rb") as f:
        r = requests.put(
            upload_url,
            data=f,
            headers={"Content-Type": content_type},
        )
    r.raise_for_status()
    return r.status_code


def complete(token: str, uploaded_files: list[dict]) -> dict:
    """Confirm upload completion for all files at once."""
    r = requests.post(
        f"{BASE}/complete",
        params={"token": token},
        json={"files": uploaded_files},
    )
    r.raise_for_status()
    return r.json()


def upload_carousel(token: str, folder: Path) -> list[str]:
    """Upload all media files from folder. Returns list of public URLs in order."""
    files = sorted(
        [f for f in folder.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".mp4")],
        key=lambda f: f.name,
    )

    if not files:
        print(f"  No media files in {folder}")
        return []

    uploaded = []
    urls = []
    for f in files:
        mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        size = f.stat().st_size

        print(f"  {f.name} ({size // 1024}KB) ... ", end="", flush=True)

        info = presign(token, f.name, mime, size)
        put_file(info["uploadUrl"], f, mime)

        uploaded.append({
            "key": info["key"],
            "filename": f.name,
            "size": size,
            "contentType": mime,
        })
        urls.append(info["publicUrl"])
        print(f"✓")

    print("  Completing upload... ", end="", flush=True)
    result = complete(token, uploaded)
    print(f"✓ {len(result.get('files', []))} files confirmed")

    return urls


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("token", help="Upload token from media_generate_upload_link")
    parser.add_argument("folder", help="Path to carousel folder")
    parser.add_argument("--json-out", help="Write URLs JSON to file")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"Error: {folder} is not a directory")
        sys.exit(1)

    print(f"Uploading carousel from: {folder.name}")
    urls = upload_carousel(args.token, folder)

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(urls, f, indent=2)
        print(f"\nURLs saved to {args.json_out}")

    print(f"\nDone: {len(urls)} files uploaded")
    print("\nmedia_urls (comma-separated):")
    print(",".join(urls))


if __name__ == "__main__":
    main()
