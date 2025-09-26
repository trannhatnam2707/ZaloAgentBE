from Config.Model import get_embedding
from Database.MongoDB import reports_collection
from Database.Pinecone import index

# Hàm chia chunk
def chunk_text(text, chunk_size=300, overlap=50):
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end]
        chunks.append(chunk)

        if end == text_length:
            break
        start = end - overlap  # lùi overlap để giữ context

    return chunks


# Đồng bộ report từ MongoDB qua Pinecone
def sync_report_to_pinecone():
    reports = list(reports_collection.find({}))
    vectors = []

    for report in reports:
        report_id = str(report["_id"])
        # Gộp text từ yesterday + today
        content = f"Yesterday: {report.get('yesterday', '')}\nToday: {report.get('today', '')}"

        # Chia chunk
        chunks = chunk_text(content)

        for i, chunk in enumerate(chunks):
            embedding = get_embedding(chunk)

            vectors.append({
                "id": f"{report_id}_chunk{i}",  # tránh trùng id
                "values": embedding,
                "metadata": {
                    "user_id": str(report.get("user_id", "")),
                    "date": report.get("date", ""),
                    "chunk_index": i,
                    "text": chunk
                }
            })

    if vectors:
        index.upsert(vectors=vectors)
        print(f"✅ Synced {len(vectors)} chunks từ {len(reports)} reports vào Pinecone")
    else:
        print("⚠️ Không có report nào để sync.")

if __name__ == "__main__":
    sync_report_to_pinecone()
