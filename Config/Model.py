# Config/Model.py
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def get_embedding(text: str):
    """Tạo embedding từ text sử dụng Gemini"""
    model = "gemini-embedding-001"  # Gemini embedding modelcls
    embedding = genai.embed_content(model="gemini-embedding-001", content=text)
    return embedding["embedding"]

# === LLM ===
def generate_gemini_response(question: str, context: str = "", system_prompt: str = "") -> str:
    """
    Gọi gemini-2.5-flash để tạo câu trả lời
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')   

        if context:
            full_prompt = f"""
{system_prompt}

Context từ database:
{context}

Câu hỏi: {question}

Hãy trả lời dựa trên context được cung cấp. 
Nếu không có thông tin liên quan trong context, hãy trả lời dựa trên kiến thức của bạn.
"""
        else:
            full_prompt = f"""
{system_prompt}

Câu hỏi: {question}

Hãy trả lời một cách chi tiết và hữu ích.
"""

        response = model.generate_content(full_prompt)

        if response and response.candidates:
            return response.text.strip()

        return "⚠️ Gemini không trả về kết quả."
    except Exception as e:
        print(f"❌ Lỗi khi gọi Gemini: {e}")
        return "Xin lỗi, tôi không thể tạo câu trả lời lúc này. Vui lòng thử lại sau."

def list_available_models():
    try:
        models = genai.list_models()
        for m in models:
            print(m.name, " - ", m.supported_generation_methods)
    except Exception as e:
        print("❌ Lỗi khi lấy danh sách model:", e)
