import hashlib
from bson import ObjectId
from Database.MongoDB import get_mongo_collection
from Utils.String_utils import remove_vietnamese_accents


user_collection = get_mongo_collection("Users")

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def user_helper(user) -> dict:
    return {
        "id": str(user["_id"]),
        "account": user.get("account", ""),
        "username": user["username"],
    }

# Create User
def create_user(user_data: dict) -> dict:
    if user_data["password"] != user_data["ReEnterPassword"]:
        raise ValueError("Mật khẩu nhập lại không khớp!")
    #kiểm trả account đã tồn tại chưa
    existing_user = user_collection.find_one({"account": user_data["account"]})
    if existing_user: 
        raise ValueError("account already exists")

    #Xóa trường ReEnterPass vì không cần lưu vào DB
    del user_data["ReEnterPassword"]

    #hash password trước khi lưu
    user_data["password"] = hash_password(user_data["password"])

    user_data["username_unsigned"] = remove_vietnamese_accents(user_data["username"])

    #lưu vào DB
    result = user_collection.insert_one(user_data)

    #trả về thông tin vừa tạo 
    new_user = user_collection.find_one({"_id": result.inserted_id})
    return user_helper(new_user)

#Login user
def login_user(account: str, password: str) -> dict:
    #hash password để so sánh
    hashed_password = hash_password(password)
    
    #Tìm user với account và password
    user = user_collection.find_one({
        "account" : account,
        "password" : hashed_password
    }) 

    if not user:
        raise ValueError("Invalid username or password")
    
    return user_helper(user)

# Đăng xuất
def logout_user(user_id: str) -> bool:
    try:
        # Dùng toán tử $unset của MongoDB để xóa hẳn cái trường refresh_token đi
        result = user_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$unset": {"refresh_token": ""}}
        )
        return result.modified_count > 0 # Trả về True nếu xóa thành công
    except Exception:
        return False
    
# Get User by Username
def get_user_by_username(username: str) -> dict:
    user = user_collection.find_one({"username": username})
    if not user:
        raise ValueError("User not found")
    return user_helper(user)

# Get All Users
def get_all_users() -> list:
    users = user_collection.find()
    return [user_helper(user) for user in users]

def save_refresh_token(user_id: str, refresh_token: str):
    # Lưu thẻ căn cước vào DB để sau này đối chiếu
    user_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"refresh_token": refresh_token}}
    )

# Tìm kiếm người dùng (để kết bạn/nhắn tin)
def search_users(keyword: str, current_user_id: str) -> list:
    # 1. Ép từ khóa khách gõ thành không dấu (VD: "Phúc" hay "phuc" đều thành "phuc")
    clean_keyword = remove_vietnamese_accents(keyword)
    
    # 2. Tìm kiếm bằng Regex trên trường "username_unsigned"
    query = {
        "_id": {"$ne": ObjectId(current_user_id)}, 
        "username_unsigned": {"$regex": clean_keyword, "$options": "i"} 
    }
    
    users = user_collection.find(query).limit(20)
    return [user_helper(user) for user in users]