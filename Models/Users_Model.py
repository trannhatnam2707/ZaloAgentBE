from pydantic import BaseModel
from pydantic import Field

class Users_Model(BaseModel):
    UserName: str = Field(..., description="Tên người dùng")
    Password: str = Field(..., description="Mật khẩu")
