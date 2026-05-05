"""
Vocabulary Admin Server — run locally to manage word lists.
Usage: python admin/admin_server.py
Then open: http://localhost:8888
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE_DIR = Path(__file__).parent.parent
ADMIN_DIR = Path(__file__).parent
PORT = 8888


class AdminHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # suppress noisy request logs

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path in ("/", "/admin"):
            self._serve_file(ADMIN_DIR / "index.html", "text/html")

        elif parsed.path == "/api/files":
            files = sorted(f.name for f in BASE_DIR.glob("vocabulary*.json"))
            self._json(files)

        elif parsed.path == "/api/vocab":
            filename = qs.get("file", ["vocabulary_demo.json"])[0]
            data = self._load_vocab(filename)
            self._json(data)

        elif parsed.path == "/api/assets":
            filename = qs.get("file", ["vocabulary_demo.json"])[0]
            data = self._load_vocab(filename)
            result = {entry["word"]: self._check_assets(entry["word"]) for entry in data}
            self._json(result)

        elif parsed.path == "/api/config":
            self._json(self._load_config())

        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))

        if parsed.path == "/api/vocab":
            filename = body.get("file", "vocabulary_demo.json")
            vocab = body.get("vocab", [])
            self._save_vocab(filename, vocab)
            self._json({"ok": True})
        elif parsed.path == "/api/config":
            self._save_config(body)
            self._json({"ok": True})
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── Helpers ──────────────────────────────────────────────

    def _load_vocab(self, filename):
        path = BASE_DIR / filename
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return []

    def _save_vocab(self, filename, vocab):
        path = BASE_DIR / filename
        path.write_text(json.dumps(vocab, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_config(self):
        path = BASE_DIR / "config.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"vocabFile": "vocabulary_demo.json", "choiceCount": 2}

    def _save_config(self, config):
        path = BASE_DIR / "config.json"
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    def _check_assets(self, word):
        key = word.replace(" ", "_")
        imgs  = [(BASE_DIR / f"assets/images/{key}_{i}.jpg").exists() for i in [1, 2, 3]]
        audio = [(BASE_DIR / f"assets/audio/{key}_{i}.mp3").exists() for i in [1, 2, 3]]
        return {"images": imgs, "audio": audio}

    def _serve_file(self, path, mime):
        if not path.exists():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{mime}; charset=utf-8")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = HTTPServer(("localhost", PORT), AdminHandler)
    print(f"Admin running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()
