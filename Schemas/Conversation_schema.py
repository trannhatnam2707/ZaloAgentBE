from pydantic import BaseModel, Field
from typing import List, Optional

# 1. Schema khi Frontend gửi yêu cầu TẠO phòng chat
class ConversationCreate(BaseModel):
    # FE phải báo cho BE biết là muốn tạo chat loại gì
    type: str = Field(..., description="Bắt buộc truyền 'direct' hoặc 'group'")
    
    # Danh sách ID những người muốn thêm vào (Chưa tính bản thân người tạo)
    members: List[str] = Field(default=[], description="Danh sách ID thành viên muốn thêm vào ngay lúc tạo")

    # Các trường dành riêng cho Group
    group_id: Optional[str] = Field(None, description="Mã nhóm chat  (Chỉ bắt buộc nếu type='group')")
    group_name: Optional[str] = Field(None, description="Tên nhóm chat (Chỉ bắt buộc nếu type='group')")

# 2. Schema khi Backend trả dữ liệu về cho Frontend hiển thị
class ConversationResponse(BaseModel):
    id: str = Field(..., description="Mã _id của MongoDB")
    type: str = Field(..., description="'direct' hoặc 'group'")
    members: List[str] = Field(..., description="Danh sách ID tất cả thành viên (Bao gồm cả người tạo)")
    
    # Các trường này sẽ trả về null nếu type là 'direct'
    group_id: Optional[str] = None
    group_name: Optional[str] = None
    owner_id: Optional[str] = None