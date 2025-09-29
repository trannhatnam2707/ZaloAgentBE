import hashlib
from bson import ObjectId
from Database.MongoDB import get_mongo_collection


user_collection = get_mongo_collection("Users")

#Bộ nhớ session tạm (đơn giản, chưa cần JWT)
active_sessions = {}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def user_helper(user) -> dict:
    return {
        "id": str(user["_id"]),
        "username": user["username"],
    }

# Create User
def create_user(user_data: dict) -> dict:
    #kiểm trả username đã tồn tại chưa
    existing_user = user_collection.find_one({"username": user_data["username"]})
    if existing_user: 
        raise ValueError("Username already exists")

    #hash password trước khi lưu
    user_data["password"] = hash_password(user_data["password"])

    #lưu vào DB
    result = user_collection.insert_one(user_data)

    #trả về thông tin vừa tạo 
    new_user = user_collection.find_one({"_id": result.inserted_id})
    return user_helper(new_user)

#Login user
def login_user(username: str, password: str) -> dict:
    #hash password để so sánh
    hashed_password = hash_password(password)
    
    #Tìm user với username và password
    user = user_collection.find_one({
        "username" : username,
        "password" : hashed_password
    }) 

    if not user:
        raise ValueError("Invalid username or password")
    
    user_id = str(user["_id"])
    active_sessions[user_id] = True # Đánh dấu là user đang đăng nhập
    return user_helper(user)

# Đăng xuất
def logout_user(user_id: str) -> bool:
    if user_id in active_sessions:
        del active_sessions[user_id]
        return True
    return False

# Get User by ID
def get_user_by_id(user_id: str) -> dict:
    user = user_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise ValueError("User not found")
    return user_helper(user)

# # Get User by Username
# def get_user_by_username(username: str) -> dict:
#     user = user_collection.find_one({"username": username})
#     if not user:
#         raise ValueError("User not found")
#     return user_helper(user)

# Get All Users
def get_all_users() -> list:
    users = user_collection.find()
    return [user_helper(user) for user in users]

#delete user
def delete_user(user_id: str) -> bool:
    result = user_collection.delete_one({"_id": ObjectId(user_id)})
    return result.deleted_count > 0