from pydantic import Field


class GroupChat_Model:
    group_id: str = Field(...,description="Mã nhóm chat ")
    group_name: str = Field(..., description= "Tên nhóm chat")
    owner_id: str = Field(..., description="Tham chiếu tới _id của bảng Users (Chủ nhóm)")
    member: str = Field(...,description="các thành viên trong nhóm")