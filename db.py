# db.py
import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional

DB_NAME = "events.db"


def get_connection() -> sqlite3.Connection:
    """Mở kết nối tới database SQLite."""
    return sqlite3.connect(DB_NAME)


def init_db() -> None:
    """Tạo bảng events nếu chưa tồn tại."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            start_time TEXT NOT NULL,  -- ISO string
            end_time TEXT,             -- ISO string hoặc NULL
            location TEXT,
            reminder_minutes INTEGER DEFAULT 10,
            notified INTEGER DEFAULT 0 -- 0: chưa nhắc, 1: đã nhắc
        );
    """)
    conn.commit()
    conn.close()


# ==========================
# THÊM / SỬA / XÓA / LẤY 1 SỰ KIỆN
# ==========================

def add_event(event: Dict) -> int:
    """
    Thêm 1 sự kiện vào database.
    event là dict dạng:
    {
        "event": "họp nhóm",
        "start_time": "2025-11-01T10:00:00",
        "end_time": None,
        "location": "phòng 302",
        "reminder_minutes": 15
    }
    Trả về id của event vừa thêm.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO events (title, start_time, end_time, location, reminder_minutes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            event.get("event"),
            event.get("start_time"),
            event.get("end_time"),
            event.get("location"),
            event.get("reminder_minutes", 10),
        ),
    )
    conn.commit()
    event_id = cur.lastrowid
    conn.close()
    return event_id


def update_event(event_id: int, **fields) -> None:
    """
    Cập nhật 1 sự kiện theo id.
    Ví dụ:
        update_event(1, title="Họp nhóm môn AI", location="phòng 101")
    """
    if not fields:
        return

    allowed_fields = {"title", "start_time", "end_time", "location", "reminder_minutes", "notified"}
    set_clauses = []
    values = []

    for key, value in fields.items():
        if key in allowed_fields:
            set_clauses.append(f"{key} = ?")
            values.append(value)

    if not set_clauses:
        return

    values.append(event_id)

    conn = get_connection()
    cur = conn.cursor()
    sql = f"UPDATE events SET {', '.join(set_clauses)} WHERE id = ?"
    cur.execute(sql, values)
    conn.commit()
    conn.close()


def delete_event(event_id: int) -> None:
    """Xóa 1 sự kiện theo id."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()


def get_event(event_id: int) -> Optional[Dict]:
    """Lấy thông tin 1 sự kiện theo id. Trả về dict hoặc None."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, start_time, end_time, location, reminder_minutes, notified
        FROM events
        WHERE id = ?
    """, (event_id,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "id": row[0],
        "title": row[1],
        "start_time": row[2],
        "end_time": row[3],
        "location": row[4],
        "reminder_minutes": row[5],
        "notified": row[6],
    }


# ==========================
# HÀM LẤY SỰ KIỆN THEO NGÀY / TUẦN / THÁNG
# ==========================

def _rows_to_events(rows) -> List[Dict]:
    events = []
    for row in rows:
        events.append({
            "id": row[0],
            "title": row[1],
            "start_time": row[2],
            "end_time": row[3],
            "location": row[4],
            "reminder_minutes": row[5],
            "notified": row[6],
        })
    return events


def get_events_between(start_dt: datetime, end_dt: datetime) -> List[Dict]:
    """Lấy các sự kiện có start_time trong [start_dt, end_dt)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, start_time, end_time, location, reminder_minutes, notified
        FROM events
        WHERE start_time >= ? AND start_time < ?
        ORDER BY start_time ASC
    """, (start_dt.isoformat(), end_dt.isoformat()))
    rows = cur.fetchall()
    conn.close()
    return _rows_to_events(rows)


def get_events_by_day(day: datetime) -> List[Dict]:
    """Lấy sự kiện trong 1 ngày (từ 00:00 đến 23:59)."""
    start_dt = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(days=1)
    return get_events_between(start_dt, end_dt)


def get_events_by_week(start_of_week: datetime) -> List[Dict]:
    """
    Lấy sự kiện trong 1 tuần.
    start_of_week: ngày đầu tuần (ví dụ thứ Hai).
    """
    start_dt = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(days=7)
    return get_events_between(start_dt, end_dt)


def get_events_by_month(year: int, month: int) -> List[Dict]:
    """Lấy sự kiện trong 1 tháng (dựa trên year, month)."""
    start_dt = datetime(year, month, 1)
    # tính tháng sau
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)

    return get_events_between(start_dt, next_month)


# ==========================
# TÌM KIẾM THEO TỪ KHÓA
# ==========================

def search_events(keyword: str) -> List[Dict]:
    """Tìm sự kiện theo từ khóa trong title hoặc location."""
    kw = f"%{keyword}%"
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, start_time, end_time, location, reminder_minutes, notified
        FROM events
        WHERE title LIKE ? OR location LIKE ?
        ORDER BY start_time ASC
    """, (kw, kw))
    rows = cur.fetchall()
    conn.close()
    return _rows_to_events(rows)



def export_all_events_to_json(filepath: str) -> None:
    """
    Xuất toàn bộ sự kiện trong database ra file JSON.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, start_time, end_time, location, reminder_minutes, notified
        FROM events
        ORDER BY start_time ASC
    """)
    rows = cur.fetchall()
    conn.close()

    events = []
    for row in rows:
        events.append({
            "id": row[0],
            "title": row[1],
            "start_time": row[2],
            "end_time": row[3],
            "location": row[4],
            "reminder_minutes": row[5],
            "notified": row[6]
        })

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=4)

# ==========================
# TEST NHANH
# ==========================

if __name__ == "__main__":
    # Khởi tạo bảng
    init_db()
    print("Đã tạo (hoặc kiểm tra) bảng events trong", DB_NAME)

    # Test thêm 1 sự kiện mẫu
    sample_event = {
        "event": "họp nhóm đồ án",
        "start_time": datetime.now().isoformat(timespec="seconds"),
        "end_time": None,
        "location": "phòng 302",
        "reminder_minutes": 15,
    }
    new_id = add_event(sample_event)
    print("Đã thêm sự kiện id =", new_id)

    # Lấy lại sự kiện vừa thêm
    evt = get_event(new_id)
    print("Chi tiết sự kiện:", evt)

    
def get_upcoming_events(now: datetime):
    """
    Lấy các sự kiện chưa nhắc, có start_time nằm trong khoảng
    now -> now + 1 giờ (dự phòng).
    """
    conn = get_connection()
    cur = conn.cursor()

    # Lấy các event chưa nhắc
    cur.execute("""
        SELECT id, title, start_time, end_time, location, reminder_minutes, notified
        FROM events
        WHERE notified = 0
        ORDER BY start_time ASC
    """)

    rows = cur.fetchall()
    conn.close()
    return _rows_to_events(rows)

