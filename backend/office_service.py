"""
Alfred 辦公室模組 — 12 場景
"""
import json
from datetime import datetime, timedelta
from typing import Optional

# ── DB 表初始化 SQL ─────────────────────────────────────────────────────────
OFFICE_DB_TABLES = """
    CREATE TABLE IF NOT EXISTS office_rooms
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         name TEXT NOT NULL, capacity INTEGER DEFAULT 4,
         floor TEXT, notes TEXT);
    CREATE TABLE IF NOT EXISTS office_bookings
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         room_id INTEGER, title TEXT, booked_by TEXT DEFAULT 'me',
         start_time TEXT, end_time TEXT, attendees TEXT,
         checked_in INTEGER DEFAULT 0, check_in_time TEXT,
         released INTEGER DEFAULT 0, ts TEXT);
    CREATE TABLE IF NOT EXISTS office_supplies
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         item TEXT NOT NULL, category TEXT DEFAULT 'general',
         quantity REAL DEFAULT 0, threshold REAL DEFAULT 1,
         unit TEXT DEFAULT '個', buy_url TEXT,
         auto_order INTEGER DEFAULT 0, notes TEXT, last_ordered TEXT);
    CREATE TABLE IF NOT EXISTS office_supply_orders
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         supply_id INTEGER, quantity REAL,
         ordered_at TEXT, status TEXT DEFAULT 'pending');
    CREATE TABLE IF NOT EXISTS office_colleagues
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         name TEXT NOT NULL, role TEXT, dept TEXT,
         timezone TEXT DEFAULT 'Asia/Taipei',
         joined_date TEXT, slack_handle TEXT, email TEXT,
         notes TEXT, added_at TEXT);
    CREATE TABLE IF NOT EXISTS colleague_activity
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         colleague_id INTEGER, activity_type TEXT, ts TEXT);
    CREATE TABLE IF NOT EXISTS thanks_log
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         from_person TEXT DEFAULT 'me', to_person TEXT NOT NULL,
         reason TEXT, thanked INTEGER DEFAULT 0, ts TEXT);
    CREATE TABLE IF NOT EXISTS onboarding_tasks
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         colleague_id INTEGER NOT NULL, task TEXT NOT NULL,
         due_day INTEGER, completed_at TEXT, notes TEXT);
"""

