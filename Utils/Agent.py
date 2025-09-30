from Config.Model import generate_gemini_response
from Utils.Logger import AgentLogger
from Utils.Tools import Tools


SYSTEM_PROMPT = """
Bạn là một Agent hỗ trợ phân tích báo cáo công việc hàng ngày.
Bạn có thể sử dụng các công cụ sau:
    -search_reports[query]: tìm các thông tin vector từ Pinecone database.
    -Answer [context, question]: dùng LLM để tạo câu trả lời dựa vào context

Luôn làm theo kế hoạch:
plan: mô tả kế hoạch,
Act: chọn công cụ và tham số để thực hiện kế hoạch
Obversation: Quan sát kết quả trả về
Final answer: câu trả lời cuối cùng cho người dùng
"""

class Agent:
    def __init__(self, llm: str = "gemini-2.5-flash"):
        self.llm = llm
        self.logger = AgentLogger()
    
    def run(self, user_query: str, top_k: int=5):
        # Tạo prompt yêu cầu LLM lên kế hoạch 
        planning_prompt = f"""
        {SYSTEM_PROMPT}

        user hỏi: {user_query}
        
        Bắt đầu lập kế hoạch: 
        """

        plan = generate_gemini_response(question=user_query, system_prompt = planning_prompt )
        self.logger.log("Plan", plan)

        # Agent hành động theo plan
        # (ở bản cơ bản này thì giả định tool đầu tiên chọn luôn là searchreport )
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