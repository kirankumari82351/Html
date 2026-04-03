import os

def _int(key: str, default: int = 0) -> int:
    """Safely parse env var to int — strips whitespace/quotes."""
    raw = os.environ.get(key, "").strip().strip('"').strip("'")
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default

API_ID      = _int("API_ID")
API_HASH    = os.environ.get("API_HASH", "").strip()
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "").strip()

# Numeric ID of log channel  e.g. -1001234567890
# Bot must be ADMIN in that channel
LOG_CHANNEL = _int("LOG_CHANNEL")

# Leave [] to allow everyone
ALLOWED_USERS: list[int] = []
