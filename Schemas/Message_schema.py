from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from Models.Message_Model import MessageType

# 1. Schema Hứng Dữ Liệu Từ Frontend (Khi bấm gửi tin nhắn)
class MessageCreate(BaseModel):
    conversation_id: str = Field(..., description="Gửi vào phòng chat nào?")
    
    # Mặc định Frontend gửi chữ là chính, nên type mặc định là "text"
    type: MessageType = Field(default=MessageType.TEXT, description="Loại tin: text, report_card...")
    
    content: str = Field(..., description="Nội dung chữ do User gõ")
    
    # Hỗ trợ trường hợp FE muốn gửi kèm data gì đó
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Túi dữ liệu đính kèm")
    
    #KHÔNG CÓ sender_id Ở ĐÂY (Bảo mật: BE tự lấy từ Token)

# 2. Schema Trả Dữ Liệu Về Cho Frontend (Khi load lịch sử chat)
class MessageResponse(BaseModel):
    id: str = Field(..., description="Mã _id của tin nhắn")
    conversation_id: str = Field(..., description="ID phòng chat")
    sender_id: str = Field(..., description="ID của người gửi (hoặc bot)")
    type: str = Field(..., description="Loại tin nhắn (text, report_card, system)")
    content: str = Field(..., description="Nội dung")
    metadata: Optional[Dict[str, Any]] = Field(default=None)
    created_at: datetime = Field(..., description="Thời gian gửi")