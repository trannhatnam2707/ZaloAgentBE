from fileinput import filename
from Utils.JWT import create_access_token, create_refresh_token
from fastapi import HTTPException
from Schemas.User_schema import UserCreate, UserLogin
from Services import User_service 
from bson import ObjectId
from Utils.JWT import verify_refresh_token
from fastapi import UploadFile
from uuid import uuid4
import shutil
import os

def handle_register(user: UserCreate):
    try:
        #Gọi Sevice truyền dữ liệu dạng dict 
        user_data = User_service.create_user(user.dict())
        user_data["message"] = "Đăng ký tài khoản thành công"
        return user_data
    except ValueError as e:
        # Dịch lỗi nghiệp vụ (ValueError) thành lỗi HTTP 400
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ")

def handle_login(user_login: UserLogin):
    try: 
        user_data= User_service.login_user(user_login.account, user_login.password)

        access_token = create_access_token(data = {"sub": str(user_data["id"])})
        refresh_token = create_refresh_token(data = {"sub": str(user_data["id"])})

        # 3. Lưu Refresh Token vào Database
        User_service.save_refresh_token(user_data["id"], refresh_token)

        # 4. Trả về cho Frontend cả 2 thẻ
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user_data
        }

    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    
def handle_logout(user_id: str):
    result = User_service.logout_user(user_id)
    if result:
        return {"message": "Logout Successful"}
    raise HTTPException(status_code=400, detail="User not logged in")

def handle_getMe(user_id: str):
    try:
        user_data = User_service.get_me(user_id)
        user_data["message"] = "Lấy thông tin cá nhân thành công!"
        return user_data
    except Exception as e :
        raise HTTPException(status_code=404, detail=str(e))

def handle_get_user_by_username(username: str):
    try:
        user_data = User_service.get_user_by_username(username)
        user_data["message"] = "Lấy thông tin người dùng thành công!"
        return user_data
    except Exception as e :
        raise HTTPException(status_code=404, detail= str(e))

def handle_refresh_token(refresh_token: str):
    try:
        # 1. Giải mã thẻ Refresh xem còn hạn 7 ngày không
        payload = verify_refresh_token(refresh_token)
        user_id = payload.get("sub")
        
        # Cần viết thêm 1 hàm nhỏ trong Service để lấy raw user từ DB ra so sánh refresh_token
        user_in_db = User_service.user_collection.find_one({"_id": ObjectId(user_id)})
        
        if not user_in_db or user_in_db.get("refresh_token") != refresh_token:
            raise HTTPException(status_code=401, detail="Refresh Token không hợp lệ hoặc đã bị thu hồi!")
            
        # 3. Mọi thứ OK -> Cấp Access Token MỚI (sống 60 phút nữa)
        new_access_token = create_access_token(data={"sub": user_id})
        
        return {"access_token": new_access_token, "token_type": "bearer"}
        
    except Exception as e:
        print(f"DEBUG REFRESH ERROR: {str(e)}") # Thêm dòng này để xem lỗi thực sự
        raise HTTPException(status_code=401, detail="Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.")

def handle_search_users(keyword: str, current_user_id: str):
    try:
        users = User_service.search_users(keyword, current_user_id)
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail="Lỗi khi tìm kiếm người dùng: " + str(e))

def handle_send_friend_request(sender_id: str, receiver_id: str):
    return User_service.send_friend_request(sender_id, receiver_id)

def handle_accept_friend_request(current_user_id: str, sender_id: str):
    return User_service.accept_friend_request(current_user_id, sender_id)

def handle_remove_friend(current_user_id: str, target_user_id: str):
    return User_service.remove_friend_or_request(current_user_id, target_user_id)

def handle_get_friends_data(current_user_id: str):
    return User_service.get_my_friends_and_requests(current_user_id)

def handle_update_profile(current_user_id: str, username: str = None ,file: UploadFile = None):
    try:
        update_data = {}
        if username:
            update_data["username"] = username

        if file:
            # Đảm bảo thư mục tồn tại trước khi lưu
            os.makedirs("Uploads/Avatars", exist_ok=True)

            # Tạo tên file ngẫu nhiên không trùng (vd:abc123.png)
            ext = file.filename.split(".")[-1]
            filename = f"{uuid4()}.{ext}"
            file_path = f"Uploads/Avatars/{filename}"

            #Lưu file từ Ram vào xuống SSD:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Tạo đường dẫn tương đối (Frontend sẽ tự ghép với BASE_URL)
            avatar_url = f"/uploads/avatars/{filename}"
            update_data["avatar"] = avatar_url

        if not update_data:
            return {"message": "Không có thông tin nào bị thay đổi!"}

        #Lưu URL vào DB
        User_service.update_data(current_user_id, update_data)

        return {"message": "Cập nhật thành công!",
                "update_data": update_data
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Lỗi khi cập nhật: " + str(e))