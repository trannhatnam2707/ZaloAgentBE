from pydantic import BaseModel
from pydantic import Field
from datetime import datetime

class Reports_Model(BaseModel): 
        group_id: str = Field(...,description="Tham chiếu tới _id của GroupChat")
        date: str = Field(..., description="Ngày")
        yesterday: str = Field(..., description="Công việc hôm qua")
        today: str = Field(..., description="Công việc hôm nay")
        user_id: str = Field(..., description="ID người dùng")
        created_at: datetime = Field(default_factory=datetime.utcnow, description="Ngày tạo")
        updated_at: datetime = Field(default_factory=datetime.utcnow, description="Ngày cập nhật")