# ── LLM Tools 定義 ──────────────────────────────────────────────────────────
OFFICE_TOOLS = [
    {"name": "office_room",
     "description":
        "管理辦公室會議室預約與打卡。"
        "訂房→action=book；到場打卡（告知阿福我進來了）→action=checkin；"
        "主動釋出沒人用的房間→action=release；查目前各房間狀態→action=status；"
        "新增/設定會議室→action=add。",
     "input_schema": {"type": "object", "properties": {
         "action":     {"type": "string", "enum": ["book","checkin","release","status","add"]},
         "room_name":  {"type": "string", "description": "會議室名稱"},
         "title":      {"type": "string", "description": "會議主題（book 用）"},
         "start_time": {"type": "string", "description": "開始時間 YYYY-MM-DDTHH:MM（book 用）"},
         "end_time":   {"type": "string", "description": "結束時間 YYYY-MM-DDTHH:MM（book 用）"},
         "attendees":  {"type": "string", "description": "出席者姓名，逗號分隔"},
         "capacity":   {"type": "integer", "description": "容納人數（add 用）"},
         "floor":      {"type": "string",  "description": "樓層（add 用）"},
         "booking_id": {"type": "integer", "description": "訂房 ID（checkin/release 用）"}
     }, "required": ["action"]}},

    {"name": "office_supply",
     "description":
        "追蹤辦公室耗材庫存，低於門檻時提醒補貨。"
        "新增品項→action=add；更新現有數量→action=update；"
        "查看快沒了的品項→action=low；記錄已下訂→action=order；列出全部→action=list。",
     "input_schema": {"type": "object", "properties": {
         "action":    {"type": "string", "enum": ["add","update","low","order","list"]},
         "item":      {"type": "string",  "description": "耗材名稱"},
         "category":  {"type": "string",  "description": "辦公/清潔/廚房/咖啡/紙張/其他"},
         "quantity":  {"type": "number",  "description": "目前數量"},
         "threshold": {"type": "number",  "description": "低庫存警戒線"},
         "unit":      {"type": "string",  "description": "單位，如 包/盒/瓶/卷"},
         "buy_url":   {"type": "string",  "description": "購買連結（選填）"},
         "order_qty": {"type": "number",  "description": "本次訂購數量（order 用）"}
     }, "required": ["action"]}},

    {"name": "office_colleague",
     "description":
        "管理同事資料、互動紀錄、沉默偵測、專長查找。"
        "新增同事→action=add；記錄今天有互動→action=activity；"
        "找哪些人最近沉默了→action=silence；依主題找最懂的人→action=expertise；"
        "列出所有同事→action=list。",
     "input_schema": {"type": "object", "properties": {
         "action":        {"type": "string", "enum": ["add","activity","silence","expertise","list"]},
         "name":          {"type": "string", "description": "同事姓名"},
         "role":          {"type": "string", "description": "職稱"},
         "dept":          {"type": "string", "description": "部門"},
         "timezone":      {"type": "string", "description": "時區，如 America/New_York（非台北時用）"},
         "joined_date":   {"type": "string", "description": "到職日 YYYY-MM-DD"},
         "email":         {"type": "string"},
         "slack_handle":  {"type": "string"},
         "notes":         {"type": "string", "description": "個人特質、喜好、注意事項、專長摘要"},
         "activity_type": {"type": "string", "description": "互動類型：message/meeting/help/review"},
         "query":         {"type": "string", "description": "查詢關鍵字（expertise 用，如「財務法規」「React」）"},
         "silence_days":  {"type": "integer", "description": "幾天沒互動算沉默（預設 5）"}
     }, "required": ["action"]}},

    {"name": "office_thanks",
     "description":
        "記錄誰幫過你，EOD 提醒致謝，讓感謝不因為忙碌被省略。"
        "記錄幫助→action=log；查還沒致謝的人→action=pending；標記已感謝→action=done。",
     "input_schema": {"type": "object", "properties": {
         "action":    {"type": "string", "enum": ["log","pending","done"]},
         "to_person": {"type": "string", "description": "幫了你的人的名字"},
         "reason":    {"type": "string", "description": "對方做了什麼（log 用）"},
         "thanks_id": {"type": "integer", "description": "感謝記錄 ID（done 用）"}
     }, "required": ["action"]}},

    {"name": "office_eod",
     "description":
        "下班收尾報告：整合今天未關閉的承諾、待辦、感謝欠債、明日提醒。"
        "主人說「今天差不多了」「幫我收尾」「下班前整理一下」「快下班了」時使用。",
     "input_schema": {"type": "object", "properties": {
         "mode": {"type": "string", "enum": ["wrap","tomorrow_prep"],
                  "description": "wrap=今日收尾總結, tomorrow_prep=明日預備清單"}
     }, "required": []}},

    {"name": "office_manager_lens",
     "description":
        "主管視角：一鍵看到整個團隊的狀態——deadline 壓力、深夜會議負擔、承諾未兌現的下屬。"
        "主人說「幫我看看團隊狀況」「誰最近壓力大」「我答應過誰什麼」時使用。",
     "input_schema": {"type": "object", "properties": {
         "focus": {"type": "string",
                   "enum": ["overview","deadline_pressure","timezone_fatigue","open_promises"],
                   "description": "overview=整體狀況 / deadline_pressure=截止壓力 / timezone_fatigue=時區疲勞 / open_promises=未兌現承諾"}
     }, "required": []}},

    {"name": "office_onboarding",
     "description":
        "新人引導助理：產生客製入職計畫、追蹤進度、主動提示接下來要做什麼。"
        "新人到職→action=add_hire；查某人入職進度→action=progress；"
        "標記任務完成→action=complete_task；為職位生成30天計畫→action=generate_plan。",
     "input_schema": {"type": "object", "properties": {
         "action":       {"type": "string", "enum": ["add_hire","progress","complete_task","generate_plan"]},
         "colleague_id": {"type": "integer", "description": "同事 ID（progress/complete_task 用）"},
         "task_id":      {"type": "integer", "description": "任務 ID（complete_task 用）"},
         "role":         {"type": "string",  "description": "職位描述（generate_plan 用）"}
     }, "required": ["action"]}},

    {"name": "office_wellness",
     "description":
        "辦公室健康感知：依 GPS 靜止時間推斷久坐狀況並建議活動，或查今日整體活動量。"
        "主人問「我今天動了多少」「好久沒動了」「提醒我站起來」時使用。",
     "input_schema": {"type": "object", "properties": {
         "action": {"type": "string", "enum": ["sitting_check","daily_summary"]}
     }, "required": ["action"]}},
]

