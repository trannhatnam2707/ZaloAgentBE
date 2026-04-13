from datetime import datetime
import os
from typing import Dict, List
from google import genai
from google.genai import types
from Utils.Logger import AgentLogger
from MCP_Server.Agent_Tools import GEMINI_TOOLS

#Bộ nhớ lưu trữ ngữ cảnh (memory)
class ConversationMemory:
    def __init__(self, max_history: int = 10):
        self.messages: List[Dict] = []
        self.max_history = max_history

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role,"content": content})
        if len(self.messages) > self.max_history:
            # -1 = phần tử cuối
            # -2 = phần tử kế cuối
            # -N = đếm từ cuối lên
            self.messages = self.messages[-self.max_history:] 
        
    def get_gemini_history(self) -> list:
        history = []
        for msg in self.messages:
            history.append(types.Content(
                role = msg["role"],
                parts = [types.Part.from_text(text=msg["content"])]
            ))
        return history
    
    def clear(self):
        self.messages = []

#Agent (đóng vai MCP clients)
class ConversationAgent:
    def __init__(self):
        self.logger = AgentLogger()
        self.session: Dict[str, ConversationMemory] = {}
    
        #khởi tạo SDK Google GenAI (Bản mới)
        self.ai_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

        #In log khởi tạo thành công
        print("\n" + "="*50)
        print(f" [SYSTEM] Khởi tạo Agent thành công")
        print(f" [SYSTEM] Số lượng Tools đã nạp: {len(GEMINI_TOOLS)}")
        print("="*50 + "\n")

    def get_or_create_session(self, session_id: str) -> ConversationMemory:
        if session_id not in self.session:
            print(f" [SYSTEM] Tạo bộ nhớ mới cho phòng chat: {session_id}")
            self.session[session_id] = ConversationMemory()
        return self.session[session_id]

    def clear_session(self, session_id: str) -> bool:
        if session_id in self.session:
            del self.session[session_id]
            print(f" [SYSTEM] Xóa bộ nhớ cũ cho phòng chat: {session_id}")
            return True
        return False      

    def run(self, user_query: str, username: str, user_id: str, session_id: str, top_k: int = 10) -> dict:
        print("\n" + "-"*50)
        print(f" [NEW REQUEST] Bắt đầu xử lý tin nhắn...")
        print(f" [SYSTEM] User Query: {user_query}")
        print("-"*50 + "\n")

        memory = self.get_or_create_session(session_id)
        self.logger.log("USER INPUT", f"[{username}] : {user_query}")

        # -----------------------------------------------------
        #  BỘ NÃO ĐIỀU PHỐI (SYSTEM PROMPT)
        # -----------------------------------------------------

        system_instruction = f"""
            Bạn là TƯ VẤN VIÊN THÔNG MINH hỗ trợ quản lý báo cáo công việc trên App.
            Bạn đang nói chuyện với người dùng là "{username}" với ID là "{user_id}". Hãy xưng hô thân thiện và lịch sự.

            THÔNG TIN HỆ THỐNG:
            - Hôm nay là ngày {datetime.now().strftime("%d/%m/%Y")}. Hãy dùng ngày này làm mốc nếu người dùng nói "hôm nay", "hôm qua" hoặc "Today", "yesterday". (Có thể dùng các từ khác hoặc ngoại ngữ nhưng có nghĩa tương tự)
            - ID phòng chat hiện tại (conversation_id) là: "{session_id}". Hãy tự động truyền ID này vào các Tool yêu cầu 'conversation_id' mà không cần hỏi người dùng.
            - Tên người đang chat là "{username}". CHỈ dùng tên này cho tool_create_report (tham số user_name khi họ tạo báo cáo cho chính họ). Không dùng tên này để giới hạn tìm kiếm toàn phòng.
            - Quyền truy cập: backend đã kiểm tra user có trong phòng chat; bạn trả lời theo TOÀN BỘ báo cáo trong conversation_id, không coi như chỉ có báo cáo của người đang hỏi.
            - Khi gọi tool_search_reports: tham số `query` chỉ mô tả ý hỏi (công việc, thời gian, chủ đề). TUYỆT ĐỐI không tự ghép tên "{username}" vào `query` trừ khi người dùng hỏi rõ về họ.
            - Nếu họ hỏi về một đồng nghiệp cụ thể, dùng `filter_reporter_name` với tên/username người đó (nếu họ nêu rõ).

            QUY TẮC SỬ DỤNG TOOLS:
            1. Bạn Có các công cụ để thao tác với Database. Hãy ưu tiên dùng chúng khi user yêu cầu tạo, sửa, xóa , tìm báo cáo.
            2. Nếu user yêu cầu và bạn quyết định dùng tools nhưng user đưa thiếu thông tin ví dụ như muốn tạo report mới nhưng thiếu ngày hoặc thiếu nội dung ,.. thì bạn tuyệt đối không được dùng tools liền
                => hãy hỏi user cấp thêm thông tin cần thiết
            3. TUYỆT ĐỐI KHÔNG tự bịa ra dữ liệu để điền vào Tool. Chỉ gọi Tool khi user đã cung cấp RÕ RÀNG.
            4. Với thao tác XÓA hoặc CẬP NHẬT: Nếu khách chưa cung cấp ID báo cáo (report_id), hãy chủ động dùng Tool Tìm kiếm (tool_search_reports) để dò tìm ID trước, sau đó hỏi lại khách xem có đúng cái báo cáo đó không rồi mới Xóa/Sửa.
        """
        
        config = types.GenerateContentConfig(
            system_instruction = system_instruction,
            tools = GEMINI_TOOLS,
            temperature = 0.5 #Độ sáng tạo của response (0.0 - 1.0)
        )
        try:
            print(f"[AGENT] Đang gửi request và tools đến cho Gemini...")
            chat = self.ai_client.chats.create(
                model = "gemini-2.5-flash",
                config = config,
                history = memory.get_gemini_history(),
            )

            response = chat.send_message(user_query)

            if response.function_calls:
                for call in response.function_calls:
                    print(f" [TOOLS CALLED] Gemini đã kích hoạt gọi Tools: {call.name}() ")
                    print(f" [TOOLS ARG]: tham số truyền vào {call.arg}")
            else:
                print(f"[NO TOOL] Gemini quyết định trả lời chay, không dùng tool. ") 

            final_answer = response.text
            print(f"[AI REPLY] : {final_answer}")
            print("-" *50)

            memory.add_message("user", user_query)
            memory.add_message("model", final_answer)

            self.logger.log("AI_RESPONSE", final_answer)

            return {
                "answer": final_answer,
                "logs": self.logger.get_logs(),
                "session_infor":{
                    "session_id": session_id,
                    "message_count": len(memory.messages)
                }
            }
        except Exception as e:
            error_msg = f"Lỗi khi AGENT xử lý: {str(e)}"
            print (f"[ERROR]: {error_msg}")
            self.logger.log("AGENT_ERROR", str(e))
            return {
                "answer": f"Xin lỗi anh {username}, hệ thống đang gặp chút sự cố hệ thống. Anh vui lòng thử lại sau nhé!",
                "logs": self.logger.get_logs()
            }
# Khởi tạo instance duy nhất để dùng chung
conversational_agent = ConversationAgent()