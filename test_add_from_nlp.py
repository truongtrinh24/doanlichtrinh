# test_add_from_nlp.py
from datetime import datetime
from nlp_module import text_to_event
from db import init_db, add_event, get_events_by_day

if __name__ == "__main__":
    init_db()

    text = "Nhắc tôi họp nhóm môn AI lúc 9 giờ sáng mai ở phòng 101, nhắc trước 20 phút"
    event = text_to_event(text)
    print("Event sau khi NLP:", event)

    event_id = add_event(event)
    print("Đã lưu vào DB với id =", event_id)

    today = datetime.now()
    events_today = get_events_by_day(today)
    print("Các sự kiện hôm nay / mai gần đó:")
    for e in events_today:
        print(e)
