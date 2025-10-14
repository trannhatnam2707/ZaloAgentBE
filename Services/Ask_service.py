try:
    from Utils.Agent import conversational_agent
    print("✅ Import conversational_agent thành công")
except ImportError as e:
    print(f"❌ Lỗi import conversational_agent: {e}")
    raise
except Exception as e:
    print(f"❌ Lỗi khác khi import: {e}")
    raise

def ask_agent(question: str, username: str, session_id: str, top_k: int = 10) -> dict:
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
        print(f"🔄 [Ask_service] Calling agent with:")
        print(f"   - username: {username}")
        print(f"   - session_id: {session_id}")
        print(f"   - question: {question}")
        
        result = conversational_agent.run(
            user_query=question,
            username=username,
            session_id=session_id,
            top_k=top_k
        )
        
        print("✅ [Ask_service] Agent returned result")
        return result
        
    except Exception as e:
        print(f"❌ [Ask_service] Error: {e}")
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
        print(f"❌ [clear_chat_history] Error: {e}")
        return False