# ── Tool Handlers ──────────────────────────────────────────────────────────
def handle_office_room(inp: dict, c) -> tuple:
    """回傳 (res_text, card_or_None)"""
    action = inp.get("action", "status")
    now_iso = datetime.now().isoformat()
    card = None

    if action == "add":
        name = inp.get("room_name") or inp.get("name", "")
        if not name:
            return "請告訴我會議室名稱。", None
        cap = inp.get("capacity", 4)
        floor_ = inp.get("floor", "")
        c.execute("INSERT OR IGNORE INTO office_rooms (name,capacity,floor,notes) VALUES (?,?,?,'')",
                  (name, cap, floor_))
        return f"已新增會議室「{name}」（{floor_ or '未填樓層'}，容納 {cap} 人）。", None

    elif action == "book":
        room_name = inp.get("room_name", "")
        title = inp.get("title", "會議")
        start = inp.get("start_time", now_iso[:16])
        end   = inp.get("end_time", "")
        att   = inp.get("attendees", "")
        room = c.execute("SELECT id FROM office_rooms WHERE name LIKE ?", (f"%{room_name}%",)).fetchone()
        room_id = room[0] if room else None
        c.execute(
            "INSERT INTO office_bookings (room_id,title,booked_by,start_time,end_time,attendees,ts) "
            "VALUES (?,?,?,?,?,?,?)",
            (room_id, title, "me", start, end, att, now_iso)
        )
        bid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        return (f"已為「{title}」預訂{'「'+room_name+'」' if room_name else '會議室'}，"
                f"{'時間 '+start[:16]+' → '+end[:16] if end else '時間 '+start[:16]}。"
                f"（訂房 ID：{bid}，到場請告訴我打卡）"), None

    elif action == "checkin":
        bid = inp.get("booking_id")
        if bid:
            c.execute("UPDATE office_bookings SET checked_in=1, check_in_time=? WHERE id=?",
                      (now_iso, bid))
            return f"訂房 {bid} 打卡完成，已記錄到場時間。", None
        # 找最近的未打卡訂房
        row = c.execute(
            "SELECT id,title,start_time FROM office_bookings "
            "WHERE checked_in=0 AND released=0 AND date(start_time)=date('now') "
            "ORDER BY start_time LIMIT 1"
        ).fetchone()
        if row:
            c.execute("UPDATE office_bookings SET checked_in=1, check_in_time=? WHERE id=?",
                      (now_iso, row[0]))
            return f"「{row[1]}」（{row[2][:16]}）打卡完成。", None
        return "找不到今天未打卡的訂房，請確認訂房 ID。", None

    elif action == "release":
        bid = inp.get("booking_id")
        if bid:
            c.execute("UPDATE office_bookings SET released=1 WHERE id=?", (bid,))
            row = c.execute("SELECT title FROM office_bookings WHERE id=?", (bid,)).fetchone()
            title = row[0] if row else str(bid)
            return f"「{title}」的會議室已釋出，其他人可以使用了。", None
        return "請提供要釋出的訂房 ID。", None

    elif action == "status":
        rooms = c.execute("SELECT id,name,capacity,floor FROM office_rooms").fetchall()
        if not rooms:
            return "目前尚未設定任何會議室，可以說「新增會議室 OO」開始設定。", None
        now_str = datetime.now().strftime("%Y-%m-%dT%H:%M")
        lines = ["目前會議室狀況："]
        for rid, rname, cap, floor_ in rooms:
            active = c.execute(
                "SELECT title,start_time,end_time,checked_in FROM office_bookings "
                "WHERE room_id=? AND released=0 AND start_time<=? AND (end_time>=? OR end_time='') "
                "ORDER BY start_time LIMIT 1",
                (rid, now_str, now_str)
            ).fetchone()
            if active:
                ci = "✅已打卡" if active[3] else "⚠️未打卡"
                lines.append(f"• {rname}（{floor_ or '?'}F，{cap}人）— 使用中：{active[0]} {ci}")
            else:
                lines.append(f"• {rname}（{floor_ or '?'}F，{cap}人）— 空閒")
        card = {"title": "會議室現況", "content": "\n".join(lines), "type": "info"}
        return "\n".join(lines), card

    return "未知 action", None


def handle_office_supply(inp: dict, c) -> tuple:
    action = inp.get("action", "list")
    now_iso = datetime.now().isoformat()
    card = None

    if action == "add":
        item = inp.get("item", "")
        if not item:
            return "請告訴我耗材名稱。", None
        qty   = inp.get("quantity", 0)
        thr   = inp.get("threshold", 1)
        cat   = inp.get("category", "辦公")
        unit  = inp.get("unit", "個")
        url   = inp.get("buy_url", "")
        c.execute(
            "INSERT INTO office_supplies (item,category,quantity,threshold,unit,buy_url) VALUES (?,?,?,?,?,?)",
            (item, cat, qty, thr, unit, url)
        )
        status = "⚠️ 已低於門檻" if qty <= thr else "✅ 庫存正常"
        return f"已新增「{item}」（{qty}{unit}，門檻 {thr}{unit}）{status}。", None

    elif action == "update":
        item = inp.get("item", "")
        qty  = inp.get("quantity")
        if qty is None:
            return "請告訴我更新後的數量。", None
        row = c.execute("SELECT id,threshold,unit FROM office_supplies WHERE item LIKE ?",
                        (f"%{item}%",)).fetchone()
        if not row:
            return f"找不到「{item}」，請先新增。", None
        c.execute("UPDATE office_supplies SET quantity=? WHERE id=?", (qty, row[0]))
        warn = "⚠️ 已低於門檻，建議補貨！" if qty <= row[1] else ""
        return f"「{item}」庫存已更新為 {qty}{row[2]}。{warn}", None

    elif action == "low":
        rows = c.execute(
            "SELECT item,quantity,threshold,unit,buy_url FROM office_supplies WHERE quantity<=threshold ORDER BY quantity"
        ).fetchall()
        if not rows:
            return "目前所有耗材庫存充足，不需要補貨。", None
        lines = ["以下耗材需要補貨："]
        for item, qty, thr, unit, url in rows:
            u = url or "（無連結）"
            lines.append(f"• {item}：剩 {qty}{unit}（門檻 {thr}{unit}） → {u}")
        card = {"title": "需補貨清單", "content": "\n".join(lines), "type": "warning"}
        return "\n".join(lines), card

    elif action == "order":
        item  = inp.get("item", "")
        oqty  = inp.get("order_qty", 1)
        row = c.execute("SELECT id,unit FROM office_supplies WHERE item LIKE ?",
                        (f"%{item}%",)).fetchone()
        if not row:
            return f"找不到「{item}」。", None
        c.execute("INSERT INTO office_supply_orders (supply_id,quantity,ordered_at,status) VALUES (?,?,?,'ordered')",
                  (row[0], oqty, now_iso))
        c.execute("UPDATE office_supplies SET last_ordered=? WHERE id=?", (now_iso[:10], row[0]))
        return f"已記錄「{item}」訂購 {oqty}{row[1]}，今天 {now_iso[:10]}。", None

    elif action == "list":
        rows = c.execute(
            "SELECT item,quantity,threshold,unit,category FROM office_supplies ORDER BY category,item"
        ).fetchall()
        if not rows:
            return "尚未設定任何耗材，可以說「新增耗材 XX 數量 Y」開始追蹤。", None
        lines = ["辦公室耗材庫存："]
        for item, qty, thr, unit, cat in rows:
            icon = "⚠️" if qty <= thr else "✅"
            lines.append(f"{icon} [{cat}] {item}：{qty}{unit}（門檻 {thr}{unit}）")
        card = {"title": "耗材庫存", "content": "\n".join(lines), "type": "info"}
        return "\n".join(lines), card

    return "未知 action", None


