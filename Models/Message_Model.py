from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


#Khai báo Enum để khóa cứng các loại tin nhắn được phép
class MessageType(str, Enum):
    TEXT = "text",
    REPORT_CARD = "report_card",
    SYSTEM = "system"

class Messages_Model(BaseModel):
    conversation_id: str = Field(...,description="ID của phòng chat")
    
    #Cho phép string  vì có thể là bot chat hoặc từ system
    sender_id: str = Field(...,description="ID người gửi hoặc tên bot")

    type: MessageType = Field(default=MessageType.TEXT, description="Loại tin nhắn")
    content: str = Field(..., description="Nội dung tin nhắn")

    #Metadata dùng kiểu Dict[str, Any] để chứa Object JSON tự do o (ví dụ: {"report_id": "..."})
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Dữ liệu đính kèm")

    created_at: datetime = Field(default_factory=datetime.now)