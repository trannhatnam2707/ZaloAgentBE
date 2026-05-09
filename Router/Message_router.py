from fastapi import APIRouter, Depends, Query
from Controller.Message_Controller import MessageController
from Schemas.Message_schema import MessageCreate, MessageResponse
from Middleware.Auth_middleware import get_current_user
from typing import List

router = APIRouter(prefix="/messages", tags=["Messages"])
@router.post("/", response_model=MessageResponse)
def api_send_message(
    data: MessageCreate,
    current_user: dict = Depends(get_current_user)
):
    #Nếu là gửi trong bong bóng chat AI thì FE kèm theo metadata : {"is_ai_bubble": true}
    user_id = str(current_user["_id"])
    return MessageController.send_new_message(data, user_id)

@router.get("/{conversation_id}", response_model=List[MessageResponse])
def api_get_message_history( 
    conversation_id: str,
    skip: int = Query(0, description="Bỏ qua bao nhiêu tin nhắn"),
    limit: int = Query(50, description="lấy tối đa bao nhiêu tin nhắn 1 lần"),
    current_user: dict = Depends(get_current_user)
):
    # Lấy ID của user hiện tại
    user_id = str(current_user["_id"])
    
   
    messages =  MessageController.get_messages(conversation_id, user_id, skip, limit)
    
    return messages

@router.get("/ai-bubble/{conversation_id}", response_model=List[MessageResponse])
def api_get_ai_bubble_history(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
   
    #Lấy danh sách tin nhắn giữa User và AI trong khung chat riêng
  
    user_id = str(current_user["_id"])
    return MessageController.get_ai_history(conversation_id, user_id)