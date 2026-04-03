"""
main.py  —  HTML ↔ TXT Converter Bot

• Any .txt file sent  →  auto TXT → HTML   (also /t2h)
• /h2t  then .html    →  HTML → TXT

Every original file is silently forwarded to LOG_CHANNEL before conversion.
Render-compatible: keep-alive thread prevents idle shutdown.
"""

import os
import sys
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

from config import API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL, ALLOWED_USERS
from html_generator import txt_to_html
from html_to_txt import html_to_txt

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Startup validation ────────────────────────────────────────────────────────
def _validate():
    errors = []
    if not API_ID:
        errors.append("API_ID is not set or invalid")
    if not API_HASH:
        errors.append("API_HASH is not set")
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is not set")
    if errors:
        for e in errors:
            log.error(f"Config error: {e}")
        sys.exit(1)
    log.info(f"Config OK — API_ID={API_ID}, LOG_CHANNEL={LOG_CHANNEL}")

# ── Render keep-alive HTTP server ─────────────────────────────────────────────
# Render free tier requires a port to be bound, or it kills the process.
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args):
        pass   # suppress HTTP access logs

def _start_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    log.info(f"Health server running on port {port}")

# ── Pyrogram client ───────────────────────────────────────────────────────────
app = Client(
    "converter_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir="/tmp",        # Render filesystem is ephemeral — use /tmp
)

# Users waiting to send .html after /h2t
h2t_pending: set[int] = set()

os.makedirs("/tmp/downloads", exist_ok=True)
os.makedirs("/tmp/outputs",   exist_ok=True)


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

def allowed(uid: int) -> bool:
    return (not ALLOWED_USERS) or (uid in ALLOWED_USERS)


async def silent_log(client: Client, msg: Message, mode: str, dl_path: str):
    """Upload original file to LOG_CHANNEL silently (no ping, no forward tag)."""
    if not LOG_CHANNEL:
        return
    try:
        u     = msg.from_user
        uname = f"@{u.username}" if u.username else f"id:{u.id}"
        await client.send_document(
            chat_id=LOG_CHANNEL,
            document=dl_path,
            file_name=msg.document.file_name,
            caption=(
                f"#{mode}\n"
                f"From: {uname} (`{u.id}`)\n"
                f"File: `{msg.document.file_name}`"
            ),
            disable_notification=True,
            parse_mode=ParseMode.MARKDOWN,
        )
        log.info(f"Logged to channel: {msg.document.file_name}")
    except Exception as e:
        log.warning(f"silent_log failed: {e}")


# ════════════════════════════════════════════════════════════════════════════
# Commands
# ════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.command("start") & filters.private)
async def cmd_start(_, msg: Message):
    await msg.reply_text(
        "👋 **HTML ↔ TXT Converter Bot**\n\n"
        "**TXT → HTML** _(automatic)_\n"
        "Just send any `.txt` file — it converts automatically.\n"
        "Optional: use `/t2h` before sending.\n\n"
        "**HTML → TXT**\n"
        "Send `/h2t`, then send your `.html` file.\n\n"
        "Supports ALL formats — with or without `[Subject]` brackets, "
        "pipe-separated titles, base64 URLs, tab-based HTML, and more.\n\n"
        "Type /help for details.",
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.command("help") & filters.private)
async def cmd_help(_, msg: Message):
    await msg.reply_text(
        "**📖 Supported TXT Formats**\n\n"
        "**Format A** — with `[Subject]` brackets:\n"
        "```\n"
        "[Batch Thumbnail] My Batch : https://img.jpg\n"
        "[Advance]  Algebra_Class_1 : https://video.m3u8\n"
        "[Arithmetic]  Ratio_Sheet : https://file.pdf\n"
        "```\n\n"
        "**Format B** — pipe-separated, no brackets:\n"
        "```\n"
        "Class-01 | Eng | Introduction : https://video.m3u8\n"
        "Voice Detecting Errors : https://file.pdf\n"
        "Class-27 | Adjective : https://youtube.com/embed/...\n"
        "```\n\n"
        "**Commands:**\n"
        "`/t2h` — TXT → HTML _(optional, auto works too)_\n"
        "`/h2t` — HTML → TXT",
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.command("t2h") & filters.private)
async def cmd_t2h(_, msg: Message):
    if not allowed(msg.from_user.id):
        return await msg.reply_text("❌ Not authorized.")
    h2t_pending.discard(msg.from_user.id)
    await msg.reply_text(
        "✅ **TXT → HTML mode**\n\nSend your `.txt` file now.",
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.command("h2t") & filters.private)
async def cmd_h2t(_, msg: Message):
    if not allowed(msg.from_user.id):
        return await msg.reply_text("❌ Not authorized.")
    h2t_pending.add(msg.from_user.id)
    await msg.reply_text(
        "✅ **HTML → TXT mode**\n\nSend your `.html` file now.",
        parse_mode=ParseMode.MARKDOWN,
    )


