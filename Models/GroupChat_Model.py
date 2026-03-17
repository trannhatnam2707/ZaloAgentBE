from pydantic import BaseModel, Field


class GroupChat_Model(BaseModel):
    group_id: str = Field(...,description="Mã nhóm chat ")
    group_name: str = Field(..., description= "Tên nhóm chat")
    owner_id: str = Field(..., description="Tham chiếu tới _id của bảng Users (Chủ nhóm)")
    member: list[str] = Field(...,description="các thành viên trong nhóm")