def handle_office_colleague(inp: dict, c, _simple_chat_fn=None) -> tuple:
    action = inp.get("action", "list")
    now_iso = datetime.now().isoformat()
    card = None

    if action == "add":
        name = inp.get("name", "")
        if not name:
            return "請告訴我同事名字。", None
        role  = inp.get("role", "")
        dept  = inp.get("dept", "")
        tz    = inp.get("timezone", "Asia/Taipei")
        jdate = inp.get("joined_date", "")
        slack = inp.get("slack_handle", "")
        email = inp.get("email", "")
        notes = inp.get("notes", "")
        c.execute(
            "INSERT INTO office_colleagues (name,role,dept,timezone,joined_date,slack_handle,email,notes,added_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (name, role, dept, tz, jdate, slack, email, notes, now_iso)
        )
        return (f"已加入同事「{name}」" +
                (f"（{role}，{dept}）" if role or dept else "") +
                ("，非台北時區，跨時區疲勞監測已啟動。" if tz != "Asia/Taipei" else "。")), None

    elif action == "activity":
        name = inp.get("name", "")
        atype = inp.get("activity_type", "message")
        row = c.execute("SELECT id FROM office_colleagues WHERE name LIKE ?",
                        (f"%{name}%",)).fetchone()
        if not row:
            return f"找不到同事「{name}」，請先用 action=add 新增。", None
        c.execute("INSERT INTO colleague_activity (colleague_id,activity_type,ts) VALUES (?,?,?)",
                  (row[0], atype, now_iso))
        return f"已記錄與「{name}」的互動（{atype}）。", None

    elif action == "silence":
        days = inp.get("silence_days", 5)
        threshold_ts = (datetime.now() - timedelta(days=days)).isoformat()
        colleagues = c.execute("SELECT id,name,role,dept FROM office_colleagues").fetchall()
        silent = []
        for cid, cname, role_, dept_ in colleagues:
            last = c.execute(
                "SELECT ts FROM colleague_activity WHERE colleague_id=? ORDER BY ts DESC LIMIT 1",
                (cid,)
            ).fetchone()
            if not last or last[0] < threshold_ts:
                days_ago = "（從未有互動記錄）"
                if last:
                    try:
                        diff = (datetime.now() - datetime.fromisoformat(last[0])).days
                        days_ago = f"（{diff} 天前）"
                    except:
                        pass
                silent.append(f"• {cname}" + (f"（{role_}）" if role_ else "") + f" — 最後互動 {days_ago}")
        if not silent:
            return f"過去 {days} 天內，所有同事都有互動記錄，沒有沉默者。", None
        lines = [f"超過 {days} 天沒有互動的同事："] + silent
        card = {"title": "沉默偵測", "content": "\n".join(lines), "type": "warning"}
        return "\n".join(lines), card

    elif action == "expertise":
        query = inp.get("query", "")
        if not query:
            return "請告訴我要找哪個領域的專長。", None
        # 從 notes、meeting_notes、memories 找
        colleagues = c.execute("SELECT id,name,role,notes FROM office_colleagues").fetchall()
        matches = []
        for cid, cname, role_, notes_ in colleagues:
            score = 0
            if notes_ and query.lower() in notes_.lower():
                score += 3
            if role_ and query.lower() in role_.lower():
                score += 2
            # 查 meeting_notes
            mn = c.execute(
                "SELECT COUNT(*) FROM meeting_notes WHERE (summary LIKE ? OR transcript LIKE ?) AND ts > date('now','-90 day')",
                (f"%{cname}%{query}%", f"%{cname}%{query}%")
            ).fetchone()
            if mn and mn[0] > 0:
                score += mn[0]
            if score > 0:
                matches.append((score, cname, role_ or "", notes_ or ""))
        matches.sort(key=lambda x: -x[0])
        if not matches:
            return f"在同事資料與會議記錄中找不到「{query}」相關的明確專長，試試用更具體的關鍵字。", None
        lines = [f"「{query}」相關專長推薦："]
        for sc, cname, role_, notes_ in matches[:3]:
            hint = notes_[:60] + "…" if len(notes_) > 60 else notes_
            lines.append(f"• {cname}（{role_}）— {hint or '（依職稱推斷）'}")
        return "\n".join(lines), None

    elif action == "list":
        rows = c.execute(
            "SELECT name,role,dept,timezone,joined_date FROM office_colleagues ORDER BY dept,name"
        ).fetchall()
        if not rows:
            return "尚未登記任何同事，可以說「新增同事 OO，職稱 XX」開始建立名單。", None
        lines = ["同事名單："]
        for name, role_, dept_, tz_, jdate_ in rows:
            tz_tag = f" 🌐{tz_}" if tz_ and tz_ != "Asia/Taipei" else ""
            lines.append(f"• {name}" + (f"（{role_}，{dept_}）" if role_ or dept_ else "") + tz_tag)
        card = {"title": "同事名單", "content": "\n".join(lines), "type": "info"}
        return "\n".join(lines), card

    return "未知 action", None


