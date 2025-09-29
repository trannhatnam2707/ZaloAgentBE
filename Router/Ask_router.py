from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from Services.Ask_service import ask_agent


router = APIRouter()

class AskRequest(BaseModel):
    question: str
    top_k: int = 1000

@router.post("/ask")
def ask_endpoint(req: AskRequest):
    try:
        result = ask_agent(req.question, req.top_k)
        return {
            "answer": result["answer"],
            "logs": result["logs"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi gọi agent: {e}")
