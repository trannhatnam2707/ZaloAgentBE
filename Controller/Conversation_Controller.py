from Services.Conversation_service import ConversationService
from Schemas.Conversation_schema import ConversationCreate

class ConversationController:
    @staticmethod
    def get_all_my_chats(current_user_id: str, keyword: str = ""):
        return ConversationService.get_my_conversation(current_user_id, keyword)
    
    @staticmethod
    def start_chat(data: ConversationCreate, current_user_id: str):
        if data.type == "direct":
            target_user_id = data.members[0] if data.members else ""
            return ConversationService.create_or_get_direct_chat(current_user_id, target_user_id, data.name)
        elif data.type == "group":
            return ConversationService.create_group_chat(data.name, data.members, current_user_id)
    
    @staticmethod
    def add_member(conservation_id: str, new_member_id: str):
        return ConversationService.add_member_to_group(conservation_id, new_member_id)
    
    @staticmethod
    def kick_member(conservation_id: str, new_member_id: str):
        return ConversationService.remove_member_from_group(conservation_id,new_member_id)

    @staticmethod
    def leave_group(conversation_id: str, current_user_id: str):
        """
        Logic rời nhóm: Thực chất là gỡ bản thân (current_user_id) ra khỏi nhóm.
        Nếu service của bạn có logic tự động xóa nhóm khi = 0 người thì càng tốt!
        """
        return ConversationService.remove_member_from_group(conversation_id, current_user_id)