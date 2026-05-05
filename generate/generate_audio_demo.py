"""
Generate audio for vocabulary words using Google Cloud Text-to-Speech API (free tier: 1M chars/month).
Run from project root: python generate/generate_audio_demo.py
"""

import json
import base64
import urllib.request
from pathlib import Path

GOOGLE_TTS_API_KEY = "AIzaSyAHY5VZz3ottyJPZRxoyJCtfCm7DZCv-Wg"
ASSETS_DIR = Path(__file__).parent.parent / "assets"
VOCAB_FILE = Path(__file__).parent.parent / "vocabulary_demo.json"

# 3 voices with distinct character: female / male / female (different style)
VOICES = [
    ("en-US-Neural2-C", 1),   # female, clear and bright
    ("en-US-Neural2-D", 2),   # male, warm and friendly
    ("en-US-Neural2-H", 3),   # female, energetic
]


def synthesize(text: str, voice_name: str) -> bytes:
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={GOOGLE_TTS_API_KEY}"
    body = json.dumps({
        "input": {"text": text},
        "voice": {"languageCode": "en-US", "name": voice_name},
        "audioConfig": {"audioEncoding": "MP3", "speakingRate": 0.9}
    }).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return base64.b64decode(data["audioContent"])


def main():
    entries = json.loads(VOCAB_FILE.read_text(encoding="utf-8"))
    total = len(entries) * len(VOICES)
    print(f"Generating {total} audio files with Google TTS...")

    done = 0
    for entry in entries:
        word = entry["word"]
        cat = entry["category"]
        out_dir = ASSETS_DIR / "audio" / cat
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{word}]")
        for voice_name, variant in VOICES:
            out = out_dir / f"{word}_{variant}.mp3"
            if out.exists():
                print(f"  skip {out.name} (already exists)")
                done += 1
                continue
            try:
                audio_bytes = synthesize(word, voice_name)
                out.write_bytes(audio_bytes)
                print(f"  created {out.name} ({voice_name})")
            except Exception as e:
                print(f"  ERROR {out.name}: {e}")
            done += 1
            print(f"  progress: {done}/{total}")
    print("Done.")


if __name__ == "__main__":
    main()
