from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from Services.Ask_service import ask_agent, clear_chat_history
import traceback

router = APIRouter()

class AskRequest(BaseModel):
    question: str
    username: str
    session_id: str = None
    top_k: int = 50

class ClearHistoryRequest(BaseModel):
    session_id: str

@router.post("/ask")
def ask_endpoint(req: AskRequest):
    """
    Endpoint với error handling chi tiết
    """
    try:
        print("\n" + "="*80)
        print("RECEIVED REQUEST:")
        print(f"   - Username: {req.username}")
        print(f"   - Question: {req.question}")
        print(f"   - Session ID: {req.session_id}")
        print("="*80)
        
        # Kiểm tra username
        if not req.username or req.username.strip() == "":
            raise HTTPException(
                status_code=400,
                detail="Username là bắt buộc. Vui lòng đăng nhập."
            )
        
        # Dùng username làm session_id nếu không có
        session_id = req.session_id or req.username
        print(f"Session ID: {session_id}")
        
        # Gọi agent
        result = ask_agent(
            question=req.question,
            username=req.username,
            session_id=session_id,
            top_k=req.top_k
        )
        
        print("Agent response successful")
        
        return {
            "answer": result["answer"],
            "logs": result["logs"],
            "session_info": result.get("session_info"),
            "mcp_result": result.get("mcp_result")
        }
        
    except HTTPException as he:
        print(f"HTTP Exception: {he.detail}")
        raise he
        
    except Exception as e:
        print("\n" + "="*80)
        print("FATAL ERROR:")
        print(f"   Error Type: {type(e).__name__}")
        print(f"   Error Message: {str(e)}")
        print("\nFULL TRACEBACK:")
        traceback.print_exc()
        print("="*80 + "\n")
        
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi server: {type(e).__name__} - {str(e)}"
        )

@router.post("/clear-history")
def clear_history_endpoint(req: ClearHistoryRequest):
    """Xóa lịch sử chat"""
    try:
        success = clear_chat_history(req.session_id)
        return {
            "success": success,
            "message": "Đã xóa lịch sử" if success else "Session không tồn tại"
        }
    except Exception as e:
        print(f"Error clearing history: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/{session_id}")
def get_session_info(session_id: str):
    """Lấy thông tin session"""
    try:
        from Utils.Agent import conversational_agent
        
        if session_id in conversational_agent.sessions:
            memory = conversational_agent.sessions[session_id]
            return {
                "session_id": session_id,
                "message_count": len(memory.messages),
                "summary": memory.get_summary(),
                "exists": True
            }
        else:
            return {
                "session_id": session_id,
                "exists": False,
                "message": "Session chưa có lịch sử"
            }
    except Exception as e:
        print(f" Error getting session: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))