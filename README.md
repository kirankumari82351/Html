# 🔄 HTML ↔ TXT Converter Bot

Telegram bot — converts `.txt` course files → `.html` and vice versa.

---

## 📁 Files

```
converter_bot/
├── main.py                ← Bot + Render keep-alive server
├── html_generator.py      ← TXT → HTML
├── html_to_txt.py         ← HTML → TXT
├── subject_template.html  ← HTML template (required)
├── config.py              ← Reads env vars safely
├── requirements.txt
├── render.yaml            ← Render deploy config
└── .env.example
```

---

## 🚀 Deploy on Render (Free)

### Step 1 — Push to GitHub
Upload this folder to a **private** GitHub repo.

### Step 2 — Create Render Web Service
1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repo
3. Settings:
   - **Environment:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
   - **Plan:** Free

### Step 3 — Add Environment Variables
In Render dashboard → **Environment** tab, add:

| Key | Value |
|-----|-------|
| `API_ID` | Your Telegram API ID |
| `API_HASH` | Your Telegram API Hash |
| `BOT_TOKEN` | Your bot token from @BotFather |
| `LOG_CHANNEL` | Numeric channel ID e.g. `-1001234567890` |
| `PORT` | `8080` |

> **How to get LOG_CHANNEL numeric ID:**  
> Add `@username_to_id_bot` to your channel → it gives `-100xxxxxxxxxx`  
> Make sure your bot is **Admin** in that channel.

### Step 4 — Deploy
Click **Deploy** — bot starts automatically. ✅

---

## 💻 Local / Colab Run

```bash
pip install -r requirements.txt

# Set env vars
export API_ID=12345678
export API_HASH=your_hash
export BOT_TOKEN=your_token
export LOG_CHANNEL=-1001234567890

python main.py
```

---

## 🤖 Bot Commands

| Command | Action |
|---------|--------|
| `/start` | Welcome |
| `/help` | Format guide |
| `/t2h` | TXT → HTML mode (optional) |
| `/h2t` | HTML → TXT mode |
| Send `.txt` | Auto-converts to `.html` |

---

## 📋 TXT Formats Supported

**Format A** (with brackets):
```
[Batch Thumbnail] My Batch : https://img.jpg
[Advance]  Algebra_Class_1 : https://video.m3u8
[Arithmetic]  Ratio_Sheet : https://file.pdf
```

**Format B** (pipe-separated):
```
Class-01 | Eng | Introduction : https://video.m3u8
Voice Detecting Errors : https://file.pdf
Class-27 | Adjective : https://youtube.com/embed/xxx
```

## 🌐 HTML Formats Supported

- `subject_template.html` style (folder-content divs)
- Tab-based crwill style (videos-tab / pdfs-tab)
- JS CONFIG with **base64-encoded URLs** (GS special style)
- Generic fallback (any HTML with onclick/href URLs)
