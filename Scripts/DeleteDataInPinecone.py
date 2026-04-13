# File: Scripts/clear_pinecone.py

import sys
import os

# Thêm đường dẫn thư mục gốc của project vào sys.path để có thể import từ Database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Database.Pinecone import index

def clear_all_pinecone_data():
    print("🚀 Bắt đầu xóa toàn bộ dữ liệu trên Pinecone...")
    try:
        # Lệnh này sẽ xóa toàn bộ vector trong namespace mặc định
        index.delete(delete_all=True)
        print("✅ Đã xóa THÀNH CÔNG toàn bộ dữ liệu trên Pinecone!")
        print("💡 Bây giờ Pinecone của bạn đã hoàn toàn trống.")
        print("👉 Bước tiếp theo: Bạn hãy viết/chạy script lấy toàn bộ Report từ MongoDB và gọi hàm sync_one_report để đẩy dữ liệu sạch lên lại nhé.")
    except Exception as e:
        print(f"❌ Lỗi khi xóa dữ liệu Pinecone: {e}")

if __name__ == "__main__":
    clear_all_pinecone_data()