from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from Services.Ask_service import ask_agent


router = APIRouter()

class AskRequest(BaseModel):
    question: str
    username: Optional[str] = None  # Optional, chỉ bắt buộc khi thực hiện action
    top_k: int = 5

@router.post("/ask")
def ask_endpoint(req: AskRequest):
    """
    Endpoint chính để user tương tác với Agent
    
    - Nếu user hỏi thông tin → Agent tìm kiếm và trả lời
    - Nếu user yêu cầu action (tạo/cập nhật/tóm tắt report) → Agent gọi MCP Server
    """
    try:
        result = ask_agent(
            question=req.question,
            username=req.username,
            top_k=req.top_k
        )
        return {
            "answer": result["answer"],
            "logs": result["logs"],
            "mcp_result": result.get("mcp_result")  # Trả về kết quả từ MCP nếu có
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi gọi agent: {e}")