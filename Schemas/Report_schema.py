from datetime import datetime 
from typing import Optional, Annotated
from pydantic import BaseModel, Field, BeforeValidator

# Định nghĩa kiểu dữ liệu để tự động convert ObjectId sang String
PyObjectId = Annotated[str, BeforeValidator(str)]

class ReportBase(BaseModel):
    date: str = Field(..., description="Ngày report")
    yesterday: str = Field(..., description="Công việc hôm qua")
    today: str = Field(..., description="Công việc hôm nay")
    # Sử dụng PyObjectId ở đây để tránh lỗi validation khi lấy dữ liệu từ DB
    conversation_id: Optional[PyObjectId] = Field(default=None, description="ID của phòng chat chứa report này")
    
class ReportCreate(ReportBase):
    pass 

class ReportUpdate(BaseModel):
    date: Optional[str] = None  
    yesterday: Optional[str] = None 
    today: Optional[str] = None 

class ReportResponse(ReportBase):
    # Sử dụng PyObjectId cho tất cả các trường ID
    id: PyObjectId = Field(alias="_id") 
    user_id: PyObjectId
    user_name: str
    created_at: datetime
    updated_at: datetime    
    
    class Config:
        # Cho phép Pydantic đọc dữ liệu từ các object (như document của MongoDB)
        from_attributes = True
        # Cho phép sử dụng alias "_id" từ DB map vào trường "id" của Schema
        populate_by_name = True