from datetime import datetime 
from typing import Optional
from pydantic import BaseModel


class ReportBase(BaseModel):
    date: str
    yesterday: str
    today: str
    
# Khi tạo report, client chỉ gửi user_name
class ReportCreate(ReportBase):
    user_name: str

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
    
    