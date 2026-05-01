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

    user_data["friend_requests"] = []

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
    sender = user_collection.find_one({"_id": sender_obj_id})
    
    if not receiver or not sender: 
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại!")

    # Chuyển ID về string để so sánh tuyệt đối chính xác
    s_id_str = str(sender_obj_id)
    r_id_str = str(receiver_obj_id)

    receiver_requests = receiver.get("friend_requests", [])
    sender_requests = sender.get("friend_requests", [])
    receiver_friend = receiver.get("friends", [])

    # 1. Kiểm tra: Đã là bạn bè chưa?
    if any(str(f_id) == s_id_str for f_id in receiver_friend):
        raise HTTPException(status_code=400, detail="Hai người đã là bạn bè!")

    if any(str(req.get("user_id")) == r_id_str and req.get("is_sender") == True 
           for req in sender_requests):
        raise HTTPException(status_code=400, detail="Bạn đã gửi lời mời rồi, đang chờ người kia xác nhận!")

    # 3. KIỂM TRA: Họ đã gửi cho mình chưa?
    # Check trong mảng của CHÍNH MÌNH (sender), xem có ai là receiver_id mà is_sender=False không
    if any(str(req.get("user_id")) == r_id_str and req.get("is_sender") == False 
           for req in sender_requests):
        raise HTTPException(status_code=400, detail="Người này đã gửi lời mời cho bạn rồi. Hãy kiểm tra danh sách lời mời và bấm Chấp nhận!")

    # Nếu pass các điều kiện trên mới tiến hành $push
    user_collection.update_one(
        {"_id": receiver_obj_id},
        {"$push": {"friend_requests": {"user_id": sender_obj_id, "status": "pending", "is_sender": False}}}
    )
    user_collection.update_one(
        {"_id": sender_obj_id},
        {"$push": {"friend_requests": {"user_id": receiver_obj_id, "status": "pending", "is_sender": True}}}
    )
    return {"message": "Đã gửi lời mời kết bạn thành công"}

def accept_friend_request(current_user_id: str, sender_id: str):
    user_obj_id = ObjectId(current_user_id)
    sender_obj_id = ObjectId(sender_id)
    
    # Lấy thông tin user hiện tại (người bấm chấp nhận)
    user = user_collection.find_one({"_id": user_obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng!")

    # 1. KIỂM TRA: Có lời mời từ sender_id trong mảng Object không?
    # Phải dùng any() vì friend_requests là danh sách các dict {user_id: ..., status: ...}
    requests = user.get("friend_requests", [])
    has_request = any(str(req.get("user_id")) == str(sender_obj_id) for req in requests if isinstance(req, dict))
    
    if not has_request:
        raise HTTPException(status_code=400, detail="Không tìm thấy lời mời kết bạn từ người này!")

    # 2. DỌN DẸP MẢNG CHỜ: Xóa yêu cầu kết bạn của nhau (Xóa Object có user_id tương ứng)
    # Lưu ý: Phải dùng cấu trúc {"user_id": ...} trong $pull vì mảng chứa Object
    user_collection.update_one(
        {"_id": user_obj_id},
        {"$pull": {"friend_requests": {"user_id": sender_obj_id}}}
    )
    user_collection.update_one(
        {"_id": sender_obj_id},
        {"$pull": {"friend_requests": {"user_id": user_obj_id}}}
    )

    # 3. KẾT BẠN: Thêm ID của nhau vào mảng friends (Lưu ID thuần để search $in nhanh)
    # Dùng $addToSet để đảm bảo không bị trùng lặp ID
    user_collection.update_one(
        {"_id": user_obj_id},
        {"$addToSet": {"friends": sender_obj_id}}
    )
    user_collection.update_one(
        {"_id": sender_obj_id},
        {"$addToSet": {"friends": user_obj_id}}
    )

    return {"message": "Chúc mừng! Hai bạn đã trở thành bạn bè."}

def remove_friend_or_request(current_user_id: str, target_user_id: str):
    user_obj_id = ObjectId(current_user_id)
    target_obj_id = ObjectId(target_user_id)

    # Xóa trong mảng friends (mảng ID) và friend_requests (mảng Object)
    user_collection.update_one(
        {"_id": user_obj_id},
        {
            "$pull": {
                "friends": target_obj_id, 
                "friend_requests": {"user_id": target_obj_id} # Sửa ở đây
            }
        }
    )
    user_collection.update_one(
        {"_id": target_obj_id},
        {
            "$pull": {
                "friends": user_obj_id, 
                "friend_requests": {"user_id": user_obj_id} # Sửa ở đây
            }
        }
    )
    return {"message": "Đã xóa trạng thái bạn bè/lời mời"}

def get_my_friends_and_requests(current_user_id: str):
    user = user_collection.find_one({"_id": ObjectId(current_user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Lấy thông tin bạn bè (mảng ID thuần)
    friend_ids = [ObjectId(f) for f in user.get("friends", [])]
    friends_cursor = user_collection.find({"_id": {"$in": friend_ids}})

    # Lấy thông tin lời mời (trích xuất user_id từ mảng Object)
    raw_requests = user.get("friend_requests", [])
    
    # Tạo danh sách ID để query thông tin user một lần cho nhanh
    req_user_ids = [ObjectId(req["user_id"]) for req in raw_requests if isinstance(req, dict)]
    users_info_cursor = user_collection.find({"_id": {"$in": req_user_ids}})
    
    # Chuyển cursor thành dict để map dữ liệu nhanh hơn
    users_dict = {str(u["_id"]): user_helper(u) for u in users_info_cursor}

    # Kết hợp thông tin User với is_sender/status từ mảng raw_requests
    enriched_requests = []
    for req in raw_requests:
        u_id_str = str(req["user_id"])
        if u_id_str in users_dict:
            info = users_dict[u_id_str].copy()
            info["is_sender"] = req.get("is_sender")
            info["status"] = req.get("status")
            enriched_requests.append(info)

    return {
        "friends": [user_helper(f) for f in friends_cursor],
        "friend_requests": enriched_requests
    }