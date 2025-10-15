import re
from datetime import datetime, timedelta
from typing import List, Dict
from Config.Model import generate_gemini_response
from Utils.Logger import AgentLogger
from Utils.Tools import Tools
from Utils.MCP_Client import mcp_client

# ✅ SYSTEM PROMPT - Agent như người tư vấn viên
ADVISOR_SYSTEM_PROMPT = """
Bạn là một TƯ VẤN VIÊN THÔNG MINH và THÂN THIỆN, hỗ trợ quản lý và tra cứu báo cáo công việc.

TÍNH CÁCH:
- Thân thiện, nhiệt tình, luôn sẵn sàng giúp đỡ
- Giao tiếp tự nhiên như người thật, không cứng nhắc
- Chủ động đưa ra gợi ý khi phù hợp
- Nhớ và tham chiếu đến các cuộc trò chuyện trước đó
- Giải thích rõ ràng khi người dùng không hiểu

KHẢ NĂNG:
1. 🔍 TRA CỨU: Tìm kiếm thông tin về báo cáo công việc
2. 📝 TẠO MỚI: Giúp tạo báo cáo mới
3. ✏️ CẬP NHẬT: Cập nhật/sửa báo cáo có sẵn
4. 📊 TÓM TẮT: Tóm tắt công việc theo ngày/tuần/tháng
5. 💬 TƯ VẤN: Tư vấn cách viết báo cáo hiệu quả

CÁCH TRẢ LỜI:
- Nếu người dùng hỏi mơ hồ → Hỏi lại để làm rõ (ví dụ: "Bạn muốn xem báo cáo ngày nào nhỉ?")
- Nếu không có dữ liệu → Gợi ý hành động tiếp theo
- Nếu người dùng cần tạo/cập nhật → Hướng dẫn từng bước
- Luôn kết thúc bằng câu hỏi hoặc gợi ý nếu phù hợp

QUY TẮC QUAN TRỌNG:
- CHỈ trả lời dựa trên CONTEXT hoặc kết quả SEARCH
- KHÔNG bịa thông tin không có trong dữ liệu
- Nếu không tìm thấy → Nói rõ và đề xuất giải pháp
- Sử dụng emoji một cách tự nhiên để thân thiện hơn
"""

