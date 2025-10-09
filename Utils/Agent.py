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
- "tháng 8 nhatnam làm gì?" → {{"intent_type": "question", "reason": "Tra cứu thông tin"}}
- "Cho tôi xem report của John" → {{"intent_type": "question", "reason": "Xem dữ liệu"}}
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
    
    def extract_username_from_query(self, user_query: str) -> str:
        """Trích xuất username từ câu hỏi bằng AI"""
        import json
        
        prompt = f"""
Bạn là một AI trợ lý thông minh. Nhiệm vụ của bạn là phân tích câu sau và tìm TÊN NGƯỜI DÙNG (username) nếu có:

"{user_query}"

Hướng dẫn:
- Username có thể xuất hiện ở nhiều vị trí khác nhau trong câu
- Username thường là một từ đơn hoặc cụm từ không dấu (ví dụ: "nhatnam", "john", "admin", "dinhphuc", "user123")
- Đừng nhầm lẫn username với các từ khóa hệ thống như: "report", "ngày", "tháng", "hôm qua", "hôm nay"
- Phân tích ngữ cảnh để hiểu ai là người được nhắc đến

Ví dụ phân tích:
1. "cập nhật report của bạn dinhphuc ngày 09/10" 
   → Username: "dinhphuc" (người sở hữu report)

2. "nhatnam hôm qua làm gì?"
   → Username: "nhatnam" (chủ thể của câu hỏi)

3. "tạo report cho user john với nội dung ABC"
   → Username: "john" (người nhận report)

4. "tóm tắt báo cáo"
   → Không có username cụ thể

5. "xem report của admin tháng 8"
   → Username: "admin"

Trả về ĐÚNG format JSON (không giải thích thêm):
{{"username": "tên_user_nếu_tìm_thấy", "found": true}}

Hoặc nếu không tìm thấy:
{{"username": "", "found": false}}
"""
        
        try:
            response = generate_gemini_response(question=user_query, system_prompt=prompt)
            
            # Debug: in ra response từ AI
            print(f"🤖 [AI Response]: {response[:300]}...")
            
            # Làm sạch response
            clean_response = response.replace("```json", "").replace("```", "").strip()
            
            # Parse JSON
            result = json.loads(clean_response)
            
            if result.get("found") and result.get("username"):
                extracted = result["username"].strip()
                print(f"✅ [AI] Extracted username: {extracted}")
                return extracted
            else:
                print(f"❌ [AI] No username found in query")
                return None
                
        except json.JSONDecodeError as e:
            print(f"❌ [AI] JSON parse error: {e}")
            print(f"   Raw response: {clean_response[:300]}")
            return None
        except Exception as e:
            print(f"❌ [AI] Unexpected error: {e}")
            return None
    
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
            elif "summary" in result:
                # Trường hợp summarize_report
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
        # 🐛 Debug
        print(f"\n{'='*60}")
        print(f"🔍 [Agent.run] NEW REQUEST")
        print(f"   - Query: {user_query}")
        print(f"   - Username from request: {username}")
        print(f"{'='*60}\n")
        
        # Bước 1: Phân tích intent
        intent = self.analyze_intent(user_query)
        intent_type = intent.get("intent_type", "question")
        reason = intent.get("reason", "")
        
        self.logger.log("Intent Analysis", f"Type: {intent_type} - Reason: {reason}")
        print(f"📊 Intent Type: {intent_type}")
        print(f"💡 Reason: {reason}\n")
        
        # Bước 2: Xử lý theo intent
        if intent_type == "action":
            # Nếu không có username, thử trích xuất từ câu hỏi
            if not username:
                print(f"⚠️  Username not provided, trying to extract from query...")
                extracted_username = self.extract_username_from_query(user_query)
                
                if extracted_username:
                    username = extracted_username
                    print(f"✅ Extracted username: {username}")
                else:
                    print(f"❌ Cannot extract username from query")
                    return {
                        "answer": "❌ Không thể xác định username. Vui lòng đăng nhập hoặc chỉ rõ tên user trong câu hỏi.",
                        "logs": self.logger.get_logs()
                    }
            
            print(f"🎬 Handling ACTION with username: {username}\n")
            return self.handle_action(username, user_query)
        else:
            print(f"❓ Handling QUESTION\n")
            return self.handle_question(user_query, top_k)