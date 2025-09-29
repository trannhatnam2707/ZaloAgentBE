from Config.Model import generate_gemini_response
from Utils.Agent import Agent


agent = Agent(llm=generate_gemini_response)

def ask_agent(question: str, top_k: int = 1000) -> dict:
    return agent.run(user_query=question, top_k=top_k)