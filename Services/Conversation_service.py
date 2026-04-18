from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException
from Database.MongoDB import db, messages_collection


Conversation_collection = db.Conversations
User_collection = db.Users

class ConversationService:

    # --- Hàm Helper dùng chung để format ID ---
    @staticmethod
    def _format_conversation(conv):
        if not conv:
            return None
        conv["id"] = str(conv["_id"])
        conv["members"] = [str(m) for m in conv.get("members", [])]
        if conv.get("owner_id"):
            conv["owner_id"] = str(conv["owner_id"])
        return conv

    @staticmethod
    def create_or_get_direct_chat(current_user_id: str, target_user_id: str):
        target_user = User_collection.find_one({"_id":ObjectId(target_user_id)})
        if not target_user:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng này!")


        if current_user_id == target_user_id:
            raise HTTPException(status_code=400, detail="Bạn không thể tự chat với chính mình!")
        
        #1. Kiểm tra người kia có tồn tại không
        target_user = User_collection.find_one({"_id":ObjectId(target_user_id)})
        if not target_user :
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng này!")

        target_name = target_user.get("display_name") or target_user.get("username", "Người dùng")
        
        user1 = ObjectId(current_user_id)
        user2 = ObjectId(target_user_id)

        #2. Tìm xem 2 người đã từng có chat 1-1 chưa (Tìm mảng members chứa đúng 2 người này)
        existing_chat = Conversation_collection.find_one({
            "type": "direct",
            "members": {"$all": [user1,user2], "$size": 2}
        })

        if existing_chat:
            existing_chat["conv_name"] = target_name
            return ConversationService._format_conversation(existing_chat)

        # 4. Nếu chưa có thì tạo mới (KHÔNG lưu trường name hay conv_name vào MongoDB)
        new_chat = {
            "type": "direct",
            "members" : [user1, user2],
            "created_at" : datetime.utcnow()
        }
        result = Conversation_collection.insert_one(new_chat)
        new_chat["_id"] = result.inserted_id
        
        # Gán tên vào bộ nhớ tạm trước khi ném về FE
        new_chat["conv_name"] = target_name
        
        return ConversationService._format_conversation(new_chat)


    @staticmethod
    def create_group_chat(name: str, members_ids: list[str], owner_id: str):
        clean_name = (name or "").strip()
        if not clean_name:
            owner = User_collection.find_one({"_id": ObjectId(owner_id)})
            owner_name = owner.get("display_name") or owner.get("username", "Người dùng")
            clean_name = f"Nhóm của {owner_name}"

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
            "conv_name": clean_name,
            # "group_name": clean_name,
            "owner_id": owner_obj_id,
            "members":  obj_member_id,
            "created_at": datetime.now()
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
    def remove_member_from_group(conversation_id: str, member_id: str):
        try:
            
            result = Conversation_collection.find_one_and_update(
                {"_id": ObjectId(conversation_id)},
                {"$pull": {"members": ObjectId(member_id)}}
            )

            if result.modified_count == 0:
                raise ValueError("Không tìm thấy user trong nhóm này.")

            # Kiểm tra nếu nhóm không còn ai thì xóa luôn nhóm!
            updated_conv = Conversation_collection.find_one({"_id": ObjectId(conversation_id)})
            if updated_conv and len(updated_conv.get("members", [])) == 0:
                Conversation_collection.delete_one({"_id": ObjectId(conversation_id)})
                return {"message": "Đã xóa user và xóa luôn nhóm vì không còn thành viên."}

            return {"message": "Đã xóa user khỏi nhóm thành công."}

        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi: {str(e)}")
    
    @staticmethod
    def get_my_conversation(current_user_id: str, keyword: str = ""):
        query = {"members": ObjectId(current_user_id)}
        clean_keyword = keyword.strip().lower()
        result = []
        # Không lọc theo "nrên Mongo: name" thóm dùng trường "conv_name", chat 1-1 không lưu tên
        # trong DB (tên hiển thị lấy từ Users). Lọc theo keyword chỉ sau khi gán conv_name bên dưới.

        cursor = Conversation_collection.find(query).sort([
            ("updated_at", -1),
            ("created_at", -1),
        ])
        conversations = [ConversationService._format_conversation(c) for c in cursor]

        # Tự vá dữ liệu cũ chưa có name để FE luôn hiển thị được tên thay vì id.
        for conv in conversations:
            if conv.get("type") == "direct":
                # Tìm ID người kia
                other_user_id = next((m for m in conv["members"] if m != str(current_user_id)), None)
                if other_user_id:
                    other_user = User_collection.find_one({"_id": ObjectId(other_user_id)})
                    # Gán tên hiển thị của người kia vào conv_name chỉ ở bộ nhớ tạm (không lưu DB)
                    if other_user:
                        conv["conv_name"] = other_user.get("display_name") or other_user.get("username")
                    else:
                        conv["conv_name"] = "Người dùng ẩn"
            else:
                # Group thì lấy conv_name từ DB
                conv["conv_name"] = conv.get("conv_name", "Nhóm không tên")
            
            # Lấy tin nhắn mới nhất dựa trên conv_id
            last_msg = messages_collection.find_one(
                {
                    "$or": [
                        {"conversation_id": conv["id"]},         # Dạng String
                        {"conversation_id": ObjectId(conv["id"])} # Dạng ObjectId
                    ]
                },
                sort=[("created_at", -1)]
            )

            if last_msg:
                conv["last_msg"] = last_msg.get("content", "")
                conv["last_msg_time"] = last_msg.get("created_at")
            else:
                conv["last_msg"] = "Chưa có tin nhắn"
                conv["last_msg_time"] = conv.get("updated_at") #Dùng tạm updated_at của phòng

            if clean_keyword:
                display = (conv.get("conv_name") or "").lower()
                if clean_keyword in display:
                    result.append(conv)
            else:
                result.append(conv)

        return result

    