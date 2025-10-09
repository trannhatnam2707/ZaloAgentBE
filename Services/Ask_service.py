from Config.Model import generate_gemini_response
from Utils.Agent import Agent


agent = Agent(llm=generate_gemini_response)

def ask_agent(question: str, username: str, top_k: int = 10) -> dict:
    """
    Service layer để gọi Agent
    
    Args:
        question: Câu hỏi/yêu cầu từ user
        username: Tên user (BẮT BUỘC từ FE)
        top_k: Số lượng kết quả search
    
    Returns:
        dict: Kết quả từ Agent
    """
    return agent.run(user_query=question, username=username, top_k=top_k)