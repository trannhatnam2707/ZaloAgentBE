import sys
import os
from datetime import datetime, timedelta
from bson import ObjectId
import asyncio
    
# Thêm đường dẫn để import module từ dự án
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Database.MongoDB import Conversation_collection, messages_collection

def fix_timezone():
    print("Bắt đầu sửa lỗi múi giờ cho dữ liệu...")
    
    # Múi giờ chênh lệch (Ví dụ: Nếu DB đang chậm hơn 7 tiếng, ta cộng thêm 7)
    # Bạn nói gửi 12:23 mà lưu 17:23 ngày hôm trước -> tức là đang bị lệch khoảng 19 tiếng hoặc do UTC
    # Thông thường, sửa từ UTC sang VN là cộng 7 tiếng
    hours_to_add = 7 

    # 1. Sửa bảng Messages
    msgs = list(messages_collection.find({}))
    msg_count = 0
    for m in msgs:
        if isinstance(m.get("created_at"), datetime):
            new_time = m["created_at"] + timedelta(hours=hours_to_add)
            messages_collection.update_one(
                {"_id": m["_id"]},
                {"$set": {"created_at": new_time}}
            )
            msg_count += 1
    print(f" - Đã sửa {msg_count} tin nhắn.")

    # 2. Sửa bảng Conversations
    convs = list(Conversation_collection.find({}))
    conv_count = 0
    for c in convs:
        update_fields = {}
        if isinstance(c.get("created_at"), datetime):
            update_fields["created_at"] = c["created_at"] + timedelta(hours=hours_to_add)
        if isinstance(c.get("updated_at"), datetime):
            update_fields["updated_at"] = c["updated_at"] + timedelta(hours=hours_to_add)
        if isinstance(c.get("last_msg_time"), datetime):
            update_fields["last_msg_time"] = c["last_msg_time"] + timedelta(hours=hours_to_add)
            
        if update_fields:
            Conversation_collection.update_one({"_id": c["_id"]}, {"$set": update_fields})
            conv_count += 1
    print(f" - Đã sửa {conv_count} hội thoại.")

    print("Hoàn thành sửa lỗi múi giờ!")

if __name__ == "__main__":
    asyncio.run(fix_timezone())