import streamlit as st
import time
from datetime import datetime, timedelta, time as time_obj
from db import export_all_events_to_json
from streamlit_autorefresh import st_autorefresh
import calendar
from collections import defaultdict




from nlp_module import text_to_event
from db import (
    init_db,
    add_event,
    get_events_by_day,
    get_events_by_week,
    get_events_by_month,
    search_events,
    delete_event,
    update_event,
    get_upcoming_events
)

# ============================================================
# 1. HÀM CHECK NHẮC NHỞ
# ============================================================
def check_reminders():
    now = datetime.now()
    upcoming = get_upcoming_events(now)

    reminders = []
    for e in upcoming:
        event_time = datetime.fromisoformat(e["start_time"])
        remind_before = int(e["reminder_minutes"])

        # điều kiện nhắc
        if now >= event_time - timedelta(minutes=remind_before):
            reminders.append(e)

    return reminders


# ============================================================
# 2. KHỞI TẠO DB + UI
# ============================================================
init_db()

st.set_page_config(page_title="Trợ lý lịch trình", page_icon="📅", layout="wide")
st.title("📅 Trợ lý Quản lý Lịch Trình Cá Nhân")
# Auto refresh mỗi 30 giây
st_autorefresh(interval=30000, key="refresh")


# 🔔 HIỂN THỊ NHẮC NHỞ
reminders = check_reminders()
if reminders:
    st.header("🔔 NHẮC VIỆC QUAN TRỌNG")
    for r in reminders:
        st.warning(
            f"⏰ Sắp tới giờ: **{r['title']}** lúc *{r['start_time']}* tại **{r['location']}**",
            icon="⚠️",
        )
        update_event(r["id"], notified=1)
else:
    st.info("Không có nhắc nhở nào trong thời gian gần.")


# ============================================================
# 3. FORM THÊM SỰ KIỆN
# ============================================================
st.header("➕ Thêm sự kiện bằng câu tự nhiên")

input_text = st.text_input(
    "Nhập câu (VD: Nhắc tôi họp nhóm lúc 10 giờ sáng mai ở phòng 302, nhắc trước 15 phút):"
)

if st.button("Phân tích và thêm sự kiện"):
    if input_text.strip() == "":
        st.warning("Vui lòng nhập câu mô tả sự kiện!")
    else:
        event = text_to_event(input_text)
        event_id = add_event(event)
        st.success(f"Đã thêm sự kiện! (ID = {event_id})")
        st.json(event)


# ============================================================
# 4. XEM DANH SÁCH SỰ KIỆN
# ============================================================
st.header("📋 Danh sách sự kiện")
# Nút export JSON
if st.button("📤 Xuất toàn bộ sự kiện ra JSON"):
    filename = f"events_export_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    filepath = filename
    export_all_events_to_json(filepath)
    st.success(f"Đã xuất file JSON: {filename}")
    with open(filepath, "rb") as f:
        st.download_button(
            label="📥 Tải xuống file JSON",
            data=f,
            file_name=filename,
            mime="application/json"
        )


option = st.selectbox(
    "Chọn chế độ xem:",
    ["Hôm nay", "Tuần này", "Tháng này", "Lịch tháng", "Tìm kiếm"],
)


now = datetime.now()
events = []          # danh sách sự kiện cho các mode cũ
show_event_list = True   # flag để ẩn list khi hiển thị lịch tháng


if option == "Hôm nay":
    events = get_events_by_day(now)
    st.subheader("📅 Sự kiện hôm nay")

elif option == "Tuần này":
    monday = now - timedelta(days=now.weekday())
    events = get_events_by_week(monday)
    st.subheader("🗓️ Sự kiện tuần này")

elif option == "Tháng này":
    events = get_events_by_month(now.year, now.month)
    st.subheader("📆 Sự kiện tháng này")
