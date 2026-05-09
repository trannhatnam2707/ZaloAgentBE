import sys
import os
from bson import ObjectId
import asyncio

# Thêm đường dẫn để import module từ dự án của bạn
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Database.MongoDB import Conversation_collection, messages_collection

def migrate_conversation_data():
    print("Bắt đầu cập nhật thông tin tin nhắn cuối cho Conversation...")
    
    # 1. Lấy tất cả hội thoại
    conversations = list(Conversation_collection.find({}))
    if not conversations:
        print("Không tìm thấy hội thoại nào trong collection 'conversations'.")
        return

    count = 0
    for conv in conversations:
        conv_id_str = str(conv["_id"])
        conv_id_obj = conv["_id"] # ObjectId
        
        # 2. Tìm tin nhắn mới nhất (thử cả ID dạng String và ObjectId)
        last_msg = messages_collection.find_one(
            {
                "$or": [
                    {"conversation_id": conv_id_str},
                    {"conversation_id": conv_id_obj}
                ]
            },
            sort=[("created_at", -1)]
        )

        if last_msg:
            # 3. Cập nhật trường updated_at
            new_time = last_msg.get("created_at")
            if new_time:
                Conversation_collection.update_one(
                    {"_id": conv_id_obj},
                    {"$set": {"updated_at": new_time}}
                )
                count += 1
                print(f" - Đã cập nhật hội thoại: {conv.get('conv_name', conv_id_str)}")

    print(f"Hoàn thành! Đã cập nhật thành công {count}/{len(conversations)} hội thoại.")

if __name__ == "__main__":
    # Vì script cũ của bạn chạy đồng bộ hoặc không dùng loop, hãy đảm bảo chạy đúng cách
    asyncio.run(migrate_conversation_data())