import re
from datetime import datetime, timedelta
from Config.Model import generate_gemini_response
from Utils.Logger import AgentLogger
from Utils.Tools import Tools
from Utils.MCP_Client import mcp_client

# ✅ SYSTEM PROMPT ĐÃ ĐƯỢC SỬA - Bắt buộc chỉ dùng context thực tế
SYSTEM_PROMPT = """
Bạn là một Agent hỗ trợ trả lời câu hỏi về báo cáo công việc hàng ngày.

NGUYÊN TẮC QUAN TRỌNG:
1. CHỈ trả lời dựa trên CONTEXT được cung cấp từ database
2. TUYỆT ĐỐI KHÔNG tự bịa hoặc suy đoán thông tin không có trong context
3. Nếu không tìm thấy thông tin trong context → trả lời rõ ràng là "Không tìm thấy thông tin"

CÁC CÔNG CỤ:
- search_reports[query]: Tìm kiếm thông tin từ Pinecone database
- Answer[context, question]: Tạo câu trả lời DỰA TRÊN context có sẵn

QUY TRÌNH:
1. Plan: Lập kế hoạch ngắn gọn
2. Act: Gọi search_reports với query phù hợp
3. Observation: Mô tả kết quả TÌM ĐƯỢC (không bịa)
4. Final answer: Trả lời DỰA TRÊN context, nếu không có → nói rõ không tìm thấy
"""

INTENT_ANALYSIS_PROMPT = """
Phân tích ý định của người dùng từ câu hỏi/yêu cầu sau:
"{user_query}"

Xác định xem người dùng muốn:
1. "action" - Thực hiện hành động CẬP NHẬT/TẠO MỚI dữ liệu (tạo report mới, cập nhật report có sẵn)
2. "question" - Hỏi thông tin/tra cứu/tóm tắt về reports đã có

⚠️ QUAN TRỌNG - Phân biệt rõ:
- Các từ khóa "TẠO MỚI" hoặc "CẬP NHẬT" dữ liệu → "action"
  Ví dụ: "tạo report", "cập nhật report", "sửa report", "thêm vào report"
  
- Các từ khóa "ĐỌC/TRA CỨU/TÓM TẮT" dữ liệu có sẵn → "question"
  Ví dụ: "tóm tắt", "hỏi", "xem", "kiểm tra", "báo cáo", "làm gì", "có gì"

Trả về JSON với format:
{{
    "intent_type": "action" hoặc "question",
    "reason": "giải thích ngắn gọn"
}}
"""


