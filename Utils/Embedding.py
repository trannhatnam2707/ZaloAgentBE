from bson import ObjectId
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
def sync_one_report(report: dict, report_id: str = None):
    """Embed + upsert một report duy nhất vào Pinecone """
    if not report:
        return
    if not report_id:
        report_id = str(report["_id"])

    content = (
        f"Report date: {report.get('date', '')}\n"
        f"Yesterday: {report.get('yesterday', '')}\n"
        f"Today: {report.get('today', '')}"
    )
    chunks = chunk_text(content)

    vectors = []

    for i, chunk in enumerate(chunks):
            print("Chunk:", chunk)  # debug xem có nội dung không
            embedding = get_embedding(chunk)
            print("Embedding length:", len(embedding))  # debug độ dài vector

            vectors.append({
                "id": f"{report_id}_chunk{i}",  # tránh trùng id
                "values": embedding,
                "metadata": {
                    "report_id": report_id, 
                    "user_id": str(report.get("user_id", "")),
                    "date": report.get("date", ""),
                    "chunk_index": i,
                    "text": chunk
                }
            })

    if vectors:
        index.upsert(vectors=vectors)
        print(f"Synced {len(vectors)} chunks từ report {report_id} vào Pinecone")
    else:
        print("Không có report nào để sync.")
    
# def add_report(report_data: dict):
#     """Thêm report mới và sync ngay"""
#     result = reports_collection.insert_one(report_data)
#     report_id = str(result.inserted_id)
#     sync_one_report(report_data,report_id)
#     return report_id

# def update_report(report_id: str, update_data: dict):
#     """Update report mới và sync ngay"""
#     reports_collection.update_one({"_id": ObjectId(report_id)}, {"$set": update_data})
#     report = reports_collection.find_one({"_id":ObjectId(report_id)})
#     sync_one_report(report, report_id)

# if __name__ == "__main__":
#     reports = list(reports_collection.find({}))
#     for r in reports:
#         sync_one_report(r)

