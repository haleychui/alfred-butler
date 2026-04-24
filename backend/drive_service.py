"""
Google Drive service for Alfred.
Fetches files from Drive API and caches them in SQLite drive_index table.
First call is slow; subsequent calls read from local index (fast).
Index refreshes automatically if older than 30 minutes.
"""
import httpx
from datetime import datetime, timedelta

DRIVE_API = "https://www.googleapis.com/drive/v3"

ICON_MAP = {
    "application/pdf": "PDF",
    "application/vnd.google-apps.document": "Google 文件",
    "application/vnd.google-apps.spreadsheet": "試算表",
    "application/vnd.google-apps.presentation": "簡報",
    "application/vnd.google-apps.folder": "資料夾",
    "image/jpeg": "圖片", "image/png": "圖片", "image/gif": "圖片",
    "video/mp4": "影片", "audio/mpeg": "音樂",
    "application/zip": "壓縮檔",
    "text/plain": "文字檔",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PowerPoint",
    "application/msword": "Word",
}

def _token(db_func) -> str | None:
    try:
        import gcal_service
        return gcal_service._get_access_token(db_func)
    except Exception:
        return None

def _type_label(mime: str) -> str:
    return ICON_MAP.get(mime, "檔案")

def _fmt_size(b) -> str:
    try:
        b = int(b)
        if b < 1024: return f"{b}B"
        if b < 1048576: return f"{b//1024}KB"
        return f"{b/1048576:.1f}MB"
    except Exception:
        return "—"

def _index_is_fresh(db_func, max_age_minutes: int = 30) -> bool:
    """Check if index was updated within max_age_minutes."""
    try:
        c = db_func()
        row = c.execute("SELECT indexed_at FROM drive_index ORDER BY indexed_at DESC LIMIT 1").fetchone()
        c.close()
        if not row:
            return False
        last = datetime.fromisoformat(row[0])
        return datetime.now() - last < timedelta(minutes=max_age_minutes)
    except Exception:
        return False

def _save_to_index(db_func, files: list[dict]):
    """Upsert Drive file metadata into local SQLite index."""
    c = db_func()
    now = datetime.now().isoformat()
    for f in files:
        c.execute(
            """INSERT OR REPLACE INTO drive_index (id,name,mime_type,size,modified,url,indexed_at)
               VALUES (?,?,?,?,?,?,?)""",
            (f["id"], f["name"], f.get("mimeType",""), _fmt_size(f.get("size",0)),
             f.get("modifiedTime","")[:10], f.get("webViewLink",""), now)
        )
    c.commit()
    c.close()

def _fetch_from_api(db_func, query: str = "", max_results: int = 100) -> list[dict]:
    """Fetch from Drive API and save to index. Returns index-format dicts."""
    token = _token(db_func)
    if not token:
        return []
    q = "trashed=false"
    if query:
        q += f" and name contains '{query.replace(chr(39), '')}'"
    try:
        r = httpx.get(f"{DRIVE_API}/files",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "pageSize": max_results,
                "q": q,
                "orderBy": "modifiedTime desc",
                "fields": "files(id,name,mimeType,size,modifiedTime,webViewLink)",
            }, timeout=15)
        raw = r.json().get("files", [])
        _save_to_index(db_func, raw)
        return [{
            "id": f["id"],
            "name": f["name"],
            "type": _type_label(f.get("mimeType","")),
            "size": _fmt_size(f.get("size",0)),
            "modified": f.get("modifiedTime","")[:10],
            "url": f.get("webViewLink",""),
        } for f in raw]
    except Exception:
        return []

def _read_from_index(db_func, query: str = "", limit: int = 20) -> list[dict]:
    """Read from local SQLite index."""
    c = db_func()
    if query:
        kw = f"%{query}%"
        rows = c.execute(
            "SELECT id,name,mime_type,size,modified,url FROM drive_index "
            "WHERE name LIKE ? OR mime_type LIKE ? ORDER BY modified DESC LIMIT ?",
            (kw, kw, limit)
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT id,name,mime_type,size,modified,url FROM drive_index ORDER BY modified DESC LIMIT ?",
            (limit,)
        ).fetchall()
    c.close()
    return [{
        "id": r[0], "name": r[1], "type": _type_label(r[2]),
        "size": r[3], "modified": r[4], "url": r[5],
    } for r in rows]

def search_files(db_func, query: str = "", limit: int = 20, force_refresh: bool = False) -> tuple[list[dict], bool]:
    """
    Return (files, from_cache).
    Reads from local index if fresh; fetches from API and rebuilds index otherwise.
    """
    if not force_refresh and _index_is_fresh(db_func):
        results = _read_from_index(db_func, query, limit)
        return results, True
    # Fetch fresh from API (slow, but builds index)
    results = _fetch_from_api(db_func, query, max_results=100)
    if query:
        q_lower = query.lower()
        results = [f for f in results if q_lower in f["name"].lower() or q_lower in f["type"].lower()]
    return results[:limit], False

def list_recent(db_func, limit: int = 10) -> tuple[list[dict], bool]:
    return search_files(db_func, query="", limit=limit)

def index_count(db_func) -> int:
    try:
        c = db_func()
        n = c.execute("SELECT COUNT(*) FROM drive_index").fetchone()[0]
        c.close()
        return n
    except Exception:
        return 0

def is_connected(db_func) -> bool:
    return _token(db_func) is not None
