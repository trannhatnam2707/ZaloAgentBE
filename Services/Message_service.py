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

        # 4. CHUẨN BỊ ĐẦU RA (Format lại dữ liệu để Pydantic Schema không bị lỗi)
        new_message["id"] = str(result.inserted_id)
        new_message["conversation_id"] = str(new_message["conversation_id"])
        new_message["sender_id"] = str(new_message["sender_id"])
        
        return new_message