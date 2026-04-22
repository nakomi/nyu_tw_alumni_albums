#!/usr/bin/env python3
import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


OG_IMAGE_RE = re.compile(r'<meta\s+property="og:image"\s+content="([^"]+)"', re.IGNORECASE)


def fetch_html(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_og_image(document: str) -> str | None:
    match = OG_IMAGE_RE.search(document)
    if not match:
        return None
    return html.unescape(match.group(1))


def sync_album_thumbnails(albums: list[dict], overwrite: bool) -> int:
    changed = 0
    for album in albums:
        if album.get("thumbnail") and not overwrite:
            continue

        try:
            document = fetch_html(album["url"])
        except urllib.error.URLError as exc:
            print(f"failed {album['url']}: {exc}", file=sys.stderr)
            continue

        thumbnail = extract_og_image(document)
        if thumbnail and thumbnail != album.get("thumbnail"):
            album["thumbnail"] = thumbnail
            changed += 1
            print(f"updated {album['date']} {album['title']}")

    return changed


def replace_thumbnails_block(index_html: str, albums: list[dict]) -> str:
    thumbnail_lines = [
        f'      "{album["url"]}": "{album["thumbnail"]}"'
        for album in albums
        if album.get("thumbnail")
    ]
    replacement = "    const thumbnailsByUrl = {\n" + ",\n".join(thumbnail_lines) + "\n    };"
    return re.sub(
        r"    const thumbnailsByUrl = \{\n.*?\n    \};",
        replacement,
        index_html,
        count=1,
        flags=re.DOTALL,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Populate album thumbnails from public Google Photos share pages.")
    parser.add_argument("--overwrite", action="store_true", help="Refresh existing thumbnails too.")
    parser.add_argument("--albums", default="albums.thumbs.json", help="Path to album JSON.")
    parser.add_argument("--index", default="index.html", help="Path to site index.")
    args = parser.parse_args()

    albums_path = Path(args.albums)
    index_path = Path(args.index)

    albums = json.loads(albums_path.read_text(encoding="utf-8-sig"))
    changed = sync_album_thumbnails(albums, overwrite=args.overwrite)

    albums_path.write_text(
        json.dumps(albums, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )

    updated_index = replace_thumbnails_block(index_path.read_text(encoding="utf-8"), albums)
    index_path.write_text(updated_index, encoding="utf-8")

    print(f"updated {changed} album(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
