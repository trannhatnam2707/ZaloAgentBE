from pydantic import BaseModel
from pydantic import Field


class UserBase(BaseModel):
    username: str = Field(..., description="Tên người dùng")
   
class UserCreate(UserBase):
    password: str = Field(...,min_length=6, description="Mật khẩu")

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    username: str
    message: str    