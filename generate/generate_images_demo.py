"""
Generate images for vocabulary words using Google Imagen 4 (free tier).
Each image is validated by Gemini Vision; auto-retries once with stronger prompt.
Two consecutive failures → added to final report, user decides whether to regenerate.

Run from project root: python generate/generate_images_demo.py
"""

import json
import base64
import time
import urllib.request
import urllib.error
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False
    print("Warning: Pillow not installed. Run: pip install pillow")

GEMINI_API_KEY = "AIzaSyAJEOoZKy-SSetCk7ED-ND2ZPrqMGDLqiQ"
ASSETS_DIR = Path(__file__).parent.parent / "assets"
VOCAB_FILE = Path(__file__).parent.parent / "vocabulary_demo.json"

WORDS_ACTIONS = {
    "head":   "pointing both hands up toward their head and smiling",
    "hair":   "touching and showing off their colorful hair",
    "eye":    "pointing to one of their eyes with a big smile",
    "ear":    "cupping a hand around their ear as if listening",
    "nose":   "pointing to their nose and giggling",
    "mouth":  "pointing to their smiling mouth and showing teeth",
    "hand":   "holding one hand up high and waving it",
    "arm":    "stretching one arm straight out to the side",
    "leg":    "lifting one leg up with a playful pose",
    "foot":   "lifting one foot up and pointing down at it",
    "pen":    "holding up a pen and pretending to write in the air",
    "book":   "holding a big book open with both hands and smiling",
    "desk":   "sitting at a desk and placing both hands flat on it",
    "chair":  "sitting on a chair with hands on knees and grinning",
    "bag":    "lifting a school bag with both hands and showing it off",
    "ruler":  "holding a ruler out flat and measuring something",
    "pencil": "holding a pencil and drawing a picture in the air",
    "eraser": "holding an eraser and pretending to erase something",
    "board":  "standing in front of a chalkboard and pointing at it",
    "door":     "standing in a doorway holding the door open",
    # animals
    "dog":      "a cute cartoon dog sitting and wagging its tail happily",
    "cat":      "a cute cartoon cat sitting and smiling with bright eyes",
    "bird":     "a colorful cartoon bird perched on a branch with wings spread",
    "fish":     "a colorful cartoon fish swimming in clear blue water",
    "pig":      "a cute cartoon pig standing in a farm with a curly tail",
    "duck":     "a cute cartoon duck waddling near a pond with a cheerful look",
    "elephant": "a friendly cartoon elephant standing with its trunk raised",
    "lion":     "a friendly cartoon lion sitting with a big fluffy mane",
    "tiger":    "a friendly cartoon tiger sitting with visible orange and black stripes",
    "monkey":   "a playful cartoon monkey hanging from a tree branch and smiling",
    "rabbit":   "a cute cartoon rabbit sitting upright with long floppy ears",
}

VARIANT_CHARS = [
    "a cheerful cartoon boy with short brown hair and a blue shirt",
    "a cheerful cartoon girl with pigtails and a pink dress",
    "a cheerful cartoon child with curly red hair and a yellow shirt",
]

STYLE = ("full body visible, white background, flat vector art style, "
         "bright bold colors, thick outlines, designed for elementary school "
         "children ages 6-7, simple and clear")


# ── Prompt builder ────────────────────────────────────
def make_prompt(word: str, variant: int, strong: bool = False) -> str:
    char = VARIANT_CHARS[variant - 1]
    action = WORDS_ACTIONS.get(word, f"pointing to their {word}")
    prompt = f"{char} {action}. {STYLE}. No text or labels in the image."
    if strong:
        prompt += (f" The '{word}' object must be very large and prominent "
                   f"in the center of the image, unmistakably clear to a child.")
    return prompt


# ── Imagen 4 generation ───────────────────────────────
def generate_image_bytes(prompt: str) -> bytes:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"imagen-4.0-fast-generate-001:predict?key={GEMINI_API_KEY}")
    body = json.dumps({
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}
    }).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return base64.b64decode(data["predictions"][0]["bytesBase64Encoded"])


# ── Gemini Vision validation ──────────────────────────
def validate_image(image_bytes: bytes, word: str) -> tuple[bool, str]:
    """Ask Gemini 1.5 Flash whether the image clearly shows the target word."""
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
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    passed = text.upper().startswith("YES")
    return passed, text


# ── Image save ────────────────────────────────────────
def save_as_jpeg(image_bytes: bytes, path: Path):
    if HAS_PILLOW:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        img = img.resize((400, 400), Image.LANCZOS)
        img.save(str(path), "JPEG", quality=85)
    else:
        path.write_bytes(image_bytes)


# ── Main ──────────────────────────────────────────────
def main():
    vocab = json.loads(VOCAB_FILE.read_text(encoding="utf-8"))
    word_to_cat = {entry["word"]: entry["category"] for entry in vocab}

    words = list(WORDS_ACTIONS.keys())
    total = len(words) * 3
    print(f"Generating {total} images with Imagen 4 + Gemini Vision validation...\n")

    done = 0
    truly_failed: list[tuple[Path, str, int, str]] = []

    for word in words:
        cat = word_to_cat.get(word, "misc")
        out_dir = ASSETS_DIR / "images" / cat
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{word}]")

        for variant in [1, 2, 3]:
            out = out_dir / f"{word}_{variant}.jpg"
            if out.exists():
                print(f"  skip {out.name} (already exists)")
                done += 1
                continue

            saved = False
            for attempt in [1, 2]:
                try:
                    img_bytes = generate_image_bytes(
                        make_prompt(word, variant, strong=(attempt == 2))
                    )
                    passed, reason = validate_image(img_bytes, word)

                    if passed:
                        save_as_jpeg(img_bytes, out)
                        print(f"  ✓ {out.name}  驗證通過（第 {attempt} 次）")
                        saved = True
                        time.sleep(2)
                        break
                    else:
                        short = reason.replace("\n", " ")[:90]
                        print(f"  ✗ 第 {attempt} 次驗證失敗：{short}")
                        if attempt == 2:
                            save_as_jpeg(img_bytes, out)   # 先存，讓用戶決定
                            truly_failed.append((out, word, variant, reason))
                        time.sleep(3)

                except Exception as e:
                    print(f"  ERROR (attempt {attempt}): {e}")
                    time.sleep(5)
                    break

            done += 1
            print(f"  progress: {done}/{total}")

    # ── 最終報告 ──
    print(f"\n{'═'*55}")
    print(f"  完成：{done}/{total}  |  驗證失敗：{len(truly_failed)} 張")
    print(f"{'═'*55}")

    if truly_failed:
        print(f"\n  ⚠  以下 {len(truly_failed)} 張圖 AI 驗證連續失敗 2 次：")
        for path, word, variant, reason in truly_failed:
            short = reason.replace("\n", " ")[:90]
            print(f"  - {path.name}：{short}")
        print()
        ans = input("要刪除這些圖並重新生成嗎？(y/n): ").strip().lower()
        if ans == "y":
            for path, *_ in truly_failed:
                path.unlink(missing_ok=True)
            print("已刪除。重新執行腳本即可自動補齊。")
        else:
            print("保留現有圖片。")
    else:
        print("  全部驗證通過 🎉")


if __name__ == "__main__":
    main()
