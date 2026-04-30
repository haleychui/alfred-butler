"""
Google Drive service for Alfred.
Fetches files from Drive API and caches them in SQLite drive_index table.
First call is slow; subsequent calls read from local index (fast).
Index refreshes automatically if older than 30 minutes.
Supports shared drives (supportsAllDrives / includeItemsFromAllDrives).
Per-user DB support: pass user_conn to use per-user DB; falls back to shared DB.
"""
import httpx
import sqlite3 as _sq
_SHARED_DB = '/opt/alfred/data/alfred.db'
def _shared_conn():
    return _sq.connect(_SHARED_DB)

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

def _get_conn(user_conn=None):
    """Return (conn, should_close). If user_conn provided, use it (caller manages lifecycle)."""
    if user_conn is not None:
        return user_conn, False
    c = _shared_conn()
    return c, True

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

def _ensure_drive_index_table(conn):
    """Ensure drive_index table and drive_name column exist in the given conn."""
    conn.execute("""CREATE TABLE IF NOT EXISTS drive_index
        (id TEXT PRIMARY KEY, name TEXT, mime_type TEXT, size TEXT,
         modified TEXT, url TEXT, drive_name TEXT, indexed_at TEXT)""")
    cols = [row[1] for row in conn.execute("PRAGMA table_info(drive_index)").fetchall()]
    if "drive_name" not in cols:
        conn.execute("ALTER TABLE drive_index ADD COLUMN drive_name TEXT DEFAULT ''")
    conn.commit()

def _index_is_fresh(db_func, max_age_minutes: int = 30, user_conn=None) -> bool:
    """Check if index was updated within max_age_minutes."""
    try:
        c, should_close = _get_conn(user_conn)
        _ensure_drive_index_table(c)
        row = c.execute("SELECT indexed_at FROM drive_index ORDER BY indexed_at DESC LIMIT 1").fetchone()
        if should_close:
            c.close()
        if not row:
            return False
        last = datetime.fromisoformat(row[0])
        return datetime.now() - last < timedelta(minutes=max_age_minutes)
    except Exception:
        return False

def _ensure_drive_name_column():
    """Add drive_name column to drive_index if it does not exist yet (shared DB, kept for backward compat)."""
    try:
        c = _shared_conn()
        _ensure_drive_index_table(c)
        c.close()
    except Exception:
        pass

def _save_to_index(db_func, files: list[dict], user_conn=None):
    """Upsert Drive file metadata into local SQLite index."""
    c, should_close = _get_conn(user_conn)
    _ensure_drive_index_table(c)
    now = datetime.now().isoformat()
    for f in files:
        c.execute(
            """INSERT OR REPLACE INTO drive_index (id,name,mime_type,size,modified,url,indexed_at,drive_name)
               VALUES (?,?,?,?,?,?,?,?)""",
            (f["id"], f["name"], f.get("mimeType",""), _fmt_size(f.get("size",0)),
             f.get("modifiedTime","")[:10], f.get("webViewLink",""), now,
             f.get("drive_name","我的雲端硬碟"))
        )
    c.commit()
    if should_close:
        c.close()

def _fetch_shared_drives(token: str) -> list[dict]:
    """列出所有共用雲端硬碟，回傳 [{id, name}]。"""
    try:
        r = httpx.get(f"{DRIVE_API}/drives",
            headers={"Authorization": f"Bearer {token}"},
            params={"pageSize": 100, "fields": "drives(id,name)"},
            timeout=15)
        drives = r.json().get("drives", [])
        print(f"[drive_service] 共用雲端硬碟數量：{len(drives)}")
        return drives
    except Exception as e:
        print(f"[drive_service] _fetch_shared_drives 失敗：{e}")
        return []

def _fetch_from_api(db_func, query: str = "", max_results: int = 100, user_conn=None) -> list[dict]:
    """Fetch from Drive API (含共用雲端硬碟) and save to index. Returns index-format dicts."""
    token = _token(db_func)
    if not token:
        return []
    q = "trashed=false"
    if query:
        q += f" and name contains '{query.replace(chr(39), '')}'"

    all_raw: list[dict] = []

    # ── Step 1: 分頁抓 allDrives（含我的雲端硬碟 + 所有共用硬碟）──
    page_token = None
    page_size = min(max_results, 1000)
    fetched = 0
    while True:
        try:
            params = {
                "pageSize": page_size,
                "q": q,
                "orderBy": "modifiedTime desc",
                "fields": "nextPageToken,files(id,name,mimeType,size,modifiedTime,webViewLink,driveId)",
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True,
                "corpora": "allDrives",
            }
            if page_token:
                params["pageToken"] = page_token
            r = httpx.get(f"{DRIVE_API}/files",
                headers={"Authorization": f"Bearer {token}"},
                params=params, timeout=30)
            data = r.json()
            raw = data.get("files", [])
            all_raw.extend(raw)
            fetched += len(raw)
            page_token = data.get("nextPageToken")
            print(f"[drive_service] 已取 {fetched} 筆，nextPageToken={'有' if page_token else '無'}")
            if not page_token or fetched >= max_results:
                break
        except Exception as e:
            print(f"[drive_service] allDrives 搜尋失敗：{e}")
            break

    # ── Step 2: 取得共用硬碟名稱對照表，補充 drive_name 欄位 ──
    shared_drives = _fetch_shared_drives(token)
    drive_id_to_name = {d["id"]: d["name"] for d in shared_drives}

    for f in all_raw:
        drive_id = f.get("driveId", "")
        if drive_id and drive_id in drive_id_to_name:
            f["drive_name"] = drive_id_to_name[drive_id]
        else:
            f["drive_name"] = "我的雲端硬碟"

    # 去重（同一 id 只保留一筆）
    seen = set()
    deduped = []
    for f in all_raw:
        if f["id"] not in seen:
            seen.add(f["id"])
            deduped.append(f)

    print(f"[drive_service] 索引檔案數：{len(deduped)}，共用硬碟：{len(shared_drives)} 個")
    _save_to_index(db_func, deduped, user_conn=user_conn)
    return [{
        "id": f["id"],
        "name": f["name"],
        "type": _type_label(f.get("mimeType","")),
        "size": _fmt_size(f.get("size",0)),
        "modified": f.get("modifiedTime","")[:10],
        "url": f.get("webViewLink",""),
        "drive_name": f.get("drive_name","我的雲端硬碟"),
    } for f in deduped]

