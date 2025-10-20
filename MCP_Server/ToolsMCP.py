# File: MCP_Server/ToolsMCP.py

import json
import os
from datetime import datetime
from bson import ObjectId
import google.generativeai as genai
from dotenv import load_dotenv

import sys
# Thêm thư mục cha vào path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Database.MongoDB import get_mongo_collection, users_collection
from Services.Report_service import create_report as create_report_service
from Utils.Embedding import sync_one_report

# =====================================================
# 🔧 Helper: Chuyển ObjectId / datetime → JSON hợp lệ
# =====================================================
def serialize_mongo_doc(doc):
    if isinstance(doc, list):
        return [serialize_mongo_doc(d) for d in doc]
    if isinstance(doc, dict):
        return {k: serialize_mongo_doc(v) for k, v in doc.items()}
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc

# =====================================================
# 🔧 Cấu hình
# =====================================================
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
reports_collection = get_mongo_collection("Report")

# =====================================================
# 🧠 Tool: Phân tích ý định của người dùng
# =====================================================
def analyze_user_intent(username: str, user_input: str) -> dict:
    """AI phân tích người dùng muốn làm gì: tạo hoặc cập nhật."""
    from datetime import datetime
    
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
    Người dùng nhập: "{user_input}"
    Ngày hiện tại: {datetime.now().strftime('%Y-%m-%d')}
    
    Xác định hành động phù hợp (create_report, update_report) và trích xuất thông tin.
    
    QUAN TRỌNG về format date (YYYY-MM-DD):
    - Nếu user nói "hôm nay" → dùng ngày hiện tại
    - Nếu user nói "ngày 09/10/2025" → chuyển thành "2025-10-09"
    
    QUAN TRỌNG về update_report:
    - "date" là ngày của report CẦN CẬP NHẬT.
    - "new_date" là ngày MỚI muốn đổi (nếu có).
    - "update_request" là yêu cầu cập nhật chi tiết.
    
    Ví dụ phân tích:
    1. "Tạo report hôm nay, hôm qua làm A, hôm nay làm B"
       → {{"action": "create_report", "date": "{datetime.now().strftime('%Y-%m-%d')}", "yesterday": "làm A", "today": "làm B"}}
    
    2. "Cập nhật report ngày 08/10, thêm task C"
       → {{"action": "update_report", "date": "2025-10-08", "update_request": "thêm task C vào today"}}
       
    Trả về JSON hợp lệ với keys:
    {{
        "action": "create_report" | "update_report",
        "date": "YYYY-MM-DD",
        "new_date": "YYYY-MM-DD" (optional),
        "yesterday": "...",
        "today": "...",
        "update_request": "..." (optional)
    }}
    """
    try:
        ai_response = model.generate_content(prompt).text.strip()
        clean_json = ai_response.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"❌ Lỗi phân tích intent: {e}")
        return {"error": f"Không thể hiểu yêu cầu người dùng: {str(e)}"}

# =====================================================
# 🚀 Tool: Lưu (Tạo/Cập nhật) report
# =====================================================
def save_report_tool(username: str, date: str, yesterday: str = None, today: str = None, 
                     update_request: str = None, new_date: str = None) -> dict:
    """
    Tạo hoặc Cập nhật báo cáo.
    
    Args:
        username: Tên người dùng
        date: Ngày của report (YYYY-MM-DD)
        yesterday: Nội dung công việc hôm qua (cho create)
        today: Nội dung công việc hôm nay (cho create)
        update_request: Yêu cầu cập nhật (cho update)
        new_date: Ngày mới nếu muốn đổi ngày report (cho update)
    """
    try:
        # Kiểm tra user tồn tại
        user = users_collection.find_one({"username": username})
        if not user:
            return {"success": False, "error": f"Không tìm thấy user '{username}'"}
        user_id = user["_id"]

        # Kiểm tra date hợp lệ
        if not date:
            return {"success": False, "error": "Thiếu thông tin 'date'"}

        # Kiểm tra report đã tồn tại chưa
        report = reports_collection.find_one({"user_id": user_id, "date": date})

        if report:
            # CẬP NHẬT report đã có
            print(f"🔄 Đang cập nhật report ngày {date} cho user {username}")
            update_data = {}
            
            if update_request:
                model = genai.GenerativeModel("gemini-2.5-flash")
                prompt = f"""
                Báo cáo hiện tại:
                - Ngày: {report.get('date')}
                - Hôm qua: {report.get('yesterday', '')}
                - Hôm nay: {report.get('today', '')}
                
                Yêu cầu cập nhật: {update_request}
                
                Hãy xuất ra JSON chỉ chứa những trường cần thay đổi.
                Ví dụ: {{"yesterday": "nội dung mới", "today": "nội dung mới"}}
                """
                try:
                    ai_response = model.generate_content(prompt).text.strip()
                    clean_text = ai_response.replace("```json", "").replace("```", "").strip()
                    ai_update = json.loads(clean_text)
                    for field in ["date", "yesterday", "today"]:
                        if field in ai_update and ai_update[field]:
                            update_data[field] = ai_update[field].strip()
                except json.JSONDecodeError:
                    # Fallback: cập nhật vào today
                    update_data["today"] = clean_text

            # Cập nhật từ tham số trực tiếp
            if yesterday: 
                update_data["yesterday"] = yesterday.strip()
            if today: 
                update_data["today"] = today.strip()
            if new_date: 
                update_data["date"] = new_date

            if not update_data:
                return {"success": False, "error": "Không có dữ liệu nào để cập nhật."}

            update_data["updated_at"] = datetime.utcnow()
            reports_collection.update_one({"_id": report["_id"]}, {"$set": update_data})
            report.update(update_data)
            
            # Đồng bộ lên Pinecone
            sync_one_report(report)
            
            return {
                "success": True,
                "message": f"✅ Report ngày {report['date']} đã được cập nhật.",
                "report": serialize_mongo_doc(report)
            }

        else:
            # TẠO MỚI report
            print(f"🆕 Đang tạo report mới ngày {date} cho user {username}")
            
            if not all([yesterday, today]):
                return {"success": False, "error": "Thiếu thông tin 'yesterday' hoặc 'today' để tạo báo cáo mới."}

            new_report = {
                "user_name": username,
                "date": date,
                "yesterday": yesterday.strip() if yesterday else "",
                "today": today.strip() if today else "",
            }
            
            # Gọi service để tạo report (bao gồm cả sync lên Pinecone)
            created = create_report_service(new_report)
            
            if not created:
                return {"success": False, "error": "Không thể tạo report mới"}
            
            return {
                "success": True,
                "message": f"🆕 Report mới cho '{username}' ngày {date} đã được tạo.",
                "report": serialize_mongo_doc(created)
            }
            
    except Exception as e:
        print(f"❌ Lỗi trong save_report_tool: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": f"Lỗi hệ thống: {str(e)}"}