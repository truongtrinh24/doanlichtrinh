# nlp_module.py
import re
from datetime import datetime, timedelta
from dateutil import parser as dateparser
from underthesea import word_tokenize


# ==========================
# TIỀN XỬ LÝ
# ==========================
def preprocess(text: str) -> str:
    text = text.lower().strip()
    # bỏ khoảng trắng thừa
    text = " ".join(text.split())
    return text


# ==========================
# XỬ LÝ NGÀY / GIỜ
# ==========================

def _parse_explicit_date(text: str, base_time: datetime) -> datetime | None:
    """
    Bắt các dạng ngày kiểu: 20/11, 20-11, 20/11/2025, 1-1-2026
    """
    m = re.search(r"(\d{1,2})[/-](\d{1,2})([/-](\d{2,4}))?", text)
    if not m:
        return None

    day = int(m.group(1))
    month = int(m.group(2))
    if m.group(3):
        year = int(m.group(3).lstrip("/-"))
        if year < 100:
            year += 2000
    else:
        year = base_time.year

    try:
        return datetime(year, month, day, base_time.hour, base_time.minute, 0, 0)
    except ValueError:
        return None


def _parse_relative_day(text: str, base_time: datetime) -> datetime:
    """
    Xử lý: hôm nay, mai, ngày mốt/ kia, cuối tuần, thứ hai/ba/...
    """
    # explicit date ưu tiên hơn
    explicit = _parse_explicit_date(text, base_time)
    if explicit is not None:
        return explicit

    t = base_time

    if "hôm nay" in text:
        return t
    if "ngày mai" in text or "mai" in text:
        return t + timedelta(days=1)
    if "ngày mốt" in text or "ngày kia" in text:
        return t + timedelta(days=2)
    if "cuối tuần" in text:
        # Chủ nhật tuần này
        return t + timedelta(days=(6 - t.weekday()))

    # thứ hai, ba, tư...
    thu_map = {
        "thứ hai": 0,
        "thứ ba": 1,
        "thứ tư": 2,
        "thứ năm": 3,
        "thứ sáu": 4,
        "thứ bảy": 5,
        "thứ bẩy": 5,
        "chủ nhật": 6,
        "chu nhat": 6,
    }

    for k, v in thu_map.items():
        if k in text:
            today = t.weekday()
            diff = v - today
            if diff <= 0:   # nếu đã qua thì coi như tuần sau
                diff += 7
            return t + timedelta(days=diff)

    # mặc định: ngày hôm nay
    return t


def _parse_time_of_day(text: str, base_time: datetime) -> tuple[int, int]:
    """
    Bắt giờ phút:
    - 10h, 10 giờ, 10:30, 10h30
    - hiểu buổi: sáng, trưa, chiều, tối, đêm
    """
    # 10h30 hoặc 10 giờ 30 hoặc 10:30
    m = re.search(r"(\d{1,2})\s*(h|giờ|:)\s*(\d{1,2})?", text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(3)) if m.group(3) else 0
    else:
        # Không ghi giờ -> default 10h
        hour, minute = 10, 0

    # điều chỉnh theo buổi
    if "tối" in text or "đêm" in text:
        if 1 <= hour <= 11:
            hour += 12
    elif "chiều" in text:
        if 1 <= hour <= 11:
            hour += 12
    elif "trưa" in text:
        if hour == 12:
            pass
        elif 1 <= hour <= 11:
            hour += 12
    # "sáng" thì để nguyên

    return hour, minute


def parse_datetime(text: str, base_time: datetime | None = None) -> datetime:
    """
    Trả về datetime tuyệt đối dựa trên:
    - explicit date (20/11, 20-11-2025)
    - hôm nay / mai / ngày mốt / cuối tuần / thứ ...
    - giờ/phút + buổi
    """
    if base_time is None:
        base_time = datetime.now()

    day_dt = _parse_relative_day(text, base_time)
    hour, minute = _parse_time_of_day(text, base_time)

    return day_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)


# ==========================
# LOCATION
# ==========================

