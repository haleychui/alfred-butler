"""
Google Calendar Service for Alfred
OAuth2 flow + read/write calendar events
"""
import os, json
# --- patched: always use shared device-level DB regardless of caller's db_func ---
import sqlite3 as _sq
_SHARED_DB = '/opt/alfred/data/alfred.db'
def _shared_conn():
    return _sq.connect(_SHARED_DB)

import httpx
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "")
SCOPES        = " ".join([
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.readonly",
])

AUTH_URL    = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL   = "https://oauth2.googleapis.com/token"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"


def authorize_url(label: str = "default") -> str:
    import urllib.parse
    params = (
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={urllib.parse.quote(SCOPES)}"
        f"&access_type=offline"
        f"&prompt=select_account%20consent"
        f"&state={urllib.parse.quote(label)}"
    )
    return AUTH_URL + params


def get_userinfo(access_token: str) -> dict:
    """Fetch Google account email via userinfo API."""
    try:
        r = httpx.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5
        )
        return r.json()
    except Exception:
        return {}


def list_accounts() -> list[dict]:
    """Return connected Google accounts, newest token per email."""
    c = _shared_conn()
    rows = c.execute(
        "SELECT key, value FROM memories WHERE category='gcal_account' ORDER BY ts DESC, rowid DESC"
    ).fetchall()
    active_row = c.execute(
        "SELECT value FROM memories WHERE category='gcal' AND key='active_account' ORDER BY ts DESC, rowid DESC LIMIT 1"
    ).fetchone()
    c.close()
    active_email = active_row[0] if active_row else None
    accounts = []
    seen = set()
    for email, val_json in rows:
        if email in seen:
            continue
        seen.add(email)
        try:
            info = json.loads(val_json)
        except Exception:
            info = {}
        accounts.append({
            "email": email,
            "label": info.get("label", ""),
            "active": (email == active_email),
        })
    return accounts


def set_active_account(email: str):
    """Set which Google account is active."""
    c = _shared_conn()
    c.execute("DELETE FROM memories WHERE category='gcal' AND key='active_account'")
    c.execute(
        "INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
        ("gcal", "active_account", email, datetime.now().isoformat())
    )
    c.commit(); c.close()


def disconnect_account(email: str = None):
    """Remove a Google account's tokens. If email=None, remove active account."""
    c = _shared_conn()
    if email is None:
        row = c.execute(
            "SELECT value FROM memories WHERE category='gcal' AND key='active_account' LIMIT 1"
        ).fetchone()
        email = row[0] if row else None
    if email:
        c.execute("DELETE FROM memories WHERE category='gcal_account' AND key=?", (email,))
        # If this was active, clear active pointer
        c.execute(
            "DELETE FROM memories WHERE category='gcal' AND key='active_account' AND value=?",
            (email,)
        )
    c.commit(); c.close()


def exchange_code(code: str) -> dict:
    r = httpx.post(TOKEN_URL, data={
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }, timeout=10)
    return r.json()


def refresh_token(refresh_tok: str) -> dict:
    r = httpx.post(TOKEN_URL, data={
        "refresh_token": refresh_tok,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
    }, timeout=10)
    return r.json()


def _get_access_token(db_func, email: str = None) -> str | None:
    """Get valid access token for the given (or active) account, refreshing if needed."""
    c = _shared_conn()
    # Determine which account to use
    if email is None:
        row_active = c.execute(
            "SELECT value FROM memories WHERE category='gcal' AND key='active_account' LIMIT 1"
        ).fetchone()
        if row_active:
            email = row_active[0]
    # Try new multi-account storage first
    row = None
    if email:
        row = c.execute(
            "SELECT value FROM memories WHERE category='gcal_account' AND key=? ORDER BY ts DESC LIMIT 1",
            (email,)
        ).fetchone()
    # Fall back to legacy single-account storage
    if not row:
        row = c.execute(
            "SELECT value FROM memories WHERE category='gcal' AND key='tokens' ORDER BY ts DESC LIMIT 1"
        ).fetchone()
    c.close()
    if not row:
        return None

    tokens = json.loads(row[0])
    access_token = tokens.get("access_token")
    expires_at = tokens.get("expires_at", 0)
    refresh_tok = tokens.get("refresh_token")

    # Refresh if expiring within 5 minutes
    if datetime.now().timestamp() > expires_at - 300 and refresh_tok:
        new = refresh_token(refresh_tok)
        if "access_token" in new:
            tokens["access_token"] = new["access_token"]
            tokens["expires_at"] = datetime.now().timestamp() + new.get("expires_in", 3600)
            if new.get("refresh_token"):
                tokens["refresh_token"] = new["refresh_token"]
            _save_account_tokens(email or "legacy", tokens)
            access_token = tokens["access_token"]

    return access_token


def _save_account_tokens(email: str, tokens: dict):
    """Save tokens keyed by Google account email."""
    c = _shared_conn()
    existing = c.execute(
        "SELECT value FROM memories WHERE category='gcal_account' AND key=? LIMIT 1", (email,)
    ).fetchone()
    label = ""
    if existing:
        try:
            label = json.loads(existing[0]).get("label", "")
        except Exception:
            pass
    tokens["label"] = label
    c.execute("DELETE FROM memories WHERE category='gcal_account' AND key=?", (email,))
    c.execute(
        "INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
        ("gcal_account", email, json.dumps(tokens), datetime.now().isoformat())
    )
    c.commit(); c.close()


