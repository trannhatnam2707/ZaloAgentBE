import sys
import os

# 1. Chỉ đường cho Python tìm thấy thư mục gốc (AGENTZALO)
current_dir = os.path.dirname(os.path.abspath(__file__)) # Thư mục Scripts
parent_dir = os.path.dirname(current_dir) # Thư mục AGENTZALO
sys.path.append(parent_dir) # Ép Python phải nhìn vào thư mục gốc

# 2. Bây giờ import bình thường, nó sẽ không báo lỗi nữa
from bson import ObjectId
from Database.MongoDB import db, users_collection
from datetime import datetime

def migrate_legacy_reports():
    """
    Script chuyển đổi 63 report cũ sang bảng Messages để hiển thị lên UI
    """
    reports_collection = db.Report
    messages_collection = db.Messages
    
    # 1. Lấy tất cả report hiện có
    all_reports = list(reports_collection.find())
    count_migrated = 0
    
    print(f"Bắt đầu kiểm tra {len(all_reports)} báo cáo...")

    for report in all_reports:
        report_id_str = str(report["_id"])
        
        # 2. Kiểm tra xem report này đã có "thẻ" bên Messages chưa
        # Dựa vào metadata.report_id chúng ta đã quy định
        exists = messages_collection.find_one({"metadata.report_id": report_id_str})
        
        if not exists:
            # 3. Lấy thông tin User để lấy Avatar và Name (giúp UI hiển thị đẹp)
            user = users_collection.find_one({"_id": report["user_id"]}) or {}
            username = user.get("username", "Unknown")
            user_avatar = user.get(
                "avatar", 
                f"https://api.dicebear.com/7.x/initials/svg?seed={username}&backgroundColor=00897b,1e88e5,43a047,e53935,fb8c00,8e24aa"
            )

            # 4. Tạo bản ghi Message loại 'report_card' tương ứng
            new_message = {
                "conversation_id": report["conversation_id"],
                "sender_id": report["user_id"],
                "type": "report_card",
                "content": "", # Để rỗng theo đúng yêu cầu mới của bạn
                "metadata": {
                    "report_id": report_id_str,
                    "date": report.get("date"),
                    "user_name": username,
                    "user_avatar": user_avatar,
                    "yesterday": report.get("yesterday"),
                    "today": report.get("today")
                },
                "created_at": report.get("created_at", datetime.now()) # Giữ đúng thời gian tạo cũ
            }
            
            messages_collection.insert_one(new_message)
            count_migrated += 1
            print(f"--- Đã tạo thẻ cho report ngày: {report.get('date')} của {username}")

    print(f"Hoàn thành! Đã chuyển đổi thành công {count_migrated} báo cáo sang luồng tin nhắn.")

# Chạy script
if __name__ == "__main__":
    migrate_legacy_reports()