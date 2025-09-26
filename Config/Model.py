# Utils/Embedding.py
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def get_embedding(text: str):
    model = "models/gemini-embedding-001"  # Gemini embedding model
    embedding = genai.embed_content(model=model, content=text)
    return embedding["embedding"]
