import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Thêm thư mục cha vào sys.path để import được các module khác
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from MCP_Server.ToolsMCP import save_report_tool, summarize_report, analyze_user_intent

app = FastAPI(title="AgentZalo MCP Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/ask")
async def ask_agent(request: dict):
    """
    Endpoint chính:
    - Người dùng gõ câu tự nhiên (ví dụ: 'Tạo report hôm nay cho nhatnam...')
    - Backend tự phân tích ý định và gọi tool tương ứng
    """
    username = request.get("username", "unknown")
    message = request.get("message", "")

    intent = analyze_user_intent(username, message)
    if "error" in intent:
        return {"success": False, "error": intent["error"]}

    action = intent.get("action")
    date = intent.get("date")
    new_date = intent.get("new_date")  # Thêm new_date
    yesterday = intent.get("yesterday")
    today = intent.get("today")
    update_request = intent.get("update_request")

    if action == "summarize_report":
        result = summarize_report(username, date)
    elif action in ["create_report", "update_report"]:
        result = save_report_tool(username, date, yesterday, today, update_request, new_date)
    else:
        result = {"error": f"Không xác định được hành động: {action}"}

    return {"success": True, "result": result}



if __name__ == "__main__":
    print("🚀 MCP Server running at http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
