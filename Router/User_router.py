from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordRequestForm

# Import Schema
from Schemas.User_schema import UserCreate, UserLogin, UserResponse

# Import Controller (Tuyệt đối không gọi Service ở đây nữa)
from Controller import User_Controller

# Import các anh Bảo vệ
from Middleware.Auth_middleware import get_current_user, require_owner

router = APIRouter(prefix="/users", tags=["Users"])

# Tạo một Schema nhỏ ngay đây để hứng Refresh Token (hoặc bạn có thể đem qua file User_schema.py)
class RefreshTokenRequest(BaseModel):
    refresh_token: str

# ========================================================
# 1. CÁC API PUBLIC (AI CŨNG VÀO ĐƯỢC - KHÔNG CẦN BẢO VỆ)
# ========================================================

@router.post("/register", response_model=UserResponse)
def api_register_user(user: UserCreate):
    # Ném thẳng cho Controller lo liệu
    return User_Controller.handle_register(user)

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


# ========================================================
# 2. CÁC API PRIVATE (BẮT BUỘC PHẢI TRÌNH THẺ JWT)
# ========================================================

# ========================================================
# 1. API LOGOUT (Đăng xuất)
# ========================================================
@router.post("/logout") # 👈 Đã bỏ {user_id} khỏi URL để chống giả mạo
def api_logout_user(
    # 🛡️ Gắn bảo vệ: Khách phải có thẻ JWT hợp lệ mới được đăng xuất
    current_user: dict = Depends(get_current_user) 
):
    # Tự động lấy ID của chính người đang đăng nhập từ Token
    user_id = str(current_user["_id"]) 
    
    # Truyền user_id vào cho Controller xử lý
    return User_Controller.handle_logout(user_id)


# ========================================================
# 2. API LẤY THÔNG TIN THEO USERNAME
# ========================================================
@router.get("/{username}", response_model=UserResponse)
def api_get_user_by_username(
    username: str, # Lấy theo username (tên người dùng) cần tìm kiếm
    current_user: dict = Depends(get_current_user) # 🛡️ Gắn bảo vệ
):
    # current_user ở đây đóng vai trò "Vệ sĩ gác cổng". 
    # Mặc dù không dùng đến nó ở bên trong hàm, nhưng nếu không có Token hợp lệ, 
    # FastAPI sẽ chửi lỗi 401 và chặn ngay ở cửa, không cho code chạy xuống dòng dưới.
    return User_Controller.handle_get_user_by_username(username)