class Agent:
    def __init__(self, llm: str = "gemini-2.5-flash"):
        self.llm = llm
        self.logger = AgentLogger()
    
    def analyze_intent(self, user_query: str) -> dict:
        """Phân tích ý định người dùng: action hay question"""
        import json
        
        prompt = INTENT_ANALYSIS_PROMPT.format(user_query=user_query)
        response = generate_gemini_response(question=user_query, system_prompt=prompt)
        
        try:
            clean_response = response.replace("```json", "").replace("```", "").strip()
            intent_data = json.loads(clean_response)
            return intent_data
        except:
            return {"intent_type": "question", "reason": "Không phân tích được, mặc định là câu hỏi"}
    
    def normalize_query_with_context(self, user_query: str, username: str) -> str:
        """
        Chuẩn hóa câu hỏi bằng regex + datetime (không dùng AI)
        1. Thay "tôi", "mình", "em" → username
        2. Chuyển đổi các format ngày → YYYY-MM-DD
        3. Thay "hôm qua", "hôm nay" → ngày cụ thể
        """
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        current_year = today.year
        
        normalized = user_query
        
        # Bước 1: Thay đại từ nhân xưng → username
        normalized = re.sub(r'\b(tôi|mình|em)\b', username, normalized, flags=re.IGNORECASE)
        
        # Bước 2: Thay "hôm qua" → ngày cụ thể
        normalized = re.sub(r'\bhôm qua\b', yesterday.strftime("%Y-%m-%d"), normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bhôm nay\b', today.strftime("%Y-%m-%d"), normalized, flags=re.IGNORECASE)
        
        # Bước 3: Chuyển đổi format ngày
        # Pattern: dd/mm/yyyy hoặc dd/mm/yy
        def replace_date_full(match):
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3))
            if year < 100:  # 2 chữ số năm
                year += 2000
            try:
                date_obj = datetime(year, month, day)
                return date_obj.strftime("%Y-%m-%d")
            except:
                return match.group(0)
        
        normalized = re.sub(r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b', replace_date_full, normalized)
        
        # Pattern: dd/mm (không có năm) → thêm năm hiện tại
        def replace_date_short(match):
            day = int(match.group(1))
            month = int(match.group(2))
            try:
                date_obj = datetime(current_year, month, day)
                return date_obj.strftime("%Y-%m-%d")
            except:
                return match.group(0)
        
        # Chỉ thay thế nếu chưa có format YYYY-MM-DD
        if not re.search(r'\d{4}-\d{2}-\d{2}', normalized):
            normalized = re.sub(r'\b(\d{1,2})/(\d{1,2})\b', replace_date_short, normalized)
        
        # Pattern: "ngày X tháng Y" → YYYY-MM-DD
        def replace_date_text(match):
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3)) if match.group(3) else current_year
            try:
                date_obj = datetime(year, month, day)
                return date_obj.strftime("%Y-%m-%d")
            except:
                return match.group(0)
        
        normalized = re.sub(
            r'ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})(?:\s+năm\s+(\d{4}))?',
            replace_date_text,
            normalized,
            flags=re.IGNORECASE
        )
        
        # Log để debug
        if normalized != user_query:
            print(f"🔄 [NORMALIZE]")
            print(f"   Input:  '{user_query}'")
            print(f"   Output: '{normalized}'")
        
        return normalized
    
    def handle_action(self, username: str, user_query: str) -> dict:
        """Xử lý khi user muốn thực hiện action (gọi MCP)"""
        self.logger.log("Action Detected", f"Gọi MCP Server với message: {user_query}")
        
        mcp_response = mcp_client.ask_mcp(username=username, message=user_query)
        
        if mcp_response.get("success"):
            result = mcp_response.get("result", {})
            self.logger.log("MCP Response", str(result))
            
            if "message" in result:
                final_answer = result["message"]
            elif "summary" in result:
                final_answer = f"📊 Tóm tắt báo cáo:\n\n{result['summary']}"
            else:
                final_answer = "✅ Đã thực hiện thành công yêu cầu của bạn."
            
            return {
                "answer": final_answer,
                "logs": self.logger.get_logs(),
                "mcp_result": result
            }
        else:
            error_msg = mcp_response.get("error", "Lỗi không xác định từ MCP Server")
            self.logger.log("MCP Error", error_msg)
            return {
                "answer": f"❌ {error_msg}",
                "logs": self.logger.get_logs()
            }
    
    def handle_question(self, user_query: str, username: str, top_k: int = 10) -> dict:
        """Xử lý khi user hỏi thông tin (search + answer)"""
        
        # Chuẩn hóa câu hỏi với username
        search_query = self.normalize_query_with_context(user_query, username)
        
        # ✅ SỬA: Bỏ planning step - LLM không cần plan, chỉ cần search và answer
        self.logger.log("Search Query", search_query)
        
        # Search reports trong Pinecone với query đã chuẩn hóa
        matches = Tools.search_reports(search_query, top_k=top_k)
        self.logger.log("Search Results", f"Tìm thấy {len(matches)} kết quả")
        
        # Gom context từ kết quả search
        if matches:
            context_parts = []
            for m in matches:
                text = m.get("metadata", {}).get("text", "")
                context_parts.append(text)
            context = "\n\n---\n\n".join(context_parts)
        else:
            context = ""
        
        # ✅ PROMPT MỚI: Bắt buộc chỉ dùng context
        answer_prompt = f"""
Bạn là trợ lý AI trả lời câu hỏi về báo cáo công việc.

QUY TẮC BẮT BUỘC:
1. CHỈ sử dụng thông tin có trong CONTEXT bên dưới
2. KHÔNG tự bịa hoặc suy đoán thông tin
3. Nếu context KHÔNG có thông tin cần thiết → Trả lời: "Không tìm thấy thông tin về [vấn đề] trong các báo cáo."
4. Khi trả lời, trích xuất CHÍNH XÁC từ context (tên người, ngày, công việc)

CONTEXT TỪ DATABASE:
{context if context else "Không có dữ liệu liên quan."}

CÂU HỎI: {user_query}

HÃY TRẢ LỜI:
- Nếu có thông tin trong context → Tóm tắt rõ ràng
- Nếu không có thông tin → Nói rõ không tìm thấy
"""
        
        # Gọi LLM để ra câu trả lời cuối cùng
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
    
    def run(self, user_query: str, username: str, top_k: int = 10) -> dict:
        """
        Main entry point của Agent
        
        Args:
            user_query: Câu hỏi/yêu cầu từ user
            username: Tên user đang đăng nhập (BẮT BUỘC)
            top_k: Số kết quả search
        """
        print(f"\n{'='*120}")
        print(f"🔍 [Agent.run] NEW REQUEST")
        print(f"   - User: {username}")
        print(f"   - Query: {user_query}")
        print(f"{'='*120}\n")
        
        # Kiểm tra username
        if not username:
            return {
                "answer": "❌ Lỗi: Không xác định được user. Vui lòng đăng nhập lại.",
                "logs": self.logger.get_logs()
            }
        
        # Bước 1: Phân tích intent
        intent = self.analyze_intent(user_query)
        intent_type = intent.get("intent_type", "question")
        reason = intent.get("reason", "")
        
        self.logger.log("Intent Analysis", f"Type: {intent_type} - Reason: {reason}")
        print(f"📊 Intent Type: {intent_type}")
        print(f"💡 Reason: {reason}\n")
        
        # Bước 2: Xử lý theo intent
        if intent_type == "action":
            print(f"🎬 Handling ACTION for user: {username}\n")
            return self.handle_action(username, user_query)
        else:
            print(f"❓ Handling QUESTION for user: {username}\n")
            return self.handle_question(user_query, username, top_k)