from fastapi import HTTPException
from Schemas.Message_schema import MessageCreate
from bson import ObjectId
from Database.MongoDB import db
from datetime import datetime

Message_collection = db.Messages
Conversation_collection = db.Conversations

class MessageService: 
    @staticmethod
    def send_message(data: MessageCreate, current_user_id: str):
        #1 Security: check if the chat room exits and if the user is present
        #Absolutely do not allow users to use other people's room IDs to send spam messages!
        try:
            conv_id = ObjectId(data.conversation_id)
        except: 
            raise HTTPException(status_cod=400, detail="ID phòng chat không hợp lệ")

        conversation = Conversation_collection.find_one({"_id": conv_id})
        if not conversation: 
            raise HTTPException(status_code=404, detail="Không tìm thấy phòng chat này")
        if ObjectId(current_user_id) not in conversation.get("members", []):
            raise HTTPException(status_code=403, detail="Bạn không có quyền nhắn tin vào phòng chat này")
        
        # 2. DATA PACKAGING: Automatically insert sender_id from the Token (Do not trust the Frontend)
        new_message = {
            "conversation_id": conv_id,
            "sender_id": ObjectId(current_user_id), # Ép kiểu về ObjectId cho chuẩn DB
            "type": data.type.value, # Lấy giá trị string từ Enum (ví dụ: "text")
            "content": data.content,
            "metadata": data.metadata,
            "created_at": datetime.utcnow()
        }

        #3. Save Mongo
        result = Message_collection.insert_one(new_message)
        Conversation_collection.update_one(
            {"_id": ObjectId(conv_id)},
            {"$set": {"updated_at":datetime.utcnow()}}
        )

        # 4. CHUẨN BỊ ĐẦU RA (Format lại dữ liệu để Pydantic Schema không bị lỗi)
        new_message["id"] = str(result.inserted_id)
        new_message["conversation_id"] = str(new_message["conversation_id"])
        new_message["sender_id"] = str(new_message["sender_id"])
        
        return new_message

    @staticmethod
    def get_conversation_messages(conversation_id: str, current_user_id: str, skip: int = 0, limit: int = 50):
        # 1 Bảo mật: Người trong phòng mới đọc được tin nhắn
        try:    
            conv_id = ObjectId(conversation_id)
        except:
            raise HTTPException(status_code=400, detail="ID phòng chat không hợp lệ")

        conversation = Conversation_collection.find_one({"_id": conv_id})
        if not conversation or ObjectId(current_user_id) not in conversation.get("members", []):
            raise HTTPException(status_code=403, detail="Bạn không có quyền xem tin nhắn này!")

        # 2. LẤY DỮ LIỆU: Lấy tin nhắn mới nhất (sort -1), hỗ trợ phân trang (skip, limit)
        # Để khi user cuộn lên trên, FE sẽ gọi hàm này để tải thêm tin cũ
        cursor = Message_collection.find({"conversation_id": conv_id,"metadata.is_ai_bubble": {"$ne": True}})\
                                   .sort("created_at", -1)\
                                   .skip(skip)\
                                   .limit(limit)
        
        messages = list(cursor)

        # 3. ĐỊNH DẠNG LẠI (Convert ObjectId -> String)
        for msg in messages:
            msg["id"] = str(msg["_id"])
            msg["conversation_id"] = str(msg["conversation_id"])
            msg["sender_id"] = str(msg["sender_id"])

        return messages
    # ==========================================
    # LUỒNG 2: DÀNH CHO AI / HỆ THỐNG (GỌI NỘI BỘ TRONG BACKEND)
    # ==========================================
    @staticmethod
    def send_bot_message(conversation_id: str, type: str, content: str, metadata: dict = None):
        """
        Hàm này không có Router API (Frontend không gọi được).
        Chỉ có các đoạn code Python của AI mới được phép gọi hàm này.
        """
        new_message = {
            "conversation_id": ObjectId(conversation_id),
            "sender_id": "bot_agent", #  BÍ QUYẾT LÀ ĐÂY: Lưu thẳng chuỗi String, không ép kiểu ObjectId!
            "type": type,
            "content": content,
            "metadata": metadata,
            "created_at": datetime.utcnow()
        }

        result = Message_collection.insert_one(new_message)
        Conversation_collection.update_one(
            {"_id": ObjectId(conversation_id)},
            {"$set": {"updated_at":datetime.utcnow()}}
            )
        # Trả về kết quả (để AI log ra màn hình hoặc xử lý tiếp)
        new_message["id"] = str(result.inserted_id)
        new_message["conversation_id"] = str(new_message["conversation_id"])
        return new_message
    
    @staticmethod
    def get_ai_bubble_history(conversation_id: str, current_user_id: str):
        """Lấy lịch sử chat đã từng nói chuyện với AI trong bong bóng"""
        conv_id = ObjectId(conversation_id)
        
        cursor = Message_collection.find({
            "conversation_id": conv_id,
            "metadata.is_ai_bubble": True  # Lọc đúng luồng của AI
        }).sort("created_at", 1) # Sắp xếp từ cũ đến mới để hiện lên khung chat
        
        return list(cursor)

