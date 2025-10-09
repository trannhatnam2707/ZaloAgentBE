from Config.Model import generate_gemini_response
from Utils.Logger import AgentLogger
from Utils.Tools import Tools
from Utils.MCP_Client import mcp_client
from datetime import datetime, timedelta


SYSTEM_PROMPT = """
Bạn là một Agent hỗ trợ phân tích báo cáo công việc hàng ngày.
Bạn có thể sử dụng các công cụ sau:
    - search_reports[query]: tìm các thông tin vector từ Pinecone database.
    - Answer [context, question]: dùng LLM để tạo câu trả lời dựa vào context
    - MCP Tools: create_report, update_report, summarize_report

Luôn làm theo kế hoạch:
Plan: mô tả kế hoạch
Act: chọn công cụ và tham số để thực hiện kế hoạch
Observation: Quan sát kết quả trả về
Final answer: câu trả lời cuối cùng cho người dùng
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

Ví dụ phân loại:
- "Tạo report hôm nay cho tôi" → {{"intent_type": "action", "reason": "Tạo dữ liệu mới"}}
- "Cập nhật report ngày 1/1 với nội dung ABC" → {{"intent_type": "action", "reason": "Cập nhật dữ liệu"}}
- "Hôm qua tôi làm gì?" → {{"intent_type": "question", "reason": "Truy vấn thông tin"}}
- "Tóm tắt báo cáo tuần này" → {{"intent_type": "question", "reason": "Đọc và tóm tắt dữ liệu có sẵn"}}
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
        Chuẩn hóa câu hỏi bằng cách:
        1. Thay "tôi", "mình", "em" → username
        2. Thay "hôm qua" → ngày cụ thể
        3. Thay "hôm nay" → ngày cụ thể
        """
        import json
        
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        prompt = f"""
Chuẩn hóa câu hỏi sau để tìm kiếm trong database:

Câu gốc: "{user_query}"
Username: {username}
Ngày hôm nay: {today}
Ngày hôm qua: {yesterday}

QUY TẮC:
1. Thay "tôi", "mình", "em" → {username}
2. Thay "hôm qua" → {yesterday}
3. Thay "hôm nay" → {today}
4. Giữ nguyên ý nghĩa câu hỏi gốc

VÍ DỤ:
- "tôi hôm qua làm gì?" → "{username} ngày {yesterday} làm gì?"
- "hôm nay mình có task gì?" → "{username} ngày {today} có task gì?"
- "hôm qua làm được gì?" → "{username} ngày {yesterday} làm được gì?"

Trả về JSON:
{{
    "normalized_query": "câu hỏi đã chuẩn hóa"
}}
"""
        
        try:
            response = generate_gemini_response(question=user_query, system_prompt=prompt)
            clean_response = response.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean_response)
            normalized = result.get("normalized_query", user_query)
            print(f"🔄 Normalized query: '{user_query}' → '{normalized}'")
            return normalized
        except Exception as e:
            print(f"⚠️ Cannot normalize query: {e}, using original")
            return user_query
    
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
        
        # ✅ Chuẩn hóa câu hỏi với username
        search_query = self.normalize_query_with_context(user_query, username)
        
        # Lập kế hoạch
        planning_prompt = f"""
        {SYSTEM_PROMPT}

        User {username} hỏi: {user_query}
        
        Bắt đầu lập kế hoạch:
        """
        
        plan = generate_gemini_response(question=user_query, system_prompt=planning_prompt)
        self.logger.log("Plan", plan)
        
        # Search reports trong Pinecone với query đã chuẩn hóa
        matches = Tools.search_reports(search_query, top_k=top_k)
        self.logger.log("Act", f"SearchReports[{search_query}]")
        self.logger.log("Observation", f"Tìm thấy {len(matches)} kết quả")
        
        # Gom context từ kết quả search
        context = "\n".join([m.get("metadata", {}).get("text", "") for m in matches]) if matches else ""
        
        # Gọi LLM để ra câu trả lời cuối cùng
        final_answer = Tools.ask_llm(
            question=user_query,
            context=context,
            system_prompt=SYSTEM_PROMPT
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
        
        # ✅ Kiểm tra username
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