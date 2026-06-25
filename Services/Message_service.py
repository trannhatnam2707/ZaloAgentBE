import re
from fastapi import HTTPException
from Schemas.Message_schema import MessageCreate
from bson import ObjectId
from Database.MongoDB import db, users_collection
from datetime import datetime
from Services.Report_service import create_report

Message_collection = db.Messages
Conversation_collection = db.Conversations

class MessageService: 

    @staticmethod
    def send_message(data: MessageCreate, current_user_id: str):
        # 1. KIỂM TRA QUYỀN VÀ PHÒNG CHAT
        try:
            conv_id = ObjectId(data.conversation_id)
        except: 
            raise HTTPException(status_code=400, detail="ID phòng chat không hợp lệ")

        conversation = Conversation_collection.find_one({"_id": conv_id})
        if not conversation: 
            raise HTTPException(status_code=404, detail="Không tìm thấy phòng chat này")
        if ObjectId(current_user_id) not in conversation.get("members", []):
            raise HTTPException(status_code=403, detail="Bạn không có quyền nhắn tin vào phòng chat này")

        # TÍNH NĂNG ĐÁNH CHẶN SLASH COMMAND (Mềm dẻo: chấp nhận cả /report và report)
        content_lower = data.content.strip().lower()
        if content_lower.startswith("/report") or content_lower.startswith("report"):
            return MessageService._handle_report_command(data.content, conv_id, current_user_id)
        
        # 2. XỬ LÝ TIN NHẮN CHỮ BÌNH THƯỜNG
        new_message = {
            "conversation_id": conv_id,
            "sender_id": ObjectId(current_user_id),
            "type": data.type.value, # Lấy giá trị string từ Enum
            "content": data.content,
            "metadata": data.metadata,
            "created_at": datetime.now()
        }

        # 3. Save Mongo
        result = Message_collection.insert_one(new_message)
        Conversation_collection.update_one(
            {"_id": ObjectId(conv_id)},
            {"$set": {"updated_at": datetime.now()}}
        )

        # 4. Format lại dữ liệu đầu ra
        new_message["id"] = str(result.inserted_id)
        new_message["conversation_id"] = str(new_message["conversation_id"])
        new_message["sender_id"] = str(new_message["sender_id"])
        
        return new_message

    @staticmethod
    def get_conversation_messages(conv_id: str, current_user_id: str, skip: int = 0, limit: int = 50):
        try:
            # 1. Kiểm tra tính hợp lệ của ObjectId
            try:
                obj_conv_id = ObjectId(conv_id)
            except:
                raise HTTPException(status_code=400, detail="ID hội thoại không hợp lệ")

            # 2. Tìm hội thoại để kiểm tra quyền truy cập
            conversation =  db.Conversations.find_one({"_id": obj_conv_id})
            if not conversation:
                raise HTTPException(status_code=404, detail="Hội thoại không tồn tại")

            # 3. Kiểm tra quyền (Ép kiểu về string để so sánh chuẩn)
            user_id_str = str(current_user_id)
            members_list = [str(m) for m in conversation.get("members", [])]
            
            if user_id_str not in members_list:
                print(f"FORBIDDEN: User {user_id_str} not in {members_list}")
                raise HTTPException(status_code=403, detail="Bạn không có quyền xem tin nhắn này")

            # 5. Lấy tin nhắn
            messages_cursor = db.Messages.find({"conversation_id": obj_conv_id}) \
                                        .sort("created_at", -1) \
                                        .skip(skip) \
                                        .limit(limit)
            
            messages = list(messages_cursor)
            
            # --- ĐÃ FIX: Lấy sender_ids an toàn chống lỗi KeyError/isinstance ---
            sender_ids = []
            for msg in messages:
                s_id = msg.get("sender_id")
                if s_id:
                    try:
                        sender_ids.append(ObjectId(str(s_id)))
                    except:
                        pass
            
            sender_ids = list(set(sender_ids))
            senders = list(users_collection.find({"_id": {"$in": sender_ids}}))
            # Tạo bản đồ id -> user_info
            sender_map = {str(u["_id"]): u for u in senders}
            
            # Format lại dữ liệu và đảo ngược lại thứ tự để hiển thị từ cũ đến mới
            formatted_messages = []
            for msg in messages:
                msg["id"] = str(msg["_id"])
                msg["conversation_id"] = str(msg["conversation_id"])
                
                # Lấy thông tin người gửi
                s_id = str(msg.get("sender_id", ""))
                sender_info = sender_map.get(s_id, {})
                username = sender_info.get("username", "User")
                
                msg["sender_avatar"] = sender_info.get("avatar", "")

                msg["sender_name"] = username

                if "sender_id" in msg:
                    msg["sender_id"] = s_id
                
                formatted_messages.append(msg)
                
            return formatted_messages[::-1] 

        except Exception as e:
            if isinstance(e, HTTPException): raise e
            raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")

    # ==========================================
    # LUỒNG DÀNH CHO AI / HỆ THỐNG
    # ==========================================
    @staticmethod
    def send_bot_message(conversation_id: str, type: str, content: str, metadata: dict = None):
        new_message = {
            "conversation_id": ObjectId(conversation_id),
            "sender_id": "bot_agent", 
            "type": type,
            "content": content,
            "metadata": metadata,
            "created_at": datetime.now()
        }

        result = Message_collection.insert_one(new_message)
        Conversation_collection.update_one(
            {"_id": ObjectId(conversation_id)},
            {"$set": {"updated_at": datetime.now()}}
        )
        new_message["id"] = str(result.inserted_id)
        new_message["conversation_id"] = str(new_message["conversation_id"])
        return new_message
    
    @staticmethod
    def get_ai_bubble_history(conversation_id: str, current_user_id: str):
        try:
            conv_id = ObjectId(conversation_id)
        except:
            raise HTTPException(status_code=400, detail="ID phòng chat không hợp lệ")
            
        conversation = Conversation_collection.find_one({"_id": conv_id})
        if not conversation or ObjectId(current_user_id) not in conversation.get("members", []):
            raise HTTPException(status_code=403, detail="Bạn không có quyền xem tin nhắn này!")

        cursor = Message_collection.find({
            "conversation_id": conv_id,
            "metadata.is_ai_bubble": True
        }).sort("created_at", 1) 
        
        return list(cursor)

    # ==========================================
    # CỖ MÁY PARSE REPORT THÔNG MINH
    # ==========================================
    @staticmethod
    def _parse_report_text(raw_text: str):
        if not raw_text or not raw_text.strip():
            return "Không có dữ liệu", "Không có dữ liệu"

        text = raw_text.strip()

        pattern = r'(?i)(yesterday|hôm qua|today|hôm nay)\s*[:\-]?\s*'
        parts = re.split(pattern, text)
        
        yesterday_text = ""
        today_text = ""
        
        if len(parts) > 1:
            for i in range(1, len(parts), 2):
                key = parts[i].lower()
                val = parts[i+1].strip(",; \n\t") 
                
                if key in ['yesterday', 'hôm qua']:
                    yesterday_text = val
                elif key in ['today', 'hôm nay']:
                    today_text = val
                    
            return (yesterday_text or "Không có dữ liệu", today_text or "Không có dữ liệu")

        if "|" in text:
            parts = text.split("|", 1)
            return (parts[0].strip() or "Không có dữ liệu", parts[1].strip() or "Không có dữ liệu")

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if len(lines) >= 2:
            return (lines[0].strip("-* "), " ".join(lines[1:]).strip("-* "))

        return "Không có dữ liệu", text

    # ==========================================
    # XỬ LÝ LỆNH TẠO BÁO CÁO (Trích xuất ngày tháng bằng Regex)
    # ==========================================
    @staticmethod
    def _handle_report_command(content: str, conv_id: ObjectId, current_user_id: str):
        content_strip = content.strip()
        raw_text = re.sub(r'^/?report(?:\s+daily)?\s*:?\s*', '', content_strip, flags=re.IGNORECASE)

        report_date = datetime.now().strftime("%Y-%m-%d")

        date_match = re.search(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b', raw_text)
        if date_match:
            date_str = date_match.group(1)
            try:
                date_str_normalized = date_str.replace("-", "/")
                parsed_date = datetime.strptime(date_str_normalized, "%d/%m/%Y")
                report_date = parsed_date.strftime("%Y-%m-%d")
                
                raw_text = raw_text.replace(date_str, "", 1).strip(" ,;:-")
            except ValueError:
                pass 

        yesterday_text, today_text = MessageService._parse_report_text(raw_text)

        # --- ĐÃ FIX: Chống lỗi NoneType ---
        user = users_collection.find_one({"_id": ObjectId(current_user_id)}) or {}
        username = user.get("username", "Unknown")

        report_data = {
            "user_id": ObjectId(current_user_id),
            "user_name": username,
            "date": report_date,
            "yesterday": yesterday_text,
            "today": today_text,
            "conversation_id": conv_id
        }

        created_report = create_report(report_data)

        user_avatar = user.get("avatar", "")

        system_msg = {
            "conversation_id": conv_id,
            "sender_id": ObjectId(current_user_id),
            "type": "report_card", 
            "content": "",
            "metadata": {
                "report_id": str(created_report.get("id", "")),
                "date": created_report.get("date", report_date),
                "user_name": username,
                "user_avatar": user_avatar,
                "yesterday": created_report.get("yesterday", yesterday_text),
                "today": created_report.get("today", today_text)
            },
            "created_at": datetime.now()
        }

        result = Message_collection.insert_one(system_msg)

        Conversation_collection.update_one(
            {"_id": conv_id},
            {"$set": {"updated_at": datetime.now()}}
        )

        system_msg["id"] = str(result.inserted_id)
        system_msg["conversation_id"] = str(system_msg["conversation_id"])
        system_msg["sender_id"] = str(system_msg["sender_id"])

        return system_msg