def handle_office_thanks(inp: dict, c) -> tuple:
    action = inp.get("action", "pending")
    now_iso = datetime.now().isoformat()

    if action == "log":
        person = inp.get("to_person", "")
        reason = inp.get("reason", "")
        if not person:
            return "請告訴我是誰幫了你。", None
        c.execute("INSERT INTO thanks_log (to_person,reason,ts) VALUES (?,?,?)",
                  (person, reason, now_iso))
        return f"已記下「{person}」幫了你（{reason or '原因待補'}），EOD 時我會提醒你致謝。", None

    elif action == "pending":
        rows = c.execute(
            "SELECT id,to_person,reason,ts FROM thanks_log WHERE thanked=0 ORDER BY ts"
        ).fetchall()
        if not rows:
            return "目前沒有待致謝的人，你都謝得很到位。", None
        lines = ["還沒謝到的人："]
        for tid, person, reason, ts in rows:
            when = ts[:10] if ts else ""
            lines.append(f"• [ID:{tid}] {person} — {reason or '（原因未記）'}（{when}）")
        return "\n".join(lines), None

    elif action == "done":
        tid = inp.get("thanks_id")
        if tid:
            c.execute("UPDATE thanks_log SET thanked=1 WHERE id=?", (tid,))
            row = c.execute("SELECT to_person FROM thanks_log WHERE id=?", (tid,)).fetchone()
            name = row[0] if row else str(tid)
            return f"已記錄對「{name}」的致謝，很好。", None
        # 批次標記
        c.execute("UPDATE thanks_log SET thanked=1 WHERE thanked=0")
        return "已將所有待謝項目標記為完成。", None

    return "未知 action", None


def handle_office_eod(inp: dict, c, _simple_chat_fn=None) -> tuple:
    mode = inp.get("mode", "wrap")
    today = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%H:%M")
    card = None

    # 收集資料
    pending_todos = c.execute(
        "SELECT title,due_date FROM todos WHERE status='pending' ORDER BY ts DESC LIMIT 10"
    ).fetchall()
    open_promises = c.execute(
        "SELECT to_whom,content,deadline FROM promises WHERE status='pending' ORDER BY noted_at"
    ).fetchall()
    pending_thanks = c.execute(
        "SELECT to_person,reason FROM thanks_log WHERE thanked=0"
    ).fetchall()
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow_events = c.execute(
        "SELECT title,event_time FROM calendar_events WHERE event_date=? ORDER BY event_time",
        (tomorrow,)
    ).fetchall()
    low_supplies = c.execute(
        "SELECT item,quantity,unit FROM office_supplies WHERE quantity<=threshold"
    ).fetchall()
    sub_commits = c.execute(
        "SELECT s.name,sc.content,sc.deadline FROM subordinate_commits sc "
        "JOIN subordinates s ON sc.sub_id=s.id WHERE sc.status='pending' ORDER BY sc.deadline"
    ).fetchall()

    sections = [f"【下班收尾 {today} {now_str}】\n"]

    if open_promises:
        sections.append("📌 未履行承諾：")
        for whom, content, deadline in open_promises:
            sections.append(f"  • 對 {whom}：{content}" + (f"（{deadline}）" if deadline else ""))

    if pending_thanks:
        sections.append("\n🙏 待感謝的人：")
        for person, reason in pending_thanks:
            sections.append(f"  • {person} — {reason or '（未記原因）'}")

    if pending_todos:
        sections.append("\n☐ 未完成待辦：")
        for title, due in pending_todos[:5]:
            sections.append(f"  • {title}" + (f"（{due}）" if due else ""))

    if tomorrow_events:
        sections.append(f"\n📅 明天行程：")
        for title, etime in tomorrow_events:
            sections.append(f"  • {etime or '全天'} {title}")

    if sub_commits:
        sections.append("\n👥 你對下屬的承諾未兌現：")
        for sname, content, deadline in sub_commits[:3]:
            sections.append(f"  • 對 {sname}：{content}" + (f"（{deadline}）" if deadline else ""))

    if low_supplies:
        sections.append("\n📦 耗材快沒了：")
        for item, qty, unit in low_supplies:
            sections.append(f"  • {item}（剩 {qty}{unit}）")

    if len(sections) == 1:
        summary = "今天乾淨收尾，沒有未了結的事。辛苦了，好好休息。"
        return summary, None

    report = "\n".join(sections)
    card = {"title": "下班收尾", "content": report, "type": "summary"}
    urgent = sum([len(open_promises), len(pending_thanks)])
    msg = f"主人，{now_str} 了，幫你整理今天的收尾：\n\n"
    if open_promises:
        msg += f"承諾還有 {len(open_promises)} 件沒完成"
    if pending_thanks:
        msg += f"{'，' if open_promises else ''}還有 {len(pending_thanks)} 個人等你說謝謝"
    if pending_todos:
        msg += f"，{len(pending_todos)} 件待辦還開著"
    msg += "。詳細報告已顯示在畫面上。\n\n要我現在幫你做什麼，還是明天繼續？"
    return msg, card


