from typing import List
from fastapi import APIRouter, Depends, Query
from Middleware.Auth_middleware import get_current_user, require_owner
from Schemas.Conversation_schema import ConversationCreate, ConversationResponse, LeaveGroupRequest
from Controller.Conversation_Controller import ConversationController


router = APIRouter(prefix="/conservations", tags=["Conservations"])

@router.get("/", response_model=List[ConversationResponse])
def api_get_my_conservations(
    keyword: str = Query(default="", description="Từ khóa tìm theo tên hội thoại"),
    current_user: dict = Depends(get_current_user)
):
    return ConversationController.get_all_my_chats(str(current_user["_id"]), keyword)

@router.post("/", response_model=ConversationResponse)
def api_create_conservation(data: ConversationCreate, current_user: dict = Depends(get_current_user)):
    # Tạo phòng chat mới : 
    # -Nếu type:"redict": truyền 1 ID của Bạn bè vào mảng member.
    # -Nếu type:"Group" : truyền group_name và danh sách ID vào mảng member
    return ConversationController.start_chat(data, str(current_user["_id"]))

@router.put("/{conversation_id}/members/{new_member_id}")
def api_add_member(
    conversation_id: str,
    new_member_id: str,
    group: dict = Depends(require_owner)
):
    return ConversationController.add_member(conversation_id, new_member_id)

@router.delete("/{conservation_id}/members/{member_to_kick_id}", response_model=ConversationResponse)
def api_kick_member(
    conservation_id: str,
    member_to_kick_id:str,
    group: dict = Depends(require_owner)
):
    return ConversationController.kick_member(conservation_id,member_to_kick_id)

@router.post("/{conversation_id}/leave")
def leave_conversation(conversation_id: str, req: LeaveGroupRequest):
    result = ConversationController.leave_group(conversation_id, req.user_id)
    return {
        "success": True,
        "message": "Đã rời nhóm thành công",
        "data": result
    }