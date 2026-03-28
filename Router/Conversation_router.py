from typing import List
from fastapi import APIRouter, Depends
from Middleware.Auth_middleware import get_current_user, require_owner
from Schemas.Conversation_schema import ConversationCreate, ConversationResponse
from Controller.Conversation_Controller import ConversationController


router = APIRouter(prefix="/conservations", tags=["Conservations"])

@router.get("/", response_model=List[ConversationResponse])
def api_get_my_conservations(current_user: dict = Depends(get_current_user)):
    return ConversationController.get_all_my_chats(str(current_user["_id"]))

@router.post("/", response_model=ConversationResponse)
def api_create_conservation(data: ConversationCreate, current_user: dict = Depends(get_current_user)):
    # Tạo phòng chat mới : 
    # -Nếu type:"redict": truyền 1 ID của Bạn bè vào mảng member.
    # -Nếu type:"Group" : truyền group_name và danh sách ID vào mảng member
    return ConversationController.start_chat(data, str(current_user["_id"]))

@router.put("/{conversation_id}/members/{new_member_id}")
def api_add_member(
    conservation_id: str,
    new_member_id: str,
    group: dict = Depends(require_owner)
):
    return ConversationController.add_member(conservation_id, new_member_id)

@router.delete("/{conservation_id}/members/{member_to_kick_id}", response_model=ConversationResponse)
def api_kick_member(
    conservation_id: str,
    member_to_kick_id:str,
    group: dict = Depends(require_owner)
):
    return ConversationController.kick_member(conservation_id,member_to_kick_id)