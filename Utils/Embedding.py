from bson import ObjectId
from Config.ModelAI import get_embedding
from Database.MongoDB import reports_collection, users_collection # Sửa lại Import cho chuẩn
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
        start = end - overlap
    return chunks

# Đồng bộ report từ MongoDB qua Pinecone
def sync_one_report(report: dict, report_id: str = None):
    """Embed + upsert một report duy nhất vào Pinecone chuẩn cấu trúc mới"""
    if not report:
        return
    
    # Lấy ID an toàn
    if not report_id:
        report_id = str(report.get("_id", ""))
    
    # Lấy ID người dùng và tên
    user_id_str = str(report.get("user_id", ""))
    user_name = "Unknown"
    if user_id_str:
        user = users_collection.find_one({"_id": ObjectId(user_id_str)})
        if user:
            user_name = user.get("username", "Unknown")

    # Lấy Conversation ID (Hỗ trợ cả trường cũ 'group_id' cho an toàn)
    conv_id = str(report.get("conversation_id", report.get("group_id", "")))

    # Chỉ embed nội dung công việc + ngày — KHÔNG nhét tên người vào text embed
    # (tên vẫn có trong metadata user_name để hiển thị / lọc tùy chọn). Tránh bias:
    # query kiểu "có ai đã report" không bị kéo về đúng một người vì vector trùng tên.
    content = (
        f"Ngày báo cáo: {report.get('date', '')}\n"
        f"Nội dung hôm qua: {report.get('yesterday', '')}\n"
        f"Nội dung hôm nay: {report.get('today', '')}"
    )
    
    chunks = chunk_text(content)
    vectors = []

    for i, chunk in enumerate(chunks):
        try:
            embedding = get_embedding(chunk)
            vectors.append({
                "id": f"{report_id}_chunk{i}",
                "values": embedding,
                "metadata": {
                    "report_id": report_id, 
                    "user_id": user_id_str,
                    "user_name": user_name,
                    "conversation_id": conv_id, # bổ sung theo Schema mới
                    "date": report.get("date", ""),
                    "chunk_index": i,
                    "text": chunk,
                }
            })
        except Exception as e:
            print(f"Lỗi khi tạo embedding cho chunk {i} của report {report_id}: {e}")

    if vectors:
        index.upsert(vectors=vectors)
        print(f"Đã đồng bộ {len(vectors)} chunks từ report {report_id} vào Pinecone")
    else:
        print(" Không có vector nào được tạo để sync.")