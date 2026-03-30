# File: Database/Pinecone.py

import os
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

load_dotenv(override=True)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY_V2")
# print(f"🔑 Đã nạp thành công Key Pinecone: {str(PINECONE_API_KEY)[:5]}...")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "agentzalo")

if not PINECONE_API_KEY:
    raise ValueError("❌ PINECONE_API_KEY is not set in .env")

pc = Pinecone(api_key=PINECONE_API_KEY)

if PINECONE_INDEX not in [idx["name"] for idx in pc.list_indexes()]:
    pc.create_index(
        name=PINECONE_INDEX,
        dimension=3072,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

index = pc.Index(PINECONE_INDEX)

def search_pinecone(query_embedding, top_k, filter=None):
    """
    Thực hiện tìm kiếm trên Pinecone, có thể kèm bộ lọc metadata.
    """
    print(f"Searching Pinecone with filter: {filter}")
    return index.query(
        vector=query_embedding,
        top_k=top_k,
        filter=filter,
        include_metadata=True
    )