from pymongo import MongoClient

# Kết nối tới DB của bạn
client = MongoClient("mongodb://localhost:27017/")
db = client["AgentZalo"] # Sửa lại tên DB nếu bạn đặt khác

# Tìm và Cập nhật TẤT CẢ user: 
# Nếu chưa có mảng friends thì set cho nó 2 mảng rỗng
result = db.Users.update_many(
    {"friends": {"$exists": False}}, # Điều kiện: những user chưa có trường này
    {"$set": {
        "friends": [],
        "friend_requests": []
    }}
)

print(f"Đã cập nhật thành công {result.modified_count} tài khoản cũ!")