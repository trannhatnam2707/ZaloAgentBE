import os
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

# Lấy API key và index name
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "agentzalo")

if not PINECONE_API_KEY:
    raise ValueError("❌ PINECONE_API_KEY is not set in .env")

# Khởi tạo client
pc = Pinecone(api_key=PINECONE_API_KEY)

# Nếu index chưa tồn tại thì tạo mới
if PINECONE_INDEX not in [idx["name"] for idx in pc.list_indexes()]:
    pc.create_index(
        name=PINECONE_INDEX,
        dimension=3072,         # chỉnh đúng dimension theo model embedding
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"  # chỉnh region theo tài khoản của mình
        )
    )

# Lấy đối tượng index
index = pc.Index(PINECONE_INDEX)
