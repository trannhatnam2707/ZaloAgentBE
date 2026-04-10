import hashlib
from bson import ObjectId
from Database.MongoDB import get_mongo_collection
from Utils.String_utils import remove_vietnamese_accents
from fastapi import HTTPException

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

    user_data["friends"] = []

    user_data["friends_requests"] = []

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

def get_me(user_id:str):
    user =  user_collection.find_one({"_id": ObjectId(user_id)})

    if not user:
        raise ValueError("Không tìm thấy thông tin tài khoản của bạn!")
    return user_helper(user)

    
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

def send_friend_request(sender_id: str, receiver_id: str):
    if sender_id == receiver_id:
        raise HTTPException(status_code=400, detail="Không thể tự kết bạn với chính mình!")
    receiver_obj_id = ObjectId(receiver_id)
    sender_obj_id = ObjectId(sender_id)

    receiver = user_collection.find_one({"_id": receiver_obj_id})
    if not receiver: 
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại!")
    
    if sender_obj_id in receiver.get("friends", []):
        raise HTTPException(status_code=400, detail="đã là bạn bè!")
    user_collection.update_one(
        {"_id": receiver_obj_id},
        {"$addToSet": {"friend_requests": sender_obj_id}}
    )

    return {"message": "Đã gửi lời mời kết bạn thành công"}

def accept_friend_request(current_user_id: str, sender_id: str):
    user_obj_id = ObjectId(current_user_id)
    sender_obj_id =  ObjectId(sender_id)

    
    user = user_collection.find_one({"_id": user_obj_id})
    
    #1. kiểm tra xem có lời mòi không
    if sender_obj_id not in user.get("friend_requests", []):
        raise HTTPException(status_code=400, detail="Không tim thấy lời mời kết bạn này!")
    
    #2. Rút người kia ra khỏi danh sách chờ của mình 
    user_collection.update_one(
        {"_id":user_obj_id},
        {"$pull": {"friend_requests": sender_obj_id}}
    )

    #3. Thêm ID của nhau vào danh sách friend của cả 2 
    user_collection.update_one(
        {"_id": user_obj_id},
        {"$addToSet":{"friends": sender_obj_id}}
    )
    user_collection.update_one(
        {"_id":sender_obj_id},
        {"$addToSet": {"friends":user_obj_id}}
    )

    return {"message": "Kết bạn thành công!"}

def remove_friend_or_request(current_user_id: str, target_user_id: str):
    """Dùng chung cho cả hủy và từ chôi lời mời"""
    user_obj_id = ObjectId(current_user_id)
    target_obj_id = ObjectId(target_obj_id)

    # Xóa chéo ID của nhau khỏi CẢ 2 mảng (friends và friend_requests) của CẢ 2 người
    user_collection.update_one(
        {"_id": user_obj_id},
        {"$pull": {"friends": target_obj_id, "friend_requests": target_obj_id}}
    )
    user_collection.update_one(
        {"_id": target_obj_id},
        {"$pull": {"friends": user_obj_id, "friend_requests": user_obj_id}}
    )
    return {"message": "Đã xóa trạng thái bạn bè/lời mời"}

def get_my_friends_and_requests(current_user_id: str):
    """Lấy danh sách bạn bè và những người đang xin kết bạn (để FE hiển thị)"""
    user = user_collection.find_one({"_id": ObjectId(current_user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Lấy thông tin chi tiết của những người trong mảng friends
    friends_cursor = user_collection.find({"_id": {"$in": user.get("friends", [])}})
    # Lấy thông tin chi tiết của những người trong mảng friend_requests
    requests_cursor = user_collection.find({"_id": {"$in": user.get("friend_requests", [])}})

    return {
        "friends": [user_helper(f) for f in friends_cursor],
        "friend_requests": [user_helper(r) for r in requests_cursor]
    }