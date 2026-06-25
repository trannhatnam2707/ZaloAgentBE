from typing import List, Optional
from pydantic import BaseModel
from pydantic import Field


class UserBase(BaseModel):
    account: str = Field(..., description="Tên đăng nhập")
   
class UserCreate(UserBase):
    username: str = Field(..., description="Tên người dùng")
    password: str = Field(...,min_length=6, description="Mật khẩu")
    ReEnterPassword: str = Field(..., min_length=6, description="Nhập lại mật khẩu khi đăng ký")

class UserLogin(BaseModel):
    account: str
    password: str

class UserResponse(UserBase):
    id: str = Field(..., description="Mã ID của user")
    username: str
    message: Optional[str] = None   
    friends: Optional[List[str]] = []
    friend_requests : Optional[List[str]] = []
    avatar: Optional[str] = None