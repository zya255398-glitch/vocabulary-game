"""
fetch_images_pixabay.py — Pixabay 抓圖 + 品質篩選 + Gemini Vision 驗證

流程（每個單字）：
  1. Pixabay 搜尋，抓 POOL_SIZE 張候選圖 URL
  2. 全部下載，用 Laplacian variance 評估清晰度，過濾曝光異常的圖
  3. 按清晰度排序（最清晰優先）
  4. 依序送 Gemini 驗證；通過則存圖（3 variants 各用不同圖）
  5. 全部失敗 → 存最後一張供人工確認

Run from project root: python generate/fetch_images_pixabay.py
"""

import base64
import io
import json
import sys
import time
import urllib.request
from io import BytesIO
from pathlib import Path

import numpy as np
import requests

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False
    print("Warning: Pillow not installed. Run: pip install pillow")

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GEMINI_API_KEY  = "AIzaSyAJEOoZKy-SSetCk7ED-ND2ZPrqMGDLqiQ"
PIXABAY_API_KEY = "55712918-12d1601df5de947cdfed9e3ec"
ASSETS_DIR  = Path(__file__).parent.parent / "assets"
VOCAB_FILE  = Path(__file__).parent.parent / "vocabulary_demo.json"

POOL_SIZE       = 10    # 每個單字抓幾張候選
BRIGHTNESS_MIN  = 40    # 平均亮度下限（同 photo_selector）
BRIGHTNESS_MAX  = 215   # 平均亮度上限

WORD_QUERIES = {
    "head":    "human head face portrait",
    "hair":    "child hair colorful",
    "eye":     "human eye closeup",
    "ear":     "human ear side view",
    "nose":    "human nose face",
    "mouth":   "human mouth smile teeth",
    "hand":    "child hand wave",
    "arm":     "human arm gesture",
    "leg":     "human leg",
    "foot":    "human foot barefoot",
    "pen":     "pen ballpoint writing",
    "book":    "book open reading",
    "desk":    "school desk student",
    "chair":   "chair simple furniture",
    "bag":     "school bag backpack child",
    "ruler":   "ruler measurement school",
    "pencil":  "pencil drawing school",
    "eraser":  "eraser rubber school",
    "board":   "chalkboard blackboard school",
    "door":    "door wooden entrance",
    # animals
    "dog":      "dog cute pet",
    "cat":      "cat cute pet",
    "bird":     "bird colorful",
    "fish":     "fish colorful underwater",
    "pig":      "pig farm animal",
    "duck":     "duck water bird",
    "elephant": "elephant wildlife",
    "lion":     "lion wildlife",
    "tiger":    "tiger wildlife",
    "monkey":   "monkey wildlife",
    "rabbit":   "rabbit cute pet",
}


# ── Pixabay ───────────────────────────────────────────

def fetch_pixabay_pool(query: str) -> list[str]:
    resp = requests.get(
        "https://pixabay.com/api/",
        params={
            "key":        PIXABAY_API_KEY,
            "q":          query,
            "per_page":   POOL_SIZE,
            "image_type": "all",
            "safesearch": "true",
            "lang":       "en",
            "order":      "popular",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return [h["largeImageURL"] for h in resp.json().get("hits", [])]


# ── 下載 ──────────────────────────────────────────────

def download_image_bytes(url: str) -> bytes:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content


# ── 品質評分（Laplacian variance + 亮度） ─────────────

def quality_score(raw: bytes) -> float | None:
    """
    回傳清晰度分數（越高越清晰）。
    曝光異常（太暗 / 太亮）回傳 None，代表直接過濾掉。
    """
    if not HAS_PILLOW:
        return 0.0
    try:
        img  = Image.open(BytesIO(raw)).convert("L")
        arr  = np.array(img, dtype=float)
        brightness = arr.mean()
        if not (BRIGHTNESS_MIN <= brightness <= BRIGHTNESS_MAX):
            return None
        # Laplacian variance（同 photo_selector 的 BLUR_THRESHOLD 邏輯）
        lap = (arr[:-2, 1:-1] + arr[2:, 1:-1]
             + arr[1:-1, :-2] + arr[1:-1, 2:]
             - 4 * arr[1:-1, 1:-1])
        return float(lap.var())
    except Exception:
        return None


# ── 格式轉換 ──────────────────────────────────────────

def to_jpeg_bytes(raw: bytes) -> bytes:
    if not HAS_PILLOW:
        return raw
    img = Image.open(BytesIO(raw)).convert("RGB")
    buf = BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


# ── Gemini Vision 驗證 ────────────────────────────────

def validate_image(jpeg_bytes: bytes, word: str) -> tuple[bool, str]:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    )
    prompt_text = (
        f"This image is for an English vocabulary game for children aged 6-7. "
        f"The image should clearly show the English word '{word}'. "
        f"Can a child easily identify '{word}' from this image alone? "
        f"Reply YES or NO on the first line, then one sentence explaining why."
    )
    body = json.dumps({
        "contents": [{
            "parts": [
                {"inline_data": {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(jpeg_bytes).decode(),
                }},
                {"text": prompt_text},
            ]
        }]
    }).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read())
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    return text.upper().startswith("YES"), text


# ── 存圖（等比縮放，不變形）─────────────────────────

def save_as_jpeg(raw: bytes, path: Path, size: int = 400) -> None:
    if HAS_PILLOW:
        img = Image.open(BytesIO(raw)).convert("RGB")
        img.thumbnail((size, size), Image.LANCZOS)  # 等比縮放
        img.save(str(path), "JPEG", quality=85)
    else:
        path.write_bytes(raw)


# ── 主流程 ────────────────────────────────────────────

def main() -> None:
    vocab       = json.loads(VOCAB_FILE.read_text(encoding="utf-8"))
    word_to_cat = {e["word"]: e["category"] for e in vocab}

    words = list(WORD_QUERIES.keys())
    total = len(words) * 3
    print(f"Pixabay 抓圖（每字 {POOL_SIZE} 張）→ 品質排序 → Gemini 驗證")
    print(f"目標：{total} 張（{len(words)} 個單字 × 3 variants）\n")

    done         = 0
    truly_failed: list[tuple[Path, str, int, str]] = []

    for word in words:
        cat     = word_to_cat.get(word, "misc")
        out_dir = ASSETS_DIR / "images" / cat
        out_dir.mkdir(parents=True, exist_ok=True)

        if all((out_dir / f"{word}_{v}.jpg").exists() for v in [1, 2, 3]):
            print(f"[{word}] skip（3 variants 已存在）")
            done += 3
            continue

        # ── Step 1: 抓 URL ──
        print(f"[{word}] 搜尋 Pixabay：「{WORD_QUERIES[word]}」")
        try:
            urls = fetch_pixabay_pool(WORD_QUERIES[word])
        except Exception as e:
            print(f"  ERROR 搜尋失敗：{e}")
            for v in [1, 2, 3]:
                if not (out_dir / f"{word}_{v}.jpg").exists():
                    truly_failed.append((out_dir / f"{word}_{v}.jpg", word, v, str(e)))
                    done += 1
            continue

        # ── Step 2: 下載 + 品質評分 ──
        print(f"  下載 {len(urls)} 張候選...")
        scored: list[tuple[float, bytes]] = []
        for i, url in enumerate(urls, 1):
            try:
                raw   = download_image_bytes(url)
                score = quality_score(raw)
                if score is None:
                    print(f"    #{i} 曝光異常，跳過")
                else:
                    scored.append((score, raw))
            except Exception as e:
                print(f"    #{i} 下載失敗：{e}")

        # 按清晰度排序（最清晰優先）
        scored.sort(key=lambda x: -x[0])
        print(f"  通過品質篩選：{len(scored)} 張，依清晰度排序完畢")

        if not scored:
            print(f"  ERROR 無可用圖片，跳過 [{word}]")
            for v in [1, 2, 3]:
                if not (out_dir / f"{word}_{v}.jpg").exists():
                    truly_failed.append((out_dir / f"{word}_{v}.jpg", word, v, "品質篩選後無可用圖"))
                    done += 1
            continue

        # ── Step 3: 每個 variant 依序送 Gemini 驗證 ──
        pool_idx = 0  # 跨 variant 遞增，確保每個 variant 用不同的圖

        for variant in [1, 2, 3]:
            out = out_dir / f"{word}_{variant}.jpg"
            if out.exists():
                print(f"  skip {out.name}（已存在）")
                done += 1
                continue

            saved    = False
            last_raw = None

            while pool_idx < len(scored):
                score, raw = scored[pool_idx]
                pool_idx  += 1

                try:
                    jpeg_bytes     = to_jpeg_bytes(raw)
                    passed, reason = validate_image(jpeg_bytes, word)
                    short          = reason.replace("\n", " ")[:80]

                    if passed:
                        save_as_jpeg(raw, out)
                        print(f"  [OK] {out.name}  清晰度={score:.0f}  Gemini 通過")
                        saved = True
                        time.sleep(1)
                        break
                    else:
                        last_raw = raw
                        print(f"  [NG] #{pool_idx} 清晰度={score:.0f}  Gemini 拒絕：{short}")
                        time.sleep(1)

                except Exception as e:
                    last_raw = raw
                    print(f"  ERROR #{pool_idx}：{e}")
                    time.sleep(2)

            if not saved:
                fallback = last_raw or scored[-1][1]
                save_as_jpeg(fallback, out)
                truly_failed.append((out, word, variant, f"Gemini 驗證全部失敗（pool 耗盡）"))
                print(f"  [!!] {out.name} 已存最後一張，需人工確認")

            done += 1
            print(f"  進度：{done}/{total}")

    # ── 最終報告 ──
    print(f"\n{'═'*55}")
    print(f"  完成：{done}/{total}  |  需人工確認：{len(truly_failed)} 張")
    print(f"{'═'*55}")

    if truly_failed:
        print(f"\n  以下 {len(truly_failed)} 張需人工確認：")
        for path, word, variant, reason in truly_failed:
            print(f"  - {path.name}：{reason[:80]}")
        print()
        ans = input("要刪除這些圖並重新抓取嗎？(y/n): ").strip().lower()
        if ans == "y":
            for path, *_ in truly_failed:
                path.unlink(missing_ok=True)
            print("已刪除，重新執行腳本即可補齊。")
        else:
            print("保留現有圖片，請自行替換。")
    else:
        print("  全部驗證通過！")


if __name__ == "__main__":
    main()
