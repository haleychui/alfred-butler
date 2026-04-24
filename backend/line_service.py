"""
LINE Messaging API service for Alfred.
Auto-generates channel access token from channel ID + secret.
"""
import os, hashlib, hmac, base64, time
import httpx
from dotenv import load_dotenv

load_dotenv()

CHANNEL_ID     = os.getenv("LINE_CHANNEL_ID", "")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_API       = "https://api.line.me/v2/bot"
TOKEN_URL      = "https://api.line.me/v2/oauth/accessToken"

_cache = {"token": None, "expires_at": 0}


def is_configured() -> bool:
    return bool(CHANNEL_ID and CHANNEL_SECRET)


def get_access_token() -> str | None:
    if not is_configured():
        return None
    now = time.time()
    if _cache["token"] and now < _cache["expires_at"] - 600:
        return _cache["token"]
    try:
        r = httpx.post(TOKEN_URL, data={
            "grant_type": "client_credentials",
            "client_id": CHANNEL_ID,
            "client_secret": CHANNEL_SECRET,
        }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=10)
        d = r.json()
        if "access_token" in d:
            _cache["token"] = d["access_token"]
            _cache["expires_at"] = now + d.get("expires_in", 2592000)
            return _cache["token"]
    except Exception:
        pass
    return None


def verify_signature(body: bytes, signature: str) -> bool:
    expected = base64.b64encode(
        hmac.new(CHANNEL_SECRET.encode(), body, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(expected, signature)


def reply_message(reply_token: str, text: str) -> bool:
    token = get_access_token()
    if not token:
        return False
    try:
        r = httpx.post(
            f"{LINE_API}/message/reply",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"replyToken": reply_token, "messages": [{"type": "text", "text": text[:5000]}]},
            timeout=10
        )
        return r.status_code == 200
    except Exception:
        return False


def push_message(user_id: str, text: str) -> bool:
    token = get_access_token()
    if not token:
        return False
    try:
        r = httpx.post(
            f"{LINE_API}/message/push",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"to": user_id, "messages": [{"type": "text", "text": text[:5000]}]},
            timeout=10
        )
        return r.status_code == 200
    except Exception:
        return False
