"""
Gmail service for Alfred — read + send emails via Google Gmail API.
Shares the same OAuth tokens stored by gcal_service (calendar + gmail scopes).
"""
import os, json, base64
from datetime import datetime
from email.mime.text import MIMEText
import httpx
from dotenv import load_dotenv

load_dotenv()

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"


def _get_access_token(db_func) -> str | None:
    """Reuse gcal_service token store (same OAuth grant covers all scopes)."""
    try:
        import gcal_service
        return gcal_service._get_access_token(db_func)
    except Exception:
        return None


def list_messages(db_func, max_results: int = 10, query: str = "is:unread") -> list[dict]:
    """Return recent emails matching query."""
    token = _get_access_token(db_func)
    if not token:
        return []
    try:
        r = httpx.get(f"{GMAIL_API}/messages",
            headers={"Authorization": f"Bearer {token}"},
            params={"maxResults": max_results, "q": query},
            timeout=10)
        items = r.json().get("messages", [])
        results = []
        for item in items:
            msg = _get_message(token, item["id"])
            if msg:
                results.append(msg)
        return results
    except Exception:
        return []


def _get_message(token: str, msg_id: str) -> dict | None:
    try:
        r = httpx.get(f"{GMAIL_API}/messages/{msg_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"format": "metadata", "metadataHeaders": ["From","Subject","Date"]},
            timeout=10)
        d = r.json()
        headers = {h["name"]: h["value"] for h in d.get("payload", {}).get("headers", [])}
        snippet = d.get("snippet", "")
        return {
            "id": msg_id,
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", "（無主旨）"),
            "date": headers.get("Date", ""),
            "snippet": snippet[:200],
        }
    except Exception:
        return None


def get_message_body(db_func, msg_id: str) -> str:
    """Get full plain-text body of a message."""
    token = _get_access_token(db_func)
    if not token:
        return ""
    try:
        r = httpx.get(f"{GMAIL_API}/messages/{msg_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"format": "full"},
            timeout=10)
        payload = r.json().get("payload", {})
        return _extract_body(payload)
    except Exception:
        return ""


def _extract_body(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace") if data else ""
    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            return text
    return ""


def send_email(db_func, to: str, subject: str, body: str) -> bool:
    """Send email from the authenticated Gmail account."""
    token = _get_access_token(db_func)
    if not token:
        return False
    msg = MIMEText(body, "plain", "utf-8")
    msg["to"] = to
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        r = httpx.post(f"{GMAIL_API}/messages/send",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"raw": raw},
            timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def mark_read(db_func, msg_id: str) -> bool:
    token = _get_access_token(db_func)
    if not token:
        return False
    try:
        r = httpx.post(f"{GMAIL_API}/messages/{msg_id}/modify",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"removeLabelIds": ["UNREAD"]},
            timeout=10)
        return r.status_code == 200
    except Exception:
        return False
