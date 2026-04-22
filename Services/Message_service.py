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
            raise HTTPException(status_cod=400, detail="ID phòng chat không hợp lệ")

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
    def get_conversation_messages(conversation_id: str, current_user_id: str, skip: int = 0, limit: int = 50):
        try:    
            conv_id = ObjectId(conversation_id)
        except:
            raise HTTPException(status_code=400, detail="ID phòng chat không hợp lệ")

        conversation = Conversation_collection.find_one({"_id": conv_id})
        if not conversation or ObjectId(current_user_id) not in conversation.get("members", []):
            raise HTTPException(status_code=403, detail="Bạn không có quyền xem tin nhắn này!")

        cursor = Message_collection.find({"conversation_id": conv_id,"metadata.is_ai_bubble": {"$ne": True}})\
                                   .sort("created_at", -1)\
                                   .skip(skip)\
                                   .limit(limit)
        
        messages = list(cursor)

        for msg in messages:
            msg["id"] = str(msg["_id"])
            msg["conversation_id"] = str(msg["conversation_id"])
            msg["sender_id"] = str(msg["sender_id"])

        return messages

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
        conv_id = ObjectId(conversation_id)
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

        raw_text = raw_text.strip()

        # Case 1: Dùng dấu |
        if "|" in raw_text:
            parts = raw_text.split("|", 1)
            yesterday = parts[0].strip()
            today = parts[1].strip()
            return (yesterday or "Không có dữ liệu", today or "Không có dữ liệu")

        # Case 2: Dùng từ khóa "hôm qua", "hôm nay"
        lower_text = raw_text.lower()
        hq = "hôm qua"
        hn = "hôm nay"

        hq_idx = lower_text.find(hq)
        hn_idx = lower_text.find(hn)

        if hq_idx != -1 and hn_idx != -1:
            len_hq = len(hq)
            len_hn = len(hn)
            if hq_idx < hn_idx:
                yesterday = raw_text[hq_idx + len_hq: hn_idx].strip(": -*\n ")
                today = raw_text[hn_idx + len_hn:].strip(": -*\n ")
            else:
                today = raw_text[hn_idx + len_hn: hq_idx].strip(": -*\n ")
                yesterday = raw_text[hq_idx + len_hq:].strip(": -*\n ")
            return (yesterday or "Không có dữ liệu", today or "Không có dữ liệu")

        # Case 3: Xuống dòng (multi-line)
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        if len(lines) >= 2:
            yesterday = lines[0].strip("-* ")
            today = " ".join(lines[1:]).strip("-* ")
            return (yesterday or "Không có dữ liệu", today or "Không có dữ liệu")

        # Case 4: Fallback
        return "Không có dữ liệu", raw_text

    # ==========================================
    # XỬ LÝ LỆNH TẠO BÁO CÁO (Trích xuất ngày tháng bằng Regex)
    # ==========================================
    @staticmethod
    def _handle_report_command(content: str, conv_id: ObjectId, current_user_id: str):
        content_strip = content.strip()
        
        # 1. Bóc chữ "report" hoặc "/report" ở đầu câu
        raw_text = re.sub(r'^/?report\s*:?\s*', '', content_strip, flags=re.IGNORECASE)

        # 2. Tìm xem ngay phần đầu câu có ngày tháng không (VD: 30/3/2026 hoặc 30-03-2026)
        report_date = datetime.now().strftime("%Y-%m-%d") # Mặc định là hôm nay
        
        date_match = re.match(r'^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*:?\s*', raw_text)
        if date_match:
            date_str = date_match.group(1)
            try:
                date_str_normalized = date_str.replace("-", "/")
                parsed_date = datetime.strptime(date_str_normalized, "%d/%m/%Y")
                report_date = parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                report_date = date_str # Lấy chuỗi gốc nếu parse lỗi
                
            # Cắt bỏ phần ngày tháng ra khỏi raw_text để parse nội dung sạch sẽ hơn
            raw_text = raw_text[date_match.end():]

        # 3. Parse nội dung
        yesterday_text, today_text = MessageService._parse_report_text(raw_text)

        # 4. Lấy thông tin user
        user = users_collection.find_one({"_id": ObjectId(current_user_id)})
        username = user["username"] if user and "username" in user else "Unknown"

        # 5. Tạo dữ liệu report
        report_data = {
            "user_name": username,
            "date": report_date,
            "yesterday": yesterday_text,
            "today": today_text,
            "conversation_id": conv_id # Nhồi conversation_id vào để lưu xuống DB Report
        }

        # Lưu report (Hàm này sẽ tự động gọi sync_one_report sang Pinecone)
        created_report = create_report(report_data)

        # 6. Tạo thẻ message hệ thống báo cáo thành công
        system_msg = {
            "conversation_id": conv_id,
            "sender_id": ObjectId(current_user_id),
            "type": "report_card",
            "content": f"Đã tạo báo cáo ngày {created_report.get('date')}",
            "metadata": {
                "report_id": created_report.get("id"),
                "yesterday": created_report.get("yesterday"),
                "today": created_report.get("today")
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