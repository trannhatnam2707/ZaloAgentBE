from Config.Model import generate_gemini_response
from Utils.Logger import AgentLogger
from Utils.Tools import Tools
from Utils.MCP_Client import mcp_client


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
1. "action" - Thực hiện hành động (tạo report, cập nhật report, tóm tắt report)
2. "question" - Hỏi thông tin về reports đã có

Trả về JSON với format:
{{
    "intent_type": "action" hoặc "question",
    "reason": "giải thích ngắn gọn"
}}

Ví dụ:
- "Tạo report hôm nay cho tôi" → {{"intent_type": "action", "reason": "Người dùng muốn tạo report mới"}}
- "Hôm qua tôi làm gì?" → {{"intent_type": "question", "reason": "Người dùng hỏi về report cũ"}}
- "Cập nhật report ngày 1/1" → {{"intent_type": "action", "reason": "Người dùng muốn cập nhật report"}}
- "Tóm tắt báo cáo tuần này" → {{"intent_type": "action", "reason": "Người dùng muốn tóm tắt"}}
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
            # Làm sạch response
            clean_response = response.replace("```json", "").replace("```", "").strip()
            intent_data = json.loads(clean_response)
            return intent_data
        except:
            # Fallback: nếu không parse được thì mặc định là question
            return {"intent_type": "question", "reason": "Không phân tích được, mặc định là câu hỏi"}
    
    def handle_action(self, username: str, user_query: str) -> dict:
        """Xử lý khi user muốn thực hiện action (gọi MCP)"""
        self.logger.log("Action Detected", f"Gọi MCP Server với message: {user_query}")
        
        # Gọi MCP Server
        mcp_response = mcp_client.ask_mcp(username=username, message=user_query)
        
        if mcp_response.get("success"):
            result = mcp_response.get("result", {})
            self.logger.log("MCP Response", str(result))
            
            # Format câu trả lời cho user
            if "message" in result:
                final_answer = result["message"]
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
    
    def handle_question(self, user_query: str, top_k: int = 5) -> dict:
        """Xử lý khi user hỏi thông tin (search + answer)"""
        # 1. Lập kế hoạch
        planning_prompt = f"""
        {SYSTEM_PROMPT}

        User hỏi: {user_query}
        
        Bắt đầu lập kế hoạch:
        """
        
        plan = generate_gemini_response(question=user_query, system_prompt=planning_prompt)
        self.logger.log("Plan", plan)
        
        # 2. Search reports trong Pinecone
        matches = Tools.search_reports(user_query, top_k=top_k)
        self.logger.log("Act", f"SearchReports[{user_query}]")
        self.logger.log("Observation", f"Tìm thấy {len(matches)} kết quả")
        
        # 3. Gom context từ kết quả search
        context = "\n".join([m.get("metadata", {}).get("text", "") for m in matches]) if matches else ""
        
        # 4. Gọi LLM để ra câu trả lời cuối cùng
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
    
    def run(self, user_query: str, username: str = None, top_k: int = 5) -> dict:
        """
        Main entry point của Agent
        
        Args:
            user_query: Câu hỏi/yêu cầu từ user
            username: Tên user (bắt buộc nếu là action)
            top_k: Số kết quả search
        """
        # Bước 1: Phân tích intent
        intent = self.analyze_intent(user_query)
        intent_type = intent.get("intent_type", "question")
        reason = intent.get("reason", "")
        
        self.logger.log("Intent Analysis", f"Type: {intent_type} - Reason: {reason}")
        
        # Bước 2: Xử lý theo intent
        if intent_type == "action":
            if not username:
                return {
                    "answer": "❌ Cần có username để thực hiện action này.",
                    "logs": self.logger.get_logs()
                }
            return self.handle_action(username, user_query)
        else:
            return self.handle_question(user_query, top_k)