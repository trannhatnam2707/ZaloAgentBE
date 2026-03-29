from typing import List, Optional
from pydantic import BaseModel
from pydantic import Field

class Users_Model(BaseModel):
    UserName: str = Field(..., description="Tên người dùng")
    Password: str = Field(..., description="Mật khẩu")
    Account: str = Field(..., description="Tên đăng nhập")
    username_unsigned: Optional[str] = Field(default="", description="Tên không dấu để phục vụ API Search")
    friends: List[str] = Field(default_factory=list, description="Mảng chứa ID của những người đã là bạn bè")
    friend_requests: List[str] = Field(default_factory=list, description="Mảng chứa ID của những người xin kết bạn")