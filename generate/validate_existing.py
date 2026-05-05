"""
Validate existing images in a folder with Gemini Vision.
Regenerates any image that fails validation (once, with stronger prompt).
Run from project root: python generate/validate_existing.py assets/images/classroom
"""

import sys
import json
import base64
import time
import urllib.request
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

# ── reuse config from generate_images_demo ────────────
sys.path.insert(0, str(Path(__file__).parent))
from generate_images_demo import (
    GEMINI_API_KEY, VARIANT_CHARS, STYLE, WORDS_ACTIONS,
    generate_image_bytes, save_as_jpeg,
)

TARGET_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("assets/images/classroom")


def validate_image(image_bytes: bytes, word: str) -> tuple[bool, str]:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}")
    prompt_text = (
        f"This cartoon image is for an English vocabulary game for children aged 6-7. "
        f"The image should clearly show the English word '{word}'. "
        f"Can a child easily identify '{word}' from this image alone? "
        f"Reply YES or NO on the first line, then one sentence explaining why."
    )
    body = json.dumps({
        "contents": [{
            "parts": [
                {"inline_data": {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(image_bytes).decode()
                }},
                {"text": prompt_text}
            ]
        }]
    }).encode()
    for wait in [5, 15, 30]:   # 429 自動重試
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return text.upper().startswith("YES"), text
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"    rate limit, wait {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("validate_image: exceeded retry limit")


def make_strong_prompt(word: str, variant: int) -> str:
    char = VARIANT_CHARS[variant - 1]
    action = WORDS_ACTIONS.get(word, f"holding a {word} and showing it off")
    return (
        f"{char} {action}. {STYLE}. No text or labels in the image. "
        f"The '{word}' object must be very large and prominent in the center "
        f"of the image, unmistakably clear to a child."
    )


def main():
    images = sorted(TARGET_DIR.glob("*.jpg"))
    if not images:
        print(f"No images found in {TARGET_DIR}")
        return

    print(f"Validating {len(images)} images in {TARGET_DIR}...\n")
    failed_after_retry = []

    for img_path in images:
        stem = img_path.stem                      # e.g. "bag_1"
        parts = stem.rsplit("_", 1)
        if len(parts) != 2 or not parts[1].isdigit():
            print(f"skip {img_path.name} (unexpected filename format)")
            continue
        word, variant = parts[0], int(parts[1])

        image_bytes = img_path.read_bytes()
        passed, reason = validate_image(image_bytes, word)
        short = reason.replace("\n", " ")[:90]

        if passed:
            print(f"  [OK] {img_path.name}")
        else:
            print(f"  [FAIL] {img_path.name}  : {short}")
            print(f"    -> regenerating with stronger prompt...")
            try:
                new_bytes = generate_image_bytes(make_strong_prompt(word, variant))
                time.sleep(1)
                passed2, reason2 = validate_image(new_bytes, word)
                short2 = reason2.replace("\n", " ")[:90]
                if passed2:
                    save_as_jpeg(new_bytes, img_path)
                    print(f"    [OK] regenerated and passed, overwritten")
                else:
                    save_as_jpeg(new_bytes, img_path)
                    print(f"    [FAIL] still failed: {short2} (overwritten, needs review)")
                    failed_after_retry.append((img_path.name, word, reason2))
            except Exception as e:
                print(f"    ERROR regeneration failed: {e}")
                failed_after_retry.append((img_path.name, word, str(e)))

        time.sleep(1.5)   # rate limit buffer

    print(f"\n{'='*55}")
    print(f"  Done  |  needs review: {len(failed_after_retry)}")
    print(f"{'='*55}")
    if failed_after_retry:
        print("\n  The following images failed validation twice:")
        for name, word, reason in failed_after_retry:
            print(f"  - {name} ({word}): {reason.replace(chr(10), ' ')[:90]}")


if __name__ == "__main__":
    main()
