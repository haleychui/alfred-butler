"""
Google Calendar Service for Alfred
OAuth2 flow + read/write calendar events
"""
import os, json
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


def authorize_url() -> str:
    params = (
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={SCOPES}"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    return AUTH_URL + params


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


def _get_access_token(db_func) -> str | None:
    """Get valid access token, refreshing if needed."""
    c = db_func()
    row = c.execute(
        "SELECT value FROM memories WHERE category='gcal' AND key=? ORDER BY ts DESC LIMIT 1",
        ("tokens",)
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
            _save_tokens(db_func, tokens)
            access_token = tokens["access_token"]

    return access_token


def _save_tokens(db_func, tokens: dict):
    c = db_func()
    c.execute(
        "INSERT OR REPLACE INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
        ("gcal", "tokens", json.dumps(tokens), datetime.now().isoformat())
    )
    c.commit(); c.close()


def save_tokens_from_code(code: str, db_func):
    """Exchange authorization code and save tokens to DB."""
    tokens = exchange_code(code)
    if "access_token" not in tokens:
        return False, tokens.get("error", "unknown error")
    tokens["expires_at"] = datetime.now().timestamp() + tokens.get("expires_in", 3600)
    _save_tokens(db_func, tokens)
    return True, "ok"


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


def _add_hour(time_str: str) -> str:
    """Add 1 hour to HH:MM string."""
    h, m = map(int, time_str.split(":"))
    h = (h + 1) % 24
    return f"{h:02d}:{m:02d}"
