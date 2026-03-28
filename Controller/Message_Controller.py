from Services.Message_service import MessageService
from Schemas.Message_schema import MessageCreate

class MessageController:
    
    @staticmethod
    def send_new_message(data: MessageCreate, current_user_id: str):
        return MessageService.send_message(data, current_user_id)

    @staticmethod
    def get_messages(conversation_id: str, current_user_id: str, skip: int, limit: int):
        return MessageService.get_conversation_messages(conversation_id, current_user_id, skip, limit)

    @staticmethod
    def get_ai_history(conversation_id: str, current_user_id: str):
        raw_messages = MessageService.get_ai_bubble_history(conversation_id, current_user_id)
        
        # Format lại dữ liệu ObjectId thành String để Schema không bị lỗi
        formatted_messages = []
        for msg in raw_messages:
            msg["id"] = str(msg["_id"])
            msg["conversation_id"] = str(msg["conversation_id"])
            msg["sender_id"] = str(msg["sender_id"])
            formatted_messages.append(msg)
            
        return formatted_messages