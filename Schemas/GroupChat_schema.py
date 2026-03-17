from pydantic import BaseModel, Field
from typing import List, Optional

# 1. Schema khi Frontend gửi yêu cầu tạo nhóm
class GroupChatCreate(BaseModel):
    # Đây là ID do Zalo sinh ra (VD: "zalo_group_001")
    group_id: str = Field(..., description="Mã nhóm chat từ Zalo")
    group_name: str = Field(..., description="Tên nhóm chat")
    
    # Tuyệt đối KHÔNG khai báo owner_id ở đây để tránh bị Frontend giả mạo!

# 2. Schema khi Backend trả dữ liệu về cho Frontend hiển thị
class GroupChatResponse(BaseModel):
    id: str = Field(..., description="Mã _id của MongoDB")
    group_id: str = Field(..., description="Mã nhóm chat từ Zalo")
    group_name: str = Field(..., description="Tên nhóm chat")
    owner_id: str = Field(..., description="ID của chủ nhóm (Lấy từ Token)")
    members: List[str] = Field(default=[], description="Danh sách ID các thành viên")