def _save_tokens(db_func, tokens: dict):
    """Legacy save — also keeps old key for backward compat."""
    c = _shared_conn()
    c.execute("DELETE FROM memories WHERE category='gcal' AND key='tokens'")
    c.execute(
        "INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
        ("gcal", "tokens", json.dumps(tokens), datetime.now().isoformat())
    )
    c.commit(); c.close()


def save_tokens_from_code(code: str, db_func, label: str = "default"):
    """Exchange authorization code, fetch email, save to multi-account store."""
    tokens = exchange_code(code)
    if "access_token" not in tokens:
        return False, tokens.get("error", "unknown error"), None
    tokens["expires_at"] = datetime.now().timestamp() + tokens.get("expires_in", 3600)
    # Fetch Google account email
    userinfo = get_userinfo(tokens["access_token"])
    email = userinfo.get("email", f"account_{label}")
    tokens["label"] = label
    tokens["email"] = email
    # Save to multi-account store
    _save_account_tokens(email, tokens)
    # Set as active account
    set_active_account(email)
    # Also save legacy format for backward compat
    _save_tokens(db_func, tokens)
    return True, "ok", email


def is_connected(db_func) -> bool:
    return _get_access_token(db_func) is not None


def create_event(db_func, title: str, date: str, time: str = "", notes: str = "") -> dict:
    """Create a Google Calendar event. date=YYYY-MM-DD, time=HH:MM"""
    token = _get_access_token(db_func)
    if not token:
        return {"error": "not connected"}

    if time:
        start_dt = f"{date}T{time}:00+08:00"
        end_dt = f"{date}T{_add_hour(time)}:00+08:00"
        start = {"dateTime": start_dt, "timeZone": "Asia/Taipei"}
        end   = {"dateTime": end_dt,   "timeZone": "Asia/Taipei"}
    else:
        start = {"date": date}
        end   = {"date": date}

    body = {"summary": title, "start": start, "end": end}
    if notes:
        body["description"] = notes

    r = httpx.post(
        f"{CALENDAR_API}/calendars/primary/events",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body, timeout=10
    )
    return r.json()


def get_upcoming_events(db_func, days: int = 7) -> list[dict]:
    """Fetch upcoming events from Google Calendar."""
    token = _get_access_token(db_func)
    if not token:
        return []

    now = datetime.utcnow().isoformat() + "Z"
    end = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"

    r = httpx.get(
        f"{CALENDAR_API}/calendars/primary/events",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "timeMin": now, "timeMax": end,
            "singleEvents": True, "orderBy": "startTime",
            "maxResults": 20,
        }, timeout=10
    )
    items = r.json().get("items", [])
    events = []
    for item in items:
        start = item.get("start", {})
        dt = start.get("dateTime", start.get("date", ""))
        events.append({
            "id": item.get("id"),
            "title": item.get("summary", "（無標題）"),
            "start": dt[:16].replace("T", " ") if dt else "",
            "notes": item.get("description", ""),
        })
    return events


def get_events_for_audit(db_func, days: int = 14) -> list[dict]:
    """拿未來 N 天的會議完整資料，供會議瘦身分析用。"""
    token = _get_access_token(db_func)
    if not token:
        return []

    now = datetime.utcnow().isoformat() + "Z"
    end = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"

    r = httpx.get(
        f"{CALENDAR_API}/calendars/primary/events",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "timeMin": now, "timeMax": end,
            "singleEvents": True, "orderBy": "startTime",
            "maxResults": 50,
        }, timeout=10
    )
    items = r.json().get("items", [])
    events = []
    for item in items:
        start_raw = item.get("start", {})
        end_raw = item.get("end", {})
        start_dt = start_raw.get("dateTime", start_raw.get("date", ""))
        end_dt = end_raw.get("dateTime", end_raw.get("date", ""))

        # 計算時長（分鐘）
        duration_min = None
        try:
            from datetime import datetime as _dt
            s = _dt.fromisoformat(start_dt.rstrip("Z"))
            e = _dt.fromisoformat(end_dt.rstrip("Z"))
            duration_min = int((e - s).total_seconds() / 60)
        except Exception:
            pass

        attendees = item.get("attendees", [])
        is_recurring = bool(item.get("recurringEventId"))
        organizer = item.get("organizer", {}).get("email", "")

        events.append({
            "id": item.get("id"),
            "title": item.get("summary", "（無標題）"),
            "start": start_dt[:16].replace("T", " ") if start_dt else "",
            "duration_min": duration_min,
            "attendee_count": len(attendees),
            "is_recurring": is_recurring,
            "organizer": organizer,
            "has_agenda": bool(item.get("description", "").strip()),
            "location": item.get("location", ""),
        })
    return events


def _add_hour(time_str: str) -> str:
    """Add 1 hour to HH:MM string."""
    h, m = map(int, time_str.split(":"))
    h = (h + 1) % 24
    return f"{h:02d}:{m:02d}"