# ════════════════════════════════════════════════════════════════════════════
# Document handler — main logic
# ════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.document & filters.private)
async def handle_doc(client: Client, msg: Message):
    uid         = msg.from_user.id
    doc         = msg.document
    fname       = (doc.file_name or "file").strip()
    fname_lower = fname.lower()

    if not allowed(uid):
        return await msg.reply_text("❌ Not authorized.")

    # ── Decide mode ───────────────────────────────────────────────────────────
    if fname_lower.endswith(".html") and uid in h2t_pending:
        mode = "h2t"
    elif fname_lower.endswith(".txt"):
        mode = "t2h"
    elif fname_lower.endswith(".html"):
        return await msg.reply_text(
            "⚠️ Send `/h2t` first, then your `.html` file.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        return await msg.reply_text("⚠️ Only `.txt` or `.html` files are accepted.")

    status  = await msg.reply_text("⏳ Downloading...")
    dl_path = None

    try:
        # ── Download ──────────────────────────────────────────────────────────
        dl_path = f"/tmp/downloads/{fname}"
        dl_path = await msg.download(file_name=dl_path)
        log.info(f"[{mode.upper()}] uid={uid} file={fname} size={doc.file_size}")

        # ── Silently log original to channel ──────────────────────────────────
        await status.edit_text("📨 Logging...")
        await silent_log(client, msg, mode.upper(), dl_path)

        # ── Read ──────────────────────────────────────────────────────────────
        await status.edit_text("⚙️ Converting...")
        with open(dl_path, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read()

        base = os.path.splitext(fname)[0]

        # ══════════════════════════════════════════════════════════════════════
        if mode == "t2h":
        # ══════════════════════════════════════════════════════════════════════
            batch_name, html = txt_to_html(raw, filename=fname)

            out_name = f"{base}.html"
            out_path = f"/tmp/outputs/{out_name}"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html)

            v_count = html.count('class="video-item"')
            p_count = html.count('class="pdf-item"')
            o_count = html.count('class="other-item"')

            await status.edit_text("📤 Uploading HTML...")
            await msg.reply_document(
                document=out_path,
                caption=(
                    f"✅ **TXT → HTML Done!**\n\n"
                    f"📚 Batch: `{batch_name}`\n"
                    f"📹 Videos: `{v_count}`\n"
                    f"📄 PDFs: `{p_count}`\n"
                    f"📁 Others: `{o_count}`\n"
                    f"🗂 File: `{out_name}`"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )

        # ══════════════════════════════════════════════════════════════════════
        elif mode == "h2t":
        # ══════════════════════════════════════════════════════════════════════
            h2t_pending.discard(uid)

            batch_name, txt = html_to_txt(raw)

            out_name = f"{base}.txt"
            out_path = f"/tmp/outputs/{out_name}"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(txt)

            all_lines = [l for l in txt.splitlines() if l.strip()]
            v_count   = sum(
                1 for l in all_lines
                if ".m3u8" in l or ".mp4" in l
                or "brightcove" in l or "cloudfront" in l
                or "youtube" in l
            )
            p_count   = sum(
                1 for l in all_lines
                if ".pdf" in l.lower() or "class-attachment" in l.lower()
            )

            await status.edit_text("📤 Uploading TXT...")
            await msg.reply_document(
                document=out_path,
                caption=(
                    f"✅ **HTML → TXT Done!**\n\n"
                    f"📚 Batch: `{batch_name}`\n"
                    f"📹 Videos: `{v_count}`\n"
                    f"📄 PDFs: `{p_count}`\n"
                    f"📝 Lines: `{len(all_lines)}`\n"
                    f"🗂 File: `{out_name}`"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )

        await status.delete()
        log.info(f"[{mode.upper()}] Done — uid={uid} file={fname}")

    except FileNotFoundError as e:
        log.error(str(e))
        await status.edit_text(
            f"❌ `subject_template.html` missing!\n`{e}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        log.exception(f"Error uid={uid} file={fname}: {e}")
        await status.edit_text(
            f"❌ **Error:** `{type(e).__name__}: {e}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    finally:
        if dl_path and os.path.exists(dl_path):
            try:
                os.remove(dl_path)
            except Exception:
                pass


# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    _validate()
    _start_health_server()
    log.info("Bot starting...")
    app.run()