def extract_location(text: str) -> str:
    """
    Lấy chuỗi sau 'ở' hoặc 'tại', cắt trước 'nhắc trước', dấu phẩy, từ khóa thời gian.
    """
    m = re.search(r"(ở|tai|tại)\s+(.+)", text)
    if not m:
        return ""

    loc = m.group(2).strip()

    # cắt theo các mốc thường gặp
    loc = re.split(r"nhắc trước|lúc|vao|vào|mai|nay|cuối tuần|thứ ", loc)[0]
    loc = loc.split(",")[0]

    return loc.strip()


# ==========================
# REMINDER
# ==========================

def extract_reminder(text: str) -> int:
    """
    Nhận 'nhắc trước 15 phút', 'nhắc trước 2 giờ' (tự đổi sang phút)
    """
    m = re.search(r"nhắc trước\s+(\d+)\s*(phút|p|phut|giờ|gio|tiếng|tieng)?", text)
    if not m:
        return 10  # default

    value = int(m.group(1))
    unit = m.group(2) or "phút"

    if unit.startswith(("giờ", "gio", "tiếng", "tieng")):
        return value * 60       # đổi giờ -> phút
    else:
        return value


# ==========================
# EVENT NAME
# ==========================

def extract_event_name(text: str) -> str:
    """
    Cố gắng bắt động từ + cụm danh từ phía sau làm tên sự kiện.
    Ví dụ: ăn cơm, đi làm, họp nhóm môn ai, nộp bài tập toán,...
    """
    # danh sách động từ phổ biến
    verbs = [
        "ăn", "di", "đi", "gap", "gặp", "họp", "hop", "lam", "làm",
        "thi", "hoc", "học", "uống", "uong", "mua", "nộp", "nop",
        "xem", "chơi", "choi", "khám", "kham", "chay", "chạy"
    ]
    verb_pattern = "|".join(sorted(set(verbs), key=len, reverse=True))

    # Bỏ phần "nhắc tôi", "nhắc mình" nếu có
    stripped = re.sub(r"nhắc( tôi| minh| mình)?", "", text).strip()

    # lấy động từ + cụm phía sau, cắt trước "lúc / vào / ở / tại / nhắc trước / ,"
    pattern = rf"({verb_pattern})\s+([^,.;]*?)(\s+lúc|\s+vao|\s+vào|\s+ở|\s+tại|\s+nhắc trước|,|$)"
    m = re.search(pattern, stripped)
    if m:
        verb = m.group(1)
        rest = m.group(2).strip()
        event = f"{verb} {rest}".strip()
        return event

    # fallback: dùng noun phrase ở đầu câu
    tokens = word_tokenize(text)
    if tokens:
        return " ".join(tokens[:3])  # lấy 3 từ đầu cho đỡ trống

    return "sự kiện"


# ==========================
# API CHÍNH
# ==========================

def text_to_event(text: str, base_time: datetime | None = None) -> dict:
    """
    Chuyển câu tiếng Việt tự nhiên thành dict:
    {
        "event": str,
        "start_time": ISO string,
        "end_time": None,
        "location": str,
        "reminder_minutes": int
    }
    """
    raw = text
    text = preprocess(text)

    dt = parse_datetime(text, base_time)
    event = extract_event_name(text)
    location = extract_location(text)
    reminder = extract_reminder(text)

    return {
        "event": event or "sự kiện",
        "start_time": dt.isoformat(timespec="seconds"),
        "end_time": None,
        "location": location,
        "reminder_minutes": reminder,
        "raw_text": raw,       # lưu thêm để debug / đánh giá
    }


# ==========================
# TEST NHANH
# ==========================
if __name__ == "__main__":
    base = datetime.now()
    samples = [
        "nhắc tôi họp nhóm lúc 10h sáng mai ở phòng 302, nhắc trước 15 phút",
        "nhắc tôi ăn cơm lúc 8 giờ tối nay ở nhà, nhắc trước 10 phút",
        "nhắc đi làm lúc 9 giờ sáng mai ở an dương vương, nhắc trước 10 phút",
        "nhắc tôi học bài môn ai lúc 19:30 thứ hai, nhắc trước 30 phút",
        "nhắc tôi đi khám bệnh lúc 7h sáng 20/11, nhắc trước 2 giờ",
        "nhắc tôi đi siêu thị cuối tuần này lúc 15h, nhắc trước 45 phút",
    ]
    for s in samples:
        print("====", s)
        print(text_to_event(s, base))
