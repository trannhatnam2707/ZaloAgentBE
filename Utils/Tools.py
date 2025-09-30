from Config.Model import generate_gemini_response, get_embedding
from Database.Pinecone import index


class Tools:
    @staticmethod
    def search_reports(query: str ,top_k: int = 5):
        embedding = get_embedding(query)
        res = index.query(vector=embedding, top_k = top_k, include_metadata = True)
        return [m for m in res["matches"] if m["score"] >= 0.6]

    @staticmethod
    def ask_llm(question: str, context: str=" ", system_prompt: str=" "):
        return generate_gemini_response(question, context, system_prompt)