import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(override=True)

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# ==========================================
# EMBEDDING CHO PINECONE 
# ==========================================
def get_embedding(text: str) -> list:
    """Tạo embedding từ text sử dụng SDK mới của Gemini"""
    try:
        # Nâng cấp lên model nhúng thế hệ mới nhất của Google
        response = client.models.embed_content(
            model="gemini-embedding-001", 
            contents=text
        )
        # SDK mới trả về object thay vì dictionary, ta lấy mảng vector bằng .values
        return response.embeddings[0].values
    except Exception as e:
        print(f"Lỗi khi tạo embedding: {e}")
        return []

# ==========================================
# LLM TRUYỀN THỐNG (CHẠY ĐỘC LẬP KHÔNG CẦN TOOLS)
# ==========================================
def generate_gemini_response(question: str, context: str = "", system_prompt: str = "") -> str:
    """
    Gọi gemini-2.5-flash để tạo câu trả lời. 
    (Hàm này dành cho các tác vụ hỏi đáp nhanh bên ngoài, không liên quan đến hệ thống Agent Tools)
    """
    try:
        # Chuẩn bị Prompt
        if context:
            full_prompt = f"""
Context từ database:
{context}

Câu hỏi: {question}

Hãy trả lời dựa trên context được cung cấp. 
Nếu không có thông tin liên quan trong context, thì đừng bịa ra gì cả. Hãy trả lời là không tìm được thông tin.
"""
        else:
            full_prompt = f"""
Câu hỏi: {question}

Hãy trả lời một cách chi tiết và hữu ích.
"""
        
        # Thiết lập System Prompt (nếu có) bằng chuẩn mới
        config = None
        if system_prompt:
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2 #Giữ AI nói chuyện logic, tránh ảo giác
            )

        # Gọi AI sinh text
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=full_prompt,
            config=config
        )

        if response and response.text:
            return response.text.strip()

        return "Gemini không trả về kết quả."
    except Exception as e:
        print(f"Lỗi khi gọi Gemini: {e}")
        return "Xin lỗi, tôi không thể tạo câu trả lời lúc này. Vui lòng thử lại sau."

def list_available_models():
    """Hàm hỗ trợ lấy danh sách các model hiện có"""
    try:
        for m in client.models.list():
            print(m.name)
    except Exception as e:
        print("Lỗi khi lấy danh sách model:", e)