def _read_from_index(db_func, query: str = "", limit: int = 20, user_conn=None) -> list[dict]:
    """Read from local SQLite index."""
    c, should_close = _get_conn(user_conn)
    _ensure_drive_index_table(c)
    if query:
        kw = f"%{query}%"
        rows = c.execute(
            "SELECT id,name,mime_type,size,modified,url,drive_name FROM drive_index "
            "WHERE name LIKE ? OR mime_type LIKE ? ORDER BY modified DESC LIMIT ?",
            (kw, kw, limit)
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT id,name,mime_type,size,modified,url,drive_name FROM drive_index ORDER BY modified DESC LIMIT ?",
            (limit,)
        ).fetchall()
    if should_close:
        c.close()
    return [{
        "id": r[0], "name": r[1], "type": _type_label(r[2]),
        "size": r[3], "modified": r[4], "url": r[5],
        "drive_name": r[6] or "我的雲端硬碟",
    } for r in rows]

def search_files(db_func, query: str = "", limit: int = 20, force_refresh: bool = False, user_conn=None) -> tuple[list[dict], bool]:
    """
    Return (files, from_cache).
    Reads from local index if fresh; fetches from API and rebuilds index otherwise.
    """
    if not force_refresh and _index_is_fresh(db_func, user_conn=user_conn):
        results = _read_from_index(db_func, query, limit, user_conn=user_conn)
        return results, True
    # Fetch fresh from API (slow, but builds index)
    results = _fetch_from_api(db_func, query, max_results=100, user_conn=user_conn)
    if query:
        q_lower = query.lower()
        results = [f for f in results if q_lower in f["name"].lower() or q_lower in f["type"].lower()]
    return results[:limit], False

def list_recent(db_func, limit: int = 10, user_conn=None) -> tuple[list[dict], bool]:
    return search_files(db_func, query="", limit=limit, user_conn=user_conn)

def index_count(db_func, user_conn=None) -> int:
    try:
        c, should_close = _get_conn(user_conn)
        _ensure_drive_index_table(c)
        n = c.execute("SELECT COUNT(*) FROM drive_index").fetchone()[0]
        if should_close:
            c.close()
        return n
    except Exception:
        return 0

def is_connected(db_func) -> bool:
    return _token(db_func) is not None

def download_and_extract(file_id: str, token: str, mime_type: str = "") -> str:
    """下載 Drive 檔案並抽取文字內容。支援 Google Docs export 和一般檔案。"""
    headers = {"Authorization": f"Bearer {token}"}

    # Google Workspace 格式用 export
    export_map = {
        "application/vnd.google-apps.document": ("text/plain", "export"),
        "application/vnd.google-apps.spreadsheet": ("text/csv", "export"),
        "application/vnd.google-apps.presentation": ("text/plain", "export"),
    }

    try:
        if mime_type in export_map:
            export_mime, _ = export_map[mime_type]
            r = httpx.get(
                f"{DRIVE_API}/files/{file_id}/export",
                headers=headers,
                params={"mimeType": export_mime},
                timeout=30
            )
            return r.text[:80000]
        else:
            # 一般檔案直接下載到記憶體
            r = httpx.get(
                f"{DRIVE_API}/files/{file_id}",
                headers=headers,
                params={"alt": "media"},
                timeout=30
            )
            # 根據 mime 抽文字
            content = r.content
            if "pdf" in mime_type:
                import io
                try:
                    import pypdf
                    reader = pypdf.PdfReader(io.BytesIO(content))
                    return "\n".join(p.extract_text() or "" for p in reader.pages)[:80000]
                except Exception:
                    return ""
            elif "wordprocessing" in mime_type or mime_type.endswith("docx"):
                import io
                try:
                    import docx
                    doc = docx.Document(io.BytesIO(content))
                    return "\n".join(p.text for p in doc.paragraphs)[:80000]
                except Exception:
                    return ""
            else:
                try:
                    return content.decode("utf-8", errors="ignore")[:80000]
                except Exception:
                    return ""
    except Exception as e:
        return f"[下載失敗: {e}]"