def handle_office_manager_lens(inp: dict, c, _simple_chat_fn=None) -> tuple:
    focus = inp.get("focus", "overview")
    today = datetime.now().strftime("%Y-%m-%d")
    card = None

    if focus in ("overview", None, ""):
        # 整體報告
        parts = []

        # 下屬數量與最近1on1
        subs = c.execute(
            "SELECT name,role,last_1on1 FROM subordinates ORDER BY name"
        ).fetchall()
        if subs:
            parts.append(f"你有 {len(subs)} 位直屬：")
            for name, role_, last1 in subs:
                days_since = ""
                if last1:
                    try:
                        d = (datetime.now() - datetime.fromisoformat(last1)).days
                        days_since = f"（上次 1:1：{d} 天前）"
                    except:
                        pass
                parts.append(f"  • {name}（{role_ or '?'}）{days_since}")

        # 未兌現承諾
        commits = c.execute(
            "SELECT s.name,sc.content,sc.deadline FROM subordinate_commits sc "
            "JOIN subordinates s ON sc.sub_id=s.id WHERE sc.status='pending'",
        ).fetchall()
        if commits:
            parts.append(f"\n你對下屬有 {len(commits)} 個未兌現承諾：")
            for sname, content, deadline in commits[:5]:
                parts.append(f"  • 對 {sname}：{content}" + (f"（{deadline}）" if deadline else ""))

        # 沉默偵測
        threshold_ts = (datetime.now() - timedelta(days=5)).isoformat()
        silent_subs = []
        for sid, sname, _ in [(s[0] if len(s) > 0 else None, s[0], s[1]) for s in c.execute(
            "SELECT id,name FROM subordinates"
        ).fetchall()]:
            sid_row = c.execute("SELECT id FROM subordinates WHERE name=?", (sname,)).fetchone()
            if not sid_row:
                continue
            last_act = c.execute(
                "SELECT ts FROM colleague_activity WHERE colleague_id=? ORDER BY ts DESC LIMIT 1",
                (sid_row[0],)
            ).fetchone()
            if not last_act or last_act[0] < threshold_ts:
                silent_subs.append(sname)
        if silent_subs:
            parts.append(f"\n⚠️ 超過 5 天沒互動記錄：{', '.join(silent_subs)}")

        if not parts:
            return "尚未設定任何下屬資料。可以說「新增下屬 OO，職稱 XX」開始建立團隊。", None

        report = "【主管視角 — 今日摘要】\n" + "\n".join(parts)
        card = {"title": "主管視角", "content": report, "type": "summary"}
        return report, card

    elif focus == "deadline_pressure":
        # 查各下屬今日/明日的截止任務
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        rows = c.execute(
            "SELECT title,due_date,status FROM todos WHERE status='pending' "
            "AND due_date<=? ORDER BY due_date",
            (tomorrow,)
        ).fetchall()
        if not rows:
            return "未來兩天沒有明確截止的待辦事項。", None
        lines = ["截止壓力（今明兩天）："]
        for title, due, _ in rows:
            lines.append(f"• [{due}] {title}")
        return "\n".join(lines), None

    elif focus == "timezone_fatigue":
        # 分析 calendar_events 中的跨時區深夜會議
        deep_night_events = c.execute(
            "SELECT title,event_date,event_time FROM calendar_events "
            "WHERE event_time < '08:00' OR event_time > '21:00' "
            "AND event_date >= date('now','-30 day') "
            "ORDER BY event_date DESC LIMIT 20"
        ).fetchall()
        if not deep_night_events:
            return "過去 30 天內，沒有明顯的深夜或清晨會議記錄。", None
        lines = [f"過去 30 天深夜/清晨會議（共 {len(deep_night_events)} 場）："]
        for title, edate, etime in deep_night_events[:10]:
            lines.append(f"• {edate} {etime} — {title}")
        if len(deep_night_events) >= 5:
            lines.append(f"\n⚠️ 建議主人評估是否需要輪流分擔跨時區會議，避免長期疲勞。")
        return "\n".join(lines), None

    elif focus == "open_promises":
        rows = c.execute(
            "SELECT to_whom,content,deadline,noted_at FROM promises WHERE status='pending' ORDER BY deadline"
        ).fetchall()
        if not rows:
            return "目前沒有未履行的承諾，乾淨。", None
        lines = [f"未履行承諾（共 {len(rows)} 件）："]
        for whom, content, deadline, noted in rows:
            age = ""
            if noted:
                try:
                    age = f"，{(datetime.now()-datetime.fromisoformat(noted)).days} 天前說的"
                except:
                    pass
            lines.append(f"• 對 {whom}：{content}" +
                          (f"（截止 {deadline}）" if deadline else "") + age)
        card = {"title": "未兌現承諾", "content": "\n".join(lines), "type": "warning"}
        return "\n".join(lines), card

    return "未知 focus", None


