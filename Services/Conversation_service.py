from datetime import  datetime
from bson import ObjectId
from fastapi import HTTPException
from Database.MongoDB import db


Conversation_collection = db.Conversations
User_collection = db.Users

class ConversationService:

    # --- Hàm Helper dùng chung để format ID ---
    @staticmethod
    def _format_conversation(conv):
        if not conv: return None
        conv["id"] = str(conv["_id"])
        conv["members"] = [str(m) for m in conv.get("members", [])]
        if conv.get("owner_id"):
            conv["owner_id"] = str(conv["owner_id"])
        return conv

    @staticmethod
    def create_or_get_direct_chat(current_user_id: str, target_user_id: str):
        if current_user_id == target_user_id:
            raise HTTPException(status_code=400, detail="Bạn không thể tự chat với chính mình!")
        
        #1. Kiểm tra người kia có tồn tại không
        target_user = User_collection.find_one({"_id":ObjectId(target_user_id)})
        if not target_user :
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng này!")
        
        user1 = ObjectId(current_user_id)
        user2 = ObjectId(target_user_id)

        #2. Tìm xem 2 người đã từng có chat 1-1 chưa (Tìm mảng members chứa đúng 2 người này)
        existing_chat = Conversation_collection.find_one({
            "type": "direct",
            "members": {"$all": [user1,user2], "$size": 2}
        })

        if existing_chat:
            return ConversationService._format_conversation(existing_chat)

        new_chat = {
            "type": "direct",
            "members" : [user1, user2],
            "created_at" : datetime.utcnow()
        }
        result = Conversation_collection.insert_one(new_chat)
        new_chat["_id"] = result.inserted_id
        return ConversationService._format_conversation(new_chat)


    @staticmethod
    def create_group_chat(group_name: str, members_ids: list[str], owner_id: str):
        #1. xử lý danh sách thành viên
        obj_member_id = []
        for mid in members_ids:
            try:
                obj_member_id.append(ObjectId(mid))
            except: 
                pass #Bỏ qua ID lỗi

        owner_obj_id = ObjectId(owner_id)
        #2.Đảm bảo chủ nhóm chắc chắn có trong list members
        if owner_obj_id not in obj_member_id:
            obj_member_id.append(owner_obj_id)

        if len(obj_member_id) < 3:
            raise HTTPException(status_code=400, detail="Nhóm chat phải từ 3 người trở lên!")

        new_group  = {
            "type": "group",
            "group_name": group_name,
            "owner_id": owner_obj_id,
            "members":  obj_member_id,
            "created_at": datetime.utcnow()
        }
        result = Conversation_collection.insert_one(new_group)
        new_group["_id"] = result.inserted_id
        return ConversationService._format_conversation(new_group)

    @staticmethod
    def add_member_to_group(conversation_id: str, new_member_id: str):
        if not User_collection.find_one({"_id":ObjectId(new_member_id)}):
            raise HTTPException(status_code=404, detail="Người dùng này không tồn tại")
        
        updated = Conversation_collection.find_one_and_update(
            {"_id": ObjectId(conversation_id)},
            {"$addToSet": {"members":ObjectId(new_member_id)}},
            return_document=True
        )
        return ConversationService._format_conversation(updated)

    @staticmethod
    def remove_member_from_group(conversatio_id:str,member_to_remove_id: str):
        #Dùng  $pull để rút ID người dùng ra khỏi mảng members
        updated = Conversation_collection.find_one_and_update(
            {"_id": ObjectId(conversatio_id)},
            {"$pull": {"members": ObjectId(member_to_remove_id)}},
            return_document=True
        )
        return ConversationService._format_conversation(updated)
    
    @staticmethod
    def get_my_conversation(current_user_id:str):
        cursor = Conversation_collection.find({
            "members": ObjectId(current_user_id),
        }).sort([
            ("updated_at", -1),
            ("created_at", -1),
        ])
        return [ConversationService._format_conversation(c) for c in cursor]

    