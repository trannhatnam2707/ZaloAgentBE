import sys
import os
from dotenv import load_dotenv

# 1. Chỉ định đường dẫn tới file .env ở thư mục gốc và load nó TRƯỚC KHI import MongoDB
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path=env_path)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Database.MongoDB import db
from pymongo import UpdateOne

def migrate_conversation_names():
    # 2. In ra để kiểm tra xem đã vào đúng DB chưa
    total_docs = db.Conversations.count_documents({})
    print(f"🔍 Đang kết nối tới Database: '{db.name}'")
    print(f"📦 Tìm thấy {total_docs} cuộc hội thoại.")

    if total_docs == 0:
        print("⚠️ LỖI: Không tìm thấy data! Hãy kiểm tra lại MONGO_URI trong file .env")
        return

    conversations = db.Conversations.find({})
    bulk_updates = []
    
    group_counter = 1

    for conv in conversations:
        conv_id = conv["_id"]
        c_type = conv.get("type")
        
        # Tạo object để XÓA các trường rác cũ
        unset_fields = {"name": "", "group_name": ""}
        set_fields = {}

        if c_type == "group":
            old_name = conv.get("conv_name") or conv.get("name") or conv.get("group_name")
            if not old_name:
                old_name = f"Group Chat {group_counter}"
                group_counter += 1
            
            set_fields["conv_name"] = old_name
            
        elif c_type == "direct":
            unset_fields["conv_name"] = ""

        # Chuẩn bị lệnh update
        update_op = {}
        if set_fields:
            update_op["$set"] = set_fields
        update_op["$unset"] = unset_fields

        bulk_updates.append(UpdateOne({"_id": conv_id}, update_op))

    if bulk_updates:
        result = db.Conversations.bulk_write(bulk_updates)
        print(f"✅ Đã dọn dẹp và cập nhật thành công {result.modified_count} cuộc hội thoại.")
    else:
        print("Không có cuộc hội thoại nào cần cập nhật.")

if __name__ == "__main__":
    migrate_conversation_names()