import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

ENV_PATH = Path(__file__).resolve().parent / ".env"
if load_dotenv is not None and ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)


def _get_env(key, default=None):
    value = os.getenv(key)
    if value is None or value == "":
        return default
    return value


def _to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_int_list(value):
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [int(v) for v in value if str(v).strip().lstrip("-").isdigit()]
    raw = str(value).strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return [int(p) for p in parts if p.lstrip("-").isdigit()]


api_id = _parse_int(_get_env("API_ID", _get_env("TELEGRAM_API_ID")))
api_hash = _get_env("API_HASH", _get_env("TELEGRAM_API_HASH", ""))
openai_api_key = _get_env("OPENAI_API_KEY", "")
telegram_bot_token = _get_env("TELEGRAM_BOT_TOKEN", "")

FOLDER_NAME = _get_env("FOLDER_NAME", "GPT")
TARGET_CHAT_ID = _get_env("TARGET_CHAT_ID", "")
SUBSCRIBERS_FILE = _get_env("SUBSCRIBERS_FILE", "subscribers.json")

DEBUG_USER_IDS = _parse_int_list(_get_env("DEBUG_USER_IDS"))
_debug_mode_env = os.getenv("DEBUG_MODE")
DEBUG_MODE = _to_bool(_debug_mode_env, default=bool(DEBUG_USER_IDS))


# Optional local overrides (keep secrets out of git)
try:
    from config_local import *  # type: ignore  # noqa: F401,F403
except Exception:
    pass