from bson import ObjectId
from fastapi import HTTPException
from Database.MongoDB import db

try:
    from MCP_Client.Agent import conversational_agent
    print("Import conversational_agent thành công")
except ImportError as e:
    print(f"Lỗi import conversational_agent: {e}")
    raise
except Exception as e:
    print(f"Lỗi khác khi import: {e}")
    raise

def ask_agent(question: str, username: str, current_user_id: str,  session_id: str, top_k: int = 10) -> dict:
    """
    Service layer để gọi Conversational Agent
    
    Args:
        question: Câu hỏi/yêu cầu từ user
        username: Tên user (BẮT BUỘC từ FE)
        session_id: ID phiên chat
        top_k: Số lượng kết quả search
    
    Returns:
        dict: Kết quả từ Agent
    """

    try:

        conversation = db.Conversations.find_one({"_id": ObjectId(session_id)})

        if not conversation:
            raise HTTPException(status_code=404, detail = "Không tìm thấy phòng chat này." )
        
        if ObjectId(current_user_id ) not in conversation.get("members", []):
            raise HTTPException(status_code=403, detail=" Bạn không có quyền trong đoạn chat này?") 

        print(f"[Ask_service] Calling agent with:")
        print(f"   - username: {username}")
        print(f"   - session_id: {session_id}")
        print(f"   - question: {question}")
        
        result = conversational_agent.run(
            user_query=question,
            username=username,
            user_id=current_user_id,
            session_id=session_id,
            top_k=top_k,
        )
        
        print("Ask_service] Agent returned result")
        return result
        
    except Exception as e:
        print(f"[Ask_service] Error: {e}")
        import traceback
        traceback.print_exc()
        raise

def clear_chat_history(session_id: str) -> bool:
    """
    Xóa lịch sử chat của một session
    """

    try:
        return conversational_agent.clear_session(session_id)
    except Exception as e:
        print(f"[clear_chat_history] Error: {e}")
        return False