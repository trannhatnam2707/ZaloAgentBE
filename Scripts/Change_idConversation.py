from pymongo import MongoClient

# 1. Kết nối tới Database
client = MongoClient("mongodb://localhost:27017/") 
db = client["AgentZalo"] 

def rename_group_to_conversation():
    print("🚀 Bắt đầu quá trình đổi tên trường trong bảng Report...")

    # 2. Sử dụng toán tử $rename của MongoDB
    # Cú pháp: tìm tất cả các doc {}, sau đó đổi tên "group_id" thành "conversation_id"
    result = db.Report.update_many(
        {}, # Filter rỗng nghĩa là áp dụng cho TOÀN BỘ document trong bảng
        {"$rename": {"group_id": "conversation_id"}} 
    )

    # 3. Báo cáo kết quả
    print(f"✅ Quét qua: {result.matched_count} báo cáo.")
    print(f"✅ Đã đổi tên thành công cho: {result.modified_count} báo cáo!")
    print("🎉 Bảng Report giờ đã chuẩn form 100%!")

if __name__ == "__main__":
    rename_group_to_conversation()