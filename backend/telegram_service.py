"""
Telegram Bot API service for Alfred.
Uses HTTP Bot API (no MTProto needed for bot).
"""
import os, httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API_BASE  = f"https://api.telegram.org/bot{BOT_TOKEN}"


def is_configured() -> bool:
    return bool(BOT_TOKEN)


def set_webhook(url: str, secret: str = "") -> dict:
    data: dict = {"url": url}
    if secret:
        data["secret_token"] = secret
    r = httpx.post(f"{API_BASE}/setWebhook", json=data, timeout=10)
    return r.json()


def delete_webhook() -> dict:
    r = httpx.post(f"{API_BASE}/deleteWebhook", timeout=10)
    return r.json()


def send_message(chat_id: int | str, text: str, parse_mode: str = "") -> bool:
    payload: dict = {"chat_id": chat_id, "text": text[:4096]}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        r = httpx.post(f"{API_BASE}/sendMessage", json=payload, timeout=10)
        return r.json().get("ok", False)
    except Exception:
        return False


def get_me() -> dict:
    r = httpx.get(f"{API_BASE}/getMe", timeout=10)
    return r.json()
