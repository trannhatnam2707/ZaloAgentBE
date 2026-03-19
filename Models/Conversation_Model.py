from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Conversation_Model(BaseModel):
    # TRƯỜNG PHÂN LOẠI (Bắt buộc)
    type: str = Field(..., description="Loại hội thoại: 'direct' (1-1) hoặc 'group' (Nhóm)") 
    
    # DANH SÁCH THÀNH VIÊN (Bắt buộc)
    members: List[str] = Field(..., description="Danh sách ID của các thành viên")
    
    # ==========================================
    # CÁC TRƯỜNG CỦA NHÓM (Chuyển thành Optional - Có thể bỏ trống)
    # Nếu là chat 1-1 thì những trường này sẽ mang giá trị null
    # ==========================================
    group_id: Optional[str] = Field(None, description="Mã nhóm chat")
    group_name: Optional[str] = Field(None, description="Tên nhóm chat")
    owner_id: Optional[str] = Field(None, description="Tham chiếu tới _id của bảng Users (Chủ nhóm)")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)