def handle_office_onboarding(inp: dict, c, _simple_chat_fn=None) -> tuple:
    action = inp.get("action", "progress")
    now_iso = datetime.now().isoformat()

    if action == "add_hire":
        cid = inp.get("colleague_id")
        role_ = inp.get("role", "")
        if not cid:
            return "請先用 office_colleague action=add 新增同事，再用 colleague_id 開啟入職引導。", None
        row = c.execute("SELECT name,joined_date FROM office_colleagues WHERE id=?", (cid,)).fetchone()
        if not row:
            return f"找不到 ID={cid} 的同事。", None
        cname, jdate = row
        # 自動生成預設入職任務（30 天計畫）
        default_tasks = [
            (1,  "認識主要團隊成員，參加所有當週會議"),
            (2,  "完成系統存取設定（帳號、工具、文件權限）"),
            (3,  "與主管完成第一次 1:1，對齊期待與目標"),
            (5,  "熟讀核心文件（產品/流程/架構）"),
            (7,  "完成第一個小任務或 PR"),
            (14, "與每位直接合作的同事各自聊過一次"),
            (21, "提交一份入職三週心得給主管"),
            (30, "完成第一個月主要交付物，與主管回顧"),
        ]
        for day, task in default_tasks:
            c.execute(
                "INSERT INTO onboarding_tasks (colleague_id,task,due_day) VALUES (?,?,?)",
                (cid, task, day)
            )
        return (f"已為「{cname}」建立 {len(default_tasks)} 項入職任務（30 天計畫）。"
                f"{'到職日：'+jdate+'。' if jdate else ''}"
                f"可以問我「{cname} 的入職進度」隨時追蹤。"), None

    elif action == "progress":
        cid = inp.get("colleague_id")
        if not cid:
            # 查所有人
            cols = c.execute("SELECT id,name FROM office_colleagues").fetchall()
            if not cols:
                return "目前沒有同事資料。", None
            cid_rows = [(r[0], r[1]) for r in cols if c.execute(
                "SELECT COUNT(*) FROM onboarding_tasks WHERE colleague_id=?", (r[0],)
            ).fetchone()[0] > 0]
            if not cid_rows:
                return "目前沒有任何同事有入職任務。", None
            lines = ["入職進度概覽："]
            for cid_, cname_ in cid_rows:
                total = c.execute("SELECT COUNT(*) FROM onboarding_tasks WHERE colleague_id=?", (cid_,)).fetchone()[0]
                done = c.execute("SELECT COUNT(*) FROM onboarding_tasks WHERE colleague_id=? AND completed_at IS NOT NULL", (cid_,)).fetchone()[0]
                lines.append(f"• {cname_}：{done}/{total} 完成")
            return "\n".join(lines), None
        row = c.execute("SELECT name,joined_date FROM office_colleagues WHERE id=?", (cid,)).fetchone()
        if not row:
            return f"找不到 ID={cid} 的同事。", None
        cname, jdate = row
        tasks = c.execute(
            "SELECT id,task,due_day,completed_at FROM onboarding_tasks WHERE colleague_id=? ORDER BY due_day",
            (cid,)
        ).fetchall()
        if not tasks:
            return f"「{cname}」尚未有入職任務，說「{cname} 開始入職引導」幫他建立計畫。", None
        done_count = sum(1 for t in tasks if t[3])
        lines = [f"「{cname}」入職進度（{done_count}/{len(tasks)}）："]
        for tid, task, day, completed in tasks:
            icon = "✅" if completed else f"☐（Day {day}）"
            lines.append(f"  {icon} {task}")
        return "\n".join(lines), None

    elif action == "complete_task":
        task_id = inp.get("task_id")
        if not task_id:
            return "請提供要完成的任務 ID。", None
        c.execute("UPDATE onboarding_tasks SET completed_at=? WHERE id=?", (now_iso, task_id))
        row = c.execute("SELECT task FROM onboarding_tasks WHERE id=?", (task_id,)).fetchone()
        task_name = row[0] if row else str(task_id)
        return f"入職任務完成：「{task_name}」。", None

    elif action == "generate_plan":
        role_ = inp.get("role", "")
        if not role_ and _simple_chat_fn:
            return "請提供職位描述，讓我生成客製化入職計畫。", None
        if _simple_chat_fn and role_:
            prompt = (f"請為「{role_}」職位設計一份 30 天入職計畫，"
                      "輸出繁中清單，格式：Day X — 任務。共 8-10 項，涵蓋人際、工具、交付物三個面向。")
            plan = _simple_chat_fn(prompt, max_tokens=800)
            return plan, {"title": f"入職計畫：{role_}", "content": plan, "type": "document"}
        return "請提供職位描述。", None

    return "未知 action", None


def handle_office_wellness(inp: dict, c) -> tuple:
    action = inp.get("action", "sitting_check")

    if action == "sitting_check":
        # 依 GPS 靜止時間推斷久坐
        two_hours_ago = (datetime.now() - timedelta(hours=2)).isoformat()
        recent_locs = c.execute(
            "SELECT lat,lng,ts FROM location_log WHERE ts>? ORDER BY ts DESC",
            (two_hours_ago,)
        ).fetchall()
        if len(recent_locs) < 3:
            return "位置資料不足，無法判斷久坐狀況。請確認位置授權已開啟。", None
        # 計算位移
        lats = [r[0] for r in recent_locs if r[0]]
        lngs = [r[1] for r in recent_locs if r[1]]
        if not lats or not lngs:
            return "位置資料缺失，無法分析。", None
        lat_range = max(lats) - min(lats)
        lng_range = max(lngs) - min(lngs)
        is_stationary = lat_range < 0.001 and lng_range < 0.001  # ~100m
        if is_stationary:
            # 找第一筆靜止時間
            earliest = recent_locs[-1][2] if recent_locs else ""
            return (f"主人，你過去兩小時幾乎沒有移動。"
                    f"站起來走走吧，三分鐘就夠——倒杯水，或是走到窗邊看一眼外面。"), None
        return "過去兩小時你有移動記錄，活動量還不錯。繼續保持。", None

    elif action == "daily_summary":
        today_start = datetime.now().strftime("%Y-%m-%d") + "T00:00:00"
        places = c.execute(
            "SELECT name,duration_min FROM place_history WHERE arrived_at>? ORDER BY duration_min DESC",
            (today_start,)
        ).fetchall()
        workouts = c.execute(
            "SELECT workout_type,duration_min FROM workouts WHERE ts>? ORDER BY ts DESC LIMIT 3",
            (today_start,)
        ).fetchall()
        loc_count = c.execute(
            "SELECT COUNT(*) FROM location_log WHERE ts>?", (today_start,)
        ).fetchone()[0]
        lines = ["今日活動摘要："]
        if workouts:
            for wt, dur in workouts:
                lines.append(f"• 運動：{wt} {dur or '?'}分鐘")
        if places:
            for pname, pdur in places[:3]:
                lines.append(f"• 停留：{pname or '未知地點'} {pdur or '?'}分鐘")
        lines.append(f"• 位置更新次數：{loc_count} 次")
        if loc_count < 20:
            lines.append("⚠️ 今天移動較少，建議晚上出去走走。")
        return "\n".join(lines), None

    return "未知 action", None


# ── REST 端點輔助函數 ──────────────────────────────────────────────────────────
def get_room_pulse_data(c):
    """找出訂了但 20 分鐘後仍未打卡的會議室。"""
    threshold = (datetime.now() - timedelta(minutes=20)).isoformat()
    rows = c.execute(
        "SELECT b.id,b.title,b.start_time,r.name "
        "FROM office_bookings b LEFT JOIN office_rooms r ON b.room_id=r.id "
        "WHERE b.checked_in=0 AND b.released=0 AND b.start_time<=? AND date(b.start_time)=date('now') "
        "ORDER BY b.start_time",
        (threshold,)
    ).fetchall()
    return [{"booking_id": r[0], "title": r[1], "start_time": r[2], "room": r[3]} for r in rows]


def get_eod_summary_data(c):
    today = datetime.now().strftime("%Y-%m-%d")
    return {
        "pending_todos":   c.execute("SELECT COUNT(*) FROM todos WHERE status='pending'").fetchone()[0],
        "open_promises":   c.execute("SELECT COUNT(*) FROM promises WHERE status='pending'").fetchone()[0],
        "pending_thanks":  c.execute("SELECT COUNT(*) FROM thanks_log WHERE thanked=0").fetchone()[0],
        "low_supplies":    c.execute("SELECT COUNT(*) FROM office_supplies WHERE quantity<=threshold").fetchone()[0],
        "open_sub_commits":c.execute("SELECT COUNT(*) FROM subordinate_commits WHERE status='pending'").fetchone()[0],
    }
