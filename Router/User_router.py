from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordRequestForm
from Schemas.User_schema import UserCreate, UserLogin, UserResponse
from Controller import User_Controller
from Middleware.Auth_middleware import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])

# Tạo một Schema nhỏ ngay đây để hứng Refresh Token 
class RefreshTokenRequest(BaseModel):
    refresh_token: str

@router.post("/register", response_model=UserResponse)
def api_register_user(user: UserCreate):
    # Ném thẳng cho Controller lo liệu
    return User_Controller.handle_register(user)


@router.get("/getMe/", response_model=UserResponse)
def api_getMe(current_user:dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])
    return User_Controller.handle_getMe(user_id)

@router.post("/login", response_model=dict)
def api_login_user(
    # Bắt FastAPI hứng dữ liệu từ Form của Swagger UI
    form_data: OAuth2PasswordRequestForm = Depends() 
):
    # Swagger sẽ nhét chữ bạn gõ ở ô "username" vào biến form_data.username
    # Chúng ta lấy biến đó gán vào trường "account" của Schema UserLogin
    user_login = UserLogin(
        account=form_data.username, 
        password=form_data.password
    )
    
    # Ném cục dữ liệu đã được gọt dũa cho Controller xử lý
    return User_Controller.handle_login(user_login)

@router.post("/refresh-token")
def api_refresh_token(req: RefreshTokenRequest):
    return User_Controller.handle_refresh_token(req.refresh_token)

@router.post("/logout") #Đã bỏ {user_id} khỏi URL để chống giả mạo
def api_logout_user(
    # Gắn bảo vệ: Khách phải có thẻ JWT hợp lệ mới được đăng xuất
    current_user: dict = Depends(get_current_user) 
):
    # Tự động lấy ID của chính người đang đăng nhập từ Token
    user_id = str(current_user["_id"]) 
    # Truyền user_id vào cho Controller xử lý
    return User_Controller.handle_logout(user_id)


@router.get("/search", response_model=List[UserResponse])
def api_search_users(
    keyword: str = Query(..., description="Từ khóa tìm kiếm (tên username)"),
    current_user: dict = Depends(get_current_user) # Bắt buộc đăng nhập
):
    """
    API tìm kiếm người dùng bằng username. 
    (Hệ thống sẽ tự động loại bỏ chính bạn ra khỏi kết quả).
    """
    user_id = str(current_user["_id"])
    return User_Controller.handle_search_users(keyword, user_id)
    
@router.get("/{username}", response_model=UserResponse)
def api_get_user_by_username(
    username: str,
    current_user: dict = Depends(get_current_user) #Gắn bảo vệ
):
    """Tìm bạn bè đã addfr"""
    # current_user ở đây đóng vai trò "Vệ sĩ gác cổng". 
    # Mặc dù không dùng đến nó ở bên trong hàm, nhưng nếu không có Token hợp lệ, 
    # FastAPI sẽ chửi lỗi 401 và chặn ngay ở cửa, không cho code chạy xuống dòng dưới.
    return User_Controller.handle_get_user_by_username(username)

@router.get("/friends/list")
def api_get_friends(current_user: dict = Depends(get_current_user)):
    """Lấy danh sách bạn bè và lời mời kết bạn của mình"""
    user_id = str(current_user["_id"])
    return User_Controller.handle_get_friends_data(user_id)


@router.post("/friends/request/{target_user_id}")
def api_send_friend_request(target_user_id: str, current_user: dict = Depends(get_current_user)):
    """Gửi lời mời kết bạn đến 1 người"""
    user_id = str(current_user["_id"])
    return User_Controller.handle_send_friend_request(user_id, target_user_id)


@router.post("/friends/accept/{sender_id}")
def api_accept_friend_request(sender_id: str, current_user: dict = Depends(get_current_user)):
    """Đồng ý lời mời kết bạn"""
    user_id = str(current_user["_id"])
    return User_Controller.handle_accept_friend_request(user_id, sender_id)


@router.delete("/friends/{target_user_id}")
def api_remove_friend_or_request(target_user_id: str, current_user: dict = Depends(get_current_user)):
    """Hủy kết bạn hoặc Từ chối lời mời"""
    user_id = str(current_user["_id"])
    return User_Controller.handle_remove_friend(user_id, target_user_id)

