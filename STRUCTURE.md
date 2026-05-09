# Vocabulary Game — 專案結構說明

> 最後更新：2026-05-09（新增 story_look_at_me 類）

---

## 目錄結構

```
vocabulary-game/
├── STRUCTURE.md              ← 本文件（專案說明，需隨修改同步更新）
├── words.json                ← ★ 唯一單字來源（新增/刪除單字在這裡改）
├── vocabulary_demo.json      ← 遊戲執行期資料（由 words.json 內容派生）
├── config.json               ← 遊戲設定
├── index.html                ← 遊戲主頁面
├── game.js                   ← 遊戲邏輯
├── style.css                 ← 遊戲樣式
├── start.bat                 ← 雙擊啟動本地伺服器（port 8080）
├── vocabulary.txt            ← 課程規劃草稿（非程式讀取，純參考）
│
├── assets/
│   ├── images/
│   │   ├── body/             ← {word}_{1|2|3}.jpg
│   │   ├── classroom/        ← {word}_{1|2|3}.jpg
│   │   ├── animals/          ← {word}_{1|2|3}.jpg
│   │   ├── actions/          ← {word}_{1|2|3}.jpg
│   │   └── story_look_at_me/ ← {word}_{1|2|3}.jpg
│   └── audio/
│       ├── body/             ← {word}_{1|2|3}.mp3
│       ├── classroom/        ← {word}_{1|2|3}.mp3
│       ├── animals/          ← {word}_{1|2|3}.mp3
│       ├── actions/          ← {word}_{1|2|3}.mp3
│       ├── story_look_at_me/ ← {word}_{1|2|3}.mp3
│       └── sfx/
│           ├── correct.mp3
│           ├── wrong.mp3
│           └── complete.mp3
│
├── generate/
│   ├── .env                  ← API 金鑰（不進 git）
│   ├── fetch_images_pixabay.py   ← 抓圖腳本（讀 words.json）
│   ├── generate_audio_demo.py    ← 生成音檔腳本（讀 words.json）
│   ├── generate_images_demo.py   ← Gemini 生成插圖腳本（舊，讀 vocabulary_demo.json）
│   ├── validate_existing.py      ← 驗證現有圖片（用 Gemini，舊）
│   └── download_sfx.py           ← 從 Freesound 下載音效
│
└── admin/
    ├── admin_server.py       ← 管理後台伺服器
    └── index.html            ← 管理後台頁面
```

---

## 關鍵檔案說明

### words.json（唯一單字來源）

每筆格式：
```json
{"word": "cat", "category": "animals", "query": "cat cute pet", "labels": ["cat", "kitten", "feline"]}
```

| 欄位 | 說明 |
|---|---|
| `word` | 英文單字 |
| `category` | 分類，決定 assets 子資料夾（body / classroom / animals / actions） |
| `query` | Pixabay 搜尋字串 |
| `labels` | Cloud Vision 驗證關鍵字（小寫 substring match，至少一個命中即通過） |

目前共 58 個單字，分 6 類：
- **body**（10）：head, hair, eye, ear, nose, mouth, hand, arm, leg, foot
- **classroom**（10）：pen, book, desk, chair, bag, ruler, pencil, eraser, board, door
- **colors**（10）：red, blue, green, yellow, orange, pink, purple, black, white, brown
- **animals**（11）：dog, cat, bird, fish, pig, duck, elephant, lion, tiger, monkey, rabbit
- **actions**（10）：stand, sit, run, jump, walk, dance, sing, read, write, draw
- **story_look_at_me**（7）：me, mom, bike, really, look at, make a mess, next time

---

### vocabulary_demo.json（遊戲執行期資料）

遊戲 `game.js` 讀取此檔。每筆包含：
- `word`、`category`
- `images[]`：3 個相對路徑（`assets/images/{category}/{word}_{1|2|3}.jpg`）
- `audio[]`：3 個相對路徑（`assets/audio/{category}/{word}_{1|2|3}.mp3`）

**注意**：此檔不是由腳本自動重寫，路徑格式需和 assets 實際檔案一致。

---

### config.json

```json
{"vocabFile": "vocabulary_demo.json", "choiceCount": 2}
```
- `choiceCount`：每題的選項數量

---

### generate/.env（API 金鑰）

```
GEMINI_API_KEY=...           # generate_images_demo.py / validate_existing.py（舊腳本）
GOOGLE_TTS_API_KEY=...       # generate_audio_demo.py
CLOUD_VISION_API_KEY=...     # fetch_images_pixabay.py
PIXABAY_API_KEY=...          # fetch_images_pixabay.py（主要來源）
UNSPLASH_ACCESS_KEY=...      # fetch_images_pixabay.py（Pixabay 耗盡時備援）
FREESOUND_API_KEY=...        # download_sfx.py
```

---

## 生成腳本說明

所有腳本從 **project root** 執行：

### 抓圖（Pixabay）
```bash
python generate/fetch_images_pixabay.py
```
- 讀 `words.json`，每個單字搜尋 10 張候選（`image_type=all`）
- Laplacian variance 品質排序，取前 3 張
- 存 `assets/images/{category}/{word}_{1|2|3}.jpg`（400px，等比縮放）
- **已存在的圖自動跳過，缺哪張補哪張**（人工刪圖後重跑即可補）
- 無 AI 驗證，圖片內容由人工確認

### 生成音檔（Google TTS）
```bash
python generate/generate_audio_demo.py
```
- 讀 `words.json`，用 3 種聲音（female/male/female）
- 存 `assets/audio/{category}/{word}_{1|2|3}.mp3`
- 已存在的音檔自動跳過

### 下載音效
```bash
python generate/download_sfx.py
```
- 從 Freesound.org 下載 correct / wrong / complete 三個音效（CC0 授權優先）
- 存 `assets/audio/sfx/`

### 驗證現有圖片（舊，用 Gemini）
```bash
python generate/validate_existing.py assets/images/classroom
```
- 對指定資料夾內的 jpg 逐張用 Gemini 驗證，失敗則重新生成
- **依賴 generate_images_demo.py（Gemini 生成插圖），非 Pixabay 流程**

---

## 資產命名規則

| 類型 | 路徑 | 命名 |
|---|---|---|
| 圖片 | `assets/images/{category}/` | `{word}_{variant}.jpg`，variant = 1 / 2 / 3 |
| 音檔 | `assets/audio/{category}/` | `{word}_{variant}.mp3`，variant = 1 / 2 / 3 |
| 音效 | `assets/audio/sfx/` | `correct.mp3`、`wrong.mp3`、`complete.mp3` |

> **檔名不可含空白**：`word` 欄位若為片語（如 `make a mess`），圖片與音檔的檔名中空白一律改為底線（`make_a_mess_1.jpg`、`make_a_mess_1.mp3`）。
> 原因：`vocabulary_demo.json` 的路徑由瀏覽器以 `fetch()` 載入，URL 中空白須編碼為 `%20`，導致路徑與實際檔名不符而 404。底線無需編碼，可直接對應。
> 此規則同時適用於 `assets/images/` 與 `assets/audio/` 下的所有檔案。

---

## 新增單字流程

1. 在 `words.json` 加入一筆：
   ```json
   {"word": "apple", "category": "food", "query": "apple fruit red", "labels": ["apple", "fruit"]}
   ```
2. 在 `vocabulary_demo.json` 加入對應的遊戲資料（images / audio 路徑）
3. 執行 `fetch_images_pixabay.py` 抓圖
4. 執行 `generate_audio_demo.py` 生成音檔
5. 更新本文件的單字清單

---

## 啟動遊戲

```
雙擊 start.bat
```
或手動：
```bash
python -m http.server 8080
# 開啟 http://localhost:8080
```

---

## 已知狀態（2026-05-09）

- 全部 58 × 3 = 174 張圖片已生成（body / classroom / colors / animals / actions / story_look_at_me）
- 全部 58 × 3 = 174 個音檔已生成
- 圖片由 Pixabay 品質排序後直接存檔，**內容正確性需人工確認**；刪除不合適的圖後重跑腳本即自動補齊
- `validate_existing.py` 和 `generate_images_demo.py` 仍使用舊的 Gemini API，與新的 Pixabay 流程獨立