elif option == "Lịch tháng":
    st.subheader("📆 Lịch tháng")

    year = st.number_input("Năm", min_value=2020, max_value=2100, value=now.year)
    month = st.number_input("Tháng", min_value=1, max_value=12, value=now.month)

    year = int(year)
    month = int(month)

    # Lấy sự kiện trong tháng
    events_in_month = get_events_by_month(year, month)

    from collections import defaultdict
    import calendar as cal_mod
    from datetime import date as date_cls

    # Gom sự kiện theo từng ngày
    events_by_date = defaultdict(list)
    for e in events_in_month:
        try:
            dt = datetime.fromisoformat(e["start_time"])
            day_key = dt.date()
            events_by_date[day_key].append(e)
        except Exception:
            continue

    cal = cal_mod.Calendar(firstweekday=0)  # 0 = Monday
    month_days = cal.monthdatescalendar(year, month)
    today = datetime.now().date()

    # Vẽ từng tuần
    weekdays = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    header_cols = st.columns(7)
    for i, w in enumerate(weekdays):
        header_cols[i].markdown(f"**{w}**")

    for week in month_days:
        cols = st.columns(7)
        for i, day in enumerate(week):
            with cols[i]:
                is_current_month = (day.month == month)
                is_today = (day == today)
                day_events = events_by_date.get(day, [])

                #header ngày
                if is_current_month:
                    if is_today:
                        st.markdown(f"**{day.day} (hôm nay)**")
                    else:
                        st.markdown(f"**{day.day}**")
                else:
                    st.markdown(f"<span style='color:#bbbbbb'>{day.day}</span>",
                                unsafe_allow_html=True)

                #nội dung trong ô
                if not day_events:
                    st.write("")  # chừa khoảng trống cho cân
                elif len(day_events) == 1:
                    ev = day_events[0]
                    try:
                        dt = datetime.fromisoformat(ev["start_time"])
                        time_str = dt.strftime("%H:%M")
                    except Exception:
                        time_str = "--:--"
                    st.caption(f"{time_str} · {ev['title'][:20]}")
                    if st.button("🔍 Chi tiết",
                                 key=f"view_{day.isoformat()}"):
                        st.session_state["selected_calendar_day"] = day.isoformat()
                else:
                    # nhiều hơn 1 sự kiện
                    st.caption(f"{len(day_events)} sự kiện")
                    if st.button(f"🔔 Xem {len(day_events)} nhắc",
                                 key=f"bell_{day.isoformat()}"):
                        st.session_state["selected_calendar_day"] = day.isoformat()

    #Chi tiết ngày được chọn
    sel = st.session_state.get("selected_calendar_day")
    if sel:
        y, m, d = map(int, sel.split("-"))
        selected_date = date_cls(y, m, d)
        day_events = events_by_date.get(selected_date, [])

        if day_events:
            st.markdown("---")
            st.subheader(f"📅 Sự kiện ngày {selected_date.strftime('%d/%m/%Y')}")
            for ev in day_events:
                try:
                    dt = datetime.fromisoformat(ev["start_time"])
                    time_str = dt.strftime("%H:%M")
                except Exception:
                    time_str = "--:--"
                st.write(f"**{time_str}** · {ev['title']} · _{ev['location']}_")

    # Ở mode Lịch tháng: chỉ xem, không hiện list + form sửa/xóa bên dưới
    show_event_list = False
    events = []








elif option == "Tìm kiếm":
    keyword = st.text_input("Nhập từ khóa:")
    events = search_events(keyword) if keyword.strip() else []


# ============================================================
# 5. SỬA + XÓA SỰ KIỆN
# ============================================================
if show_event_list:
    if events:
        for e in events:
            with st.expander(f"ID {e['id']} – {e['title']}", expanded=False):

                # --- Lấy ngày giờ ---
                try:
                    start_dt = datetime.fromisoformat(e["start_time"])
                except:
                    start_dt = datetime.now()

                # --- Các trường sửa ---
                new_title = st.text_input(
                    "Tiêu đề sự kiện",
                    value=e["title"],
                    key=f"title_{e['id']}"
                )

                new_date = st.date_input(
                    "Ngày bắt đầu",
                    value=start_dt.date(),
                    key=f"date_{e['id']}"
                )

                new_time = st.time_input(
                    "Giờ bắt đầu",
                    value=start_dt.time(),
                    key=f"time_{e['id']}"
                )

                new_location = st.text_input(
                    "Địa điểm",
                    value=e["location"] or "",
                    key=f"loc_{e['id']}"
                )

                new_reminder = st.text_input(
                    "Nhắc trước (phút)",
                    value=str(e["reminder_minutes"]),
                    key=f"rem_{e['id']}"
                )

                st.write(f"🔔 Đã nhắc: `{e['notified']}`")

                col1, col2 = st.columns(2)

                # --- Nút LƯU ---
                if col1.button("💾 Lưu thay đổi", key=f"save_{e['id']}"):
                    try:
                        reminder_int = int(new_reminder)
                        new_start_dt = datetime.combine(new_date, new_time)
                        update_event(
                            e["id"],
                            title=new_title,
                            start_time=new_start_dt.isoformat(),
                            location=new_location,
                            reminder_minutes=reminder_int
                        )
                        st.success(f"Đã cập nhật sự kiện ID {e['id']}")
                        st.rerun()

                    except ValueError:
                        st.error("Nhắc trước (phút) phải là số nguyên!")

                # --- Nút XÓA ---
                if col2.button("❌ Xóa sự kiện này", key=f"delete_{e['id']}"):
                    delete_event(e["id"])
                    st.success(f"Đã xóa sự kiện ID {e['id']}")
                    st.rerun()

    else:
        st.info("Không có sự kiện nào.")



# ============================================================
# 6. FOOTER — DÒNG BẠN ĐANG BỊ MẤT
# ============================================================
st.caption("Hệ thống trợ lý lịch trình – Python | NLP | Streamlit | SQLite")
