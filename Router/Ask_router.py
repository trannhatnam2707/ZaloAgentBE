from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from Services.Ask_service import ask_agent


router = APIRouter()

class AskRequest(BaseModel):
    question: str
    username: str  # ✅ Bắt buộc phải có username
    top_k: int = 10

@router.post("/ask")
def ask_endpoint(req: AskRequest):
    """
    Endpoint chính để user tương tác với Agent
    
    - Username BẮT BUỘC từ FE (lấy từ localStorage)
    - Nếu user hỏi thông tin → Agent tìm kiếm và trả lời
    - Nếu user yêu cầu action (tạo/cập nhật/tóm tắt report) → Agent gọi MCP Server
    """
    try:
        # ✅ Kiểm tra username
        if not req.username or req.username.strip() == "":
            raise HTTPException(
                status_code=400, 
                detail="Username là bắt buộc. Vui lòng đăng nhập."
            )
        
        result = ask_agent(
            question=req.question,
            username=req.username,
            top_k=req.top_k
        )
        return {
            "answer": result["answer"],
            "logs": result["logs"],
            "mcp_result": result.get("mcp_result")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi gọi agent: {e}")