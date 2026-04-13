from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from Middleware.Auth_middleware import get_current_user
from Services.Ask_service import ask_agent
import traceback

router = APIRouter(prefix="/ask", tags=["AskAI"])

class AskRequest(BaseModel):
    question: str
    username: str
    session_id: str = None
    top_k: int = 50

class ClearHistoryRequest(BaseModel):
    session_id: str

@router.post("/")
def ask_endpoint(req: AskRequest, current_user: dict = Depends(get_current_user)):
    """
    Endpoint với error handling chi tiết
    """
    user_id = str(current_user["_id"])
    real_name = current_user.get("display_name") or current_user.get("username")
    try:
        print("\n" + "="*80)
        print("RECEIVED REQUEST:")
        print(f"   - Username: {req.username}")
        print(f"   - Question: {req.question}")
        print(f"   - Session ID: {req.session_id}")
        print("="*50)
        
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
            username=real_name,
            session_id=session_id,
            top_k=req.top_k,
            current_user_id = user_id
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

# @router.post("/clear-history")
# def clear_history_endpoint(req: ClearHistoryRequest):
#     """Xóa lịch sử chat"""
#     try:
#         success = clear_chat_history(req.session_id)
#         return {
#             "success": success,
#             "message": "Đã xóa lịch sử" if success else "Session không tồn tại"
#         }
#     except Exception as e:
#         print(f"Error clearing history: {e}")
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))
