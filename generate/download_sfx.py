"""
Download game sound effects from Freesound.org (CC0 licensed).
Run from project root: python generate/download_sfx.py
Requires: pip install requests
"""

import sys
import urllib.request
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("請先安裝 requests：pip install requests")

FREESOUND_API_KEY = "OdIfOmJKfeQiWkw7NJFl1Oc7GSP8LaGfdonhzEYd"
OUTPUT_DIR = Path(__file__).parent.parent / "assets" / "audio" / "sfx"

TARGETS = [
    {
        "filename": "correct.mp3",
        "query": "ding correct",
        "max_duration": 3.0,
    },
    {
        "filename": "wrong.mp3",
        "query": "wrong buzz game",
        "max_duration": 3.0,
    },
    {
        "filename": "complete.mp3",
        "query": "victory fanfare short game",
        "max_duration": 5.0,
    },
]


def search_sound(query: str, max_duration: float) -> dict | None:
    """Search Freesound, filter by duration in Python, prefer CC0."""
    resp = requests.get(
        "https://freesound.org/apiv2/search/text/",
        params={
            "token": FREESOUND_API_KEY,
            "query": query,
            "fields": "id,name,duration,license,previews,username",
            "sort": "downloads_desc",
            "page_size": 50,
        },
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])

    AUDIO_EXTS = (".mp3", ".wav", ".ogg", ".flac", ".aiff", ".aif")
    candidates = [
        r for r in results
        if r["duration"] <= max_duration
        and not r["name"].lower().endswith(AUDIO_EXTS)
    ]
    if not candidates:
        return None

    # Prefer CC0
    cc0 = [r for r in candidates if "zero" in r["license"]]
    return cc0[0] if cc0 else candidates[0]


def download_preview(sound: dict, out_path: Path):
    mp3_url = sound["previews"].get("preview-hq-mp3") or sound["previews"].get("preview-lq-mp3")
    if not mp3_url:
        raise ValueError("No preview MP3 URL available")
    urllib.request.urlretrieve(mp3_url, out_path)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for target in TARGETS:
        out = OUTPUT_DIR / target["filename"]
        if out.exists():
            print(f"skip {target['filename']} (already exists)")
            continue

        print(f"Searching: {target['query']} (max {target['max_duration']}s)...")
        try:
            sound = search_sound(target["query"], target["max_duration"])
            if not sound:
                print(f"  ERROR: no results found for '{target['query']}'")
                continue

            print(f"  found: \"{sound['name']}\" by {sound['username']}")
            print(f"  duration: {sound['duration']:.2f}s  license: {sound['license']}")

            download_preview(sound, out)
            print(f"  saved → {out}")
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\nDone. 音效檔位置：", OUTPUT_DIR)
    print("請試聽確認是否合適，若不滿意可刪除該檔案後重新執行（會取下一個結果）。")


if __name__ == "__main__":
    main()