class ConversationMemory:
    """Quản lý bộ nhớ chat session"""
    
    def __init__(self, max_history: int = 10):
        self.messages: List[Dict] = []
        self.max_history = max_history
    
    def add_user_message(self, message: str):
        """Thêm tin nhắn từ user"""
        self.messages.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        self._trim_history()
    
    def add_assistant_message(self, message: str):
        """Thêm tin nhắn từ assistant"""
        self.messages.append({
            "role": "assistant",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        self._trim_history()
    
    def _trim_history(self):
        """Giữ lại N tin nhắn gần nhất"""
        if len(self.messages) > self.max_history * 2:  # user + assistant = 2 messages
            self.messages = self.messages[-(self.max_history * 2):]
    
    def get_context_string(self) -> str:
        """Chuyển lịch sử thành chuỗi context cho LLM"""
        if not self.messages:
            return ""
        
        context_parts = []
        for msg in self.messages[-6:]:  # Lấy 3 cặp hội thoại gần nhất
            role = "Người dùng" if msg["role"] == "user" else "Tư vấn viên"
            context_parts.append(f"{role}: {msg['content']}")
        
        return "\n".join(context_parts)
    
    def clear(self):
        """Xóa lịch sử (khi user muốn bắt đầu lại)"""
        self.messages = []
    
    def get_summary(self) -> str:
        """Tóm tắt ngắn gọn cuộc trò chuyện"""
        if not self.messages:
            return "Chưa có cuộc trò chuyện nào."
        
        user_messages = [m["content"] for m in self.messages if m["role"] == "user"]
        return f"Đã trao đổi {len(self.messages)} tin nhắn về: {', '.join(user_messages[:3])}"


class ConversationalAgent:
    """Agent với khả năng ghi nhớ và tư vấn"""
    
    def __init__(self):
        self.logger = AgentLogger()
        # Dictionary lưu memory theo session_id
        self.sessions: Dict[str, ConversationMemory] = {}
    
    def get_or_create_session(self, session_id: str) -> ConversationMemory:
        """Lấy hoặc tạo session mới"""
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationMemory(max_history=10)
        return self.sessions[session_id]
    
    def clear_session(self, session_id: str):
        """Xóa lịch sử chat của session"""
        if session_id in self.sessions:
            self.sessions[session_id].clear()
            return True
        return False
    
    def normalize_query(self, user_query: str, username: str) -> str:
        """Chuẩn hóa câu hỏi với context ngày tháng và username"""
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        current_year = today.year
        
        normalized = user_query
        
        # Thay đại từ → username
        normalized = re.sub(r'\b(tôi|mình|em)\b', username, normalized, flags=re.IGNORECASE)
        
        # Thay thời gian tương đối
        normalized = re.sub(r'\bhôm qua\b', yesterday.strftime("%Y-%m-%d"), normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bhôm nay\b', today.strftime("%Y-%m-%d"), normalized, flags=re.IGNORECASE)
        
        # Chuyển đổi format ngày dd/mm/yyyy → YYYY-MM-DD
        def replace_date_full(match):
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            if year < 100:
                year += 2000
            try:
                return datetime(year, month, day).strftime("%Y-%m-%d")
            except:
                return match.group(0)
        
        normalized = re.sub(r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b', replace_date_full, normalized)
        
        # dd/mm → YYYY-MM-DD
        def replace_date_short(match):
            day, month = int(match.group(1)), int(match.group(2))
            try:
                return datetime(current_year, month, day).strftime("%Y-%m-%d")
            except:
                return match.group(0)
        
        if not re.search(r'\d{4}-\d{2}-\d{2}', normalized):
            normalized = re.sub(r'\b(\d{1,2})/(\d{1,2})\b', replace_date_short, normalized)
        
        return normalized
    
    def analyze_intent_with_context(self, user_query: str, chat_history: str) -> dict:
        """Phân tích ý định với context từ lịch sử chat"""
        prompt = f"""
Bạn là trợ lý phân tích ý định người dùng trong hệ thống quản lý báo cáo công việc.

LỊCH SỬ HỘI THOẠI GẦN ĐÂY:
{chat_history if chat_history else "Chưa có lịch sử"}

TIN NHẮN MỚI: "{user_query}"

Xác định ý định người dùng:
1. "action" - Muốn TẠO MỚI/CẬP NHẬT dữ liệu (tạo report, sửa report, thêm task)
2. "question" - Muốn TRA CỨU/HỎI thông tin (xem report, tóm tắt, hỏi làm gì)
3. "clarification_needed" - Câu hỏi mơ hồ, cần hỏi lại để làm rõ
4. "chitchat" - Chat thường, chào hỏi, cảm ơn

QUAN TRỌNG:
- Nếu user nói "cập nhật", "sửa", "thay đổi" → action
- Nếu user nói "xem", "tóm tắt", "làm gì" → question
- Nếu thiếu thông tin quan trọng (ngày, nội dung) → clarification_needed
- Dựa vào lịch sử để hiểu ngữ cảnh (ví dụ: "nó" có thể là report đã nhắc trước)

Trả về JSON:
{{
    "intent_type": "action | question | clarification_needed | chitchat",
    "confidence": 0.0-1.0,
    "reason": "giải thích ngắn gọn",
    "missing_info": ["list các thông tin còn thiếu nếu có"]
}}
"""
        
        response = generate_gemini_response(question=user_query, system_prompt=prompt)
        
        try:
            import json
            clean = response.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except:
            return {
                "intent_type": "question",
                "confidence": 0.5,
                "reason": "Không phân tích được, mặc định là question"
            }
    
    def handle_chitchat(self, user_query: str, chat_history: str) -> str:
        """Xử lý chat thường, chào hỏi"""
        prompt = f"""
Bạn là tư vấn viên thân thiện đang chat với người dùng.

LỊCH SỬ:
{chat_history}

NGƯỜI DÙNG: {user_query}

Hãy trả lời tự nhiên, thân thiện. Nếu phù hợp, gợi ý họ có thể làm gì với hệ thống 
(ví dụ: "Bạn muốn tôi giúp gì không? Tôi có thể giúp bạn xem báo cáo hoặc tạo báo cáo mới đấy!")
"""
        return generate_gemini_response(question=user_query, system_prompt=prompt)
    
    def handle_clarification(self, user_query: str, missing_info: List[str], chat_history: str) -> str:
        """Xử lý khi cần làm rõ thông tin"""
        prompt = f"""
Người dùng nói: "{user_query}"

Thông tin còn thiếu: {', '.join(missing_info)}

LỊCH SỬ:
{chat_history}

Hãy hỏi lại một cách tự nhiên để làm rõ thông tin. 
Ví dụ: 
- Thiếu ngày → "Bạn muốn xem báo cáo ngày nào nhỉ? Hôm nay hay ngày cụ thể nào đó?"
- Thiếu nội dung → "Bạn muốn cập nhật nội dung gì vào báo cáo?"
"""
        return generate_gemini_response(question=user_query, system_prompt=prompt)
    
    def handle_action(self, username: str, user_query: str, chat_history: str) -> dict:
        """Xử lý action với context từ lịch sử"""
        self.logger.log("Action Handler", f"Processing action for user: {username}")
        
        # Tạo context-aware message cho MCP
        enhanced_query = f"""
LỊCH SỬ HỘI THOẠI:
{chat_history}

YÊU CẦU MỚI: {user_query}

Hãy xử lý yêu cầu trên dựa trên ngữ cảnh từ lịch sử (nếu có).
"""
        
        mcp_response = mcp_client.ask_mcp(username=username, message=enhanced_query)
        
        if mcp_response.get("success"):
            result = mcp_response.get("result", {})
            
            # Tạo câu trả lời thân thiện hơn
            if "message" in result:
                base_message = result["message"]
                friendly_response = f"{base_message}\n\n💡 Bạn có cần tôi giúp gì thêm không?"
            elif "summary" in result:
                friendly_response = f"📊 Đây là tóm tắt báo cáo của bạn:\n\n{result['summary']}\n\n✨ Bạn muốn xem chi tiết hơn không?"
            else:
                friendly_response = "✅ Đã xong! Tôi có thể giúp gì thêm cho bạn không?"
            
            return {
                "answer": friendly_response,
                "logs": self.logger.get_logs(),
                "mcp_result": result
            }
        else:
            error_msg = mcp_response.get("error", "Có lỗi xảy ra")
            return {
                "answer": f"❌ Xin lỗi, {error_msg}. Bạn có thể thử lại hoặc diễn đạt khác được không?",
                "logs": self.logger.get_logs()
            }
    
    def handle_question(self, user_query: str, username: str, chat_history: str, top_k: int = 10) -> dict:
        """Xử lý câu hỏi với context"""
        
        # Chuẩn hóa query
        search_query = self.normalize_query(user_query, username)
        self.logger.log("Search Query", search_query)
        
        # Search với context từ lịch sử
        matches = Tools.search_reports(search_query, top_k=top_k)
        self.logger.log("Search Results", f"Tìm thấy {len(matches)} kết quả")
        
        # Tạo context từ search results
        if matches:
            context_parts = []
            for m in matches:
                text = m.get("metadata", {}).get("text", "")
                score = m.get("score", 0)
                context_parts.append(f"[Độ liên quan: {score:.2f}]\n{text}")
            context = "\n\n---\n\n".join(context_parts)
        else:
            context = ""
        
        # Tạo prompt với lịch sử chat
        answer_prompt = f"""
{ADVISOR_SYSTEM_PROMPT}

LỊCH SỬ HỘI THOẠI:
{chat_history}

DỮ LIỆU TÌM ĐƯỢC:
{context if context else "Không tìm thấy dữ liệu liên quan."}

CÂU HỎI MỚI: {user_query}

HƯỚNG DẪN TRẢ LỜI:
1. Nếu có dữ liệu → Trả lời chi tiết, tham chiếu đến lịch sử nếu liên quan
2. Nếu không có dữ liệu → Nói rõ và gợi ý:
   - "Tôi chưa thấy báo cáo nào về [vấn đề] của bạn. Bạn có muốn tạo báo cáo mới không?"
   - "Có vẻ như chưa có dữ liệu cho ngày này. Tôi có thể giúp bạn tạo không?"
3. Kết thúc bằng câu hỏi hoặc gợi ý phù hợp
4. Sử dụng emoji tự nhiên (không quá nhiều)

Hãy trả lời như một người tư vấn viên thân thiện!
"""
        
        final_answer = generate_gemini_response(
            question=user_query,
            context=context,
            system_prompt=answer_prompt
        )
        
        self.logger.log("Final Answer", final_answer)
            
        return {
            "answer": final_answer,
            "logs": self.logger.get_logs()
        }
    
    def run(self, user_query: str, username: str, session_id: str, top_k: int = 10) -> dict:
        """
        Main entry point với memory
        
        Args:
            user_query: Câu hỏi/yêu cầu
            username: Tên user đăng nhập
            session_id: ID phiên chat (dùng user_id hoặc unique identifier)
            top_k: Số kết quả search
        """
        print(f"\n{'='*120}")
        print(f"💬 [Conversational Agent] NEW MESSAGE")
        print(f"   - Session: {session_id}")
        print(f"   - User: {username}")
        print(f"   - Query: {user_query}")
        print(f"{'='*120}\n")
        
        # Lấy hoặc tạo session
        memory = self.get_or_create_session(session_id)
        
        # Lưu tin nhắn user
        memory.add_user_message(user_query)
        
        # Lấy context từ lịch sử
        chat_history = memory.get_context_string()
        
        # Xử lý lệnh đặc biệt
        if user_query.strip().lower() in ["clear", "xóa lịch sử", "bắt đầu lại"]:
            self.clear_session(session_id)
            response = "🔄 Đã xóa lịch sử chat. Chúng ta bắt đầu lại nhé! Tôi có thể giúp gì cho bạn?"
            memory.add_assistant_message(response)
            return {"answer": response, "logs": self.logger.get_logs()}
        
        # Phân tích intent với context
        intent = self.analyze_intent_with_context(user_query, chat_history)
        intent_type = intent.get("intent_type", "question")
        confidence = intent.get("confidence", 0.5)
        missing_info = intent.get("missing_info", [])
        
        self.logger.log("Intent Analysis", f"Type: {intent_type} (confidence: {confidence})")
        print(f"🎯 Intent: {intent_type} ({confidence:.0%})")
        print(f"💭 Reason: {intent.get('reason', '')}\n")
        
        # Xử lý theo intent
        if intent_type == "chitchat":
            answer = self.handle_chitchat(user_query, chat_history)
            result = {"answer": answer, "logs": self.logger.get_logs()}
        
        elif intent_type == "clarification_needed":
            answer = self.handle_clarification(user_query, missing_info, chat_history)
            result = {"answer": answer, "logs": self.logger.get_logs()}
        
        elif intent_type == "action":
            result = self.handle_action(username, user_query, chat_history)
        
        else:  # question
            result = self.handle_question(user_query, username, chat_history, top_k)
        
        # Lưu câu trả lời vào memory
        memory.add_assistant_message(result["answer"])
        
        # Thêm thông tin session vào response
        result["session_info"] = {
            "session_id": session_id,
            "message_count": len(memory.messages),
            "summary": memory.get_summary()
        }
        
        return result


# Singleton instance
conversational_agent = ConversationalAgent()