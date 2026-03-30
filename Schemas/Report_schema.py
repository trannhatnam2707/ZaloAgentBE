from datetime import datetime 
from typing import Optional
from pydantic import BaseModel
from pydantic import Field


class ReportBase(BaseModel):
    date: str = Field(..., description="Ngày report")
    yesterday: str = Field(..., description="Công việc hôm qua")
    today: str = Field(..., description="Công việc hôm nay")
    conversation_id: Optional[str] = Field(default=None, description="ID của phòng chat chứa report này")
    
# Khi tạo report, client chỉ gửi user_name
class ReportCreate(ReportBase):
    pass #inheritance from ReportBase

class ReportUpdate(BaseModel):
    date: Optional[str] = None  
    yesterday: Optional[str] = None 
    today: Optional[str] = None 

class ReportResponse(ReportBase):
    id: str
    user_id: str
    user_name: str
    created_at: datetime
    updated_at: datetime    
    
    