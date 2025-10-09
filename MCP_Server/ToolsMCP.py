import json
import os
from datetime import datetime
from bson import ObjectId
import google.generativeai as genai
from dotenv import load_dotenv

import sys
import os
# Thêm thư mục cha vào path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Database.MongoDB import get_mongo_collection, users_collection
from Utils.Embedding import sync_one_report


# =====================================================
# 🔧 Helper: Chuyển ObjectId / datetime → JSON hợp lệ
# =====================================================
def serialize_mongo_doc(doc):
    """Đệ quy chuyển ObjectId và datetime thành kiểu JSON hợp lệ"""
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
# 🧠 Tool: Tóm tắt report bằng AI
# =====================================================
def summarize_report(username: str, date: str = None) -> dict:
    """
    Tóm tắt report của user
    
    Args:
        username: Tên user
        date: Ngày cụ thể (optional), nếu không có thì tóm tắt tất cả
    
    Returns:
        dict: Kết quả tóm tắt
    """
    # Tìm user
    user = users_collection.find_one({"username": username})
    if not user:
        return {"error": f"Không tìm thấy user '{username}'"}
    
    user_id = user["_id"]
    
    # Tìm reports
    query = {"user_id": user_id}
    if date:
        query["date"] = date
    
    reports = list(reports_collection.find(query))
    
    if not reports:
        return {"error": f"Không tìm thấy report nào cho user '{username}'"}
    
    # Tạo nội dung để tóm tắt
    content_parts = []
    for r in reports:
        content_parts.append(f"""
Ngày: {r.get('date', '')}
Hôm qua: {r.get('yesterday', '')}
Hôm nay: {r.get('today', '')}
---
""")
    
    full_content = "\n".join(content_parts)
    
    # Gọi AI để tóm tắt
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
Tóm tắt các báo cáo công việc sau đây của user {username}:

{full_content}

Hãy tóm tắt ngắn gọn, rõ ràng những công việc chính đã làm.
"""
    
    response = model.generate_content(prompt)
    summary = response.text.strip()
    
    return {
        "message": f"✅ Đã tóm tắt {len(reports)} report(s)",
        "summary": summary,
        "reports_count": len(reports)
    }


# =====================================================
# 🧠 Tool: Tạo mới / cập nhật report
# =====================================================
def save_report_tool(username: str, date: str, yesterday: str = None, today: str = None, update_request: str = None, new_date: str = None) -> dict:
    """
    🧩 Tạo mới hoặc cập nhật report tự động.
    - Nếu chưa có → tạo mới
    - Nếu có → cập nhật 1 hoặc nhiều trường (date, yesterday, today)
    - Có thể cập nhật qua ngôn ngữ tự nhiên bằng `update_request`
    """

    # 1️⃣ Tìm user
    user = users_collection.find_one({"username": username})
    if not user:
        return {"error": f"Không tìm thấy user '{username}'"}
    user_id = user["_id"]

    # 2️⃣ Tìm report theo user_id + date
    report = reports_collection.find_one({"user_id": user_id, "date": date})

    # =====================================================
    # 🔄 Nếu report đã tồn tại → cập nhật
    # =====================================================
    if report:
        update_data = {}

        # ✅ Nếu có yêu cầu cập nhật bằng ngôn ngữ tự nhiên
        if update_request:
            model = genai.GenerativeModel("gemini-2.5-flash")
            prompt = f"""
            Đây là báo cáo hiện tại:
            - Ngày báo cáo: {report.get('date')}
            - Hôm qua: {report.get('yesterday', '')}
            - Hôm nay: {report.get('today', '')}

            Người dùng muốn cập nhật: {update_request}

            Hãy xuất ra JSON hợp lệ, chỉ chứa những trường cần thay đổi
            (có thể gồm 'date', 'yesterday', 'today'), không cần thêm giải thích.
            """
            ai_response = model.generate_content(prompt).text.strip()

            # 🧹 Làm sạch phần text mà Gemini trả về
            clean_text = (
                ai_response.replace("```json", "")
                .replace("```", "")
                .strip()
            )

            # 🧠 Parse JSON
            try:
                ai_update = json.loads(clean_text)
                for field in ["date", "yesterday", "today"]:
                    if field in ai_update and ai_update[field]:
                        update_data[field] = ai_update[field].strip()
            except json.JSONDecodeError:
                update_data["today"] = clean_text  # fallback

        # ✅ Nếu người dùng truyền trực tiếp
        if yesterday:
            update_data["yesterday"] = yesterday.strip()
        if today:
            update_data["today"] = today.strip()
        if date and date != report["date"]:
            update_data["date"] = date

        if not update_data:
            return {"error": "Không có dữ liệu nào để cập nhật."}

        # Cập nhật thời gian
        update_data["updated_at"] = datetime.utcnow()

        # Thực hiện update
        reports_collection.update_one({"_id": report["_id"]}, {"$set": update_data})
        report.update(update_data)

        # Đồng bộ Pinecone
        sync_one_report(report)

        return {
            "message": f"✅ Report của '{username}' ngày {report['date']} đã được cập nhật.",
            "report": serialize_mongo_doc(report)
        }

    # =====================================================
    # 🆕 Nếu report chưa tồn tại → tạo mới
    # =====================================================
    new_report = {
        "user_id": user_id,
        "date": date,
        "yesterday": yesterday.strip() if yesterday else "",
        "today": today.strip() if today else "",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    # ✅ Lưu Mongo
    inserted = reports_collection.insert_one(new_report)
    new_report["_id"] = str(inserted.inserted_id)

    # ✅ Sync Pinecone
    sync_one_report(new_report)

    return {
        "message": f"🆕 Report mới cho '{username}' ngày {date} đã được tạo thành công.",
        "report": serialize_mongo_doc(new_report)
    }

# =====================================================
# 🧠 Tool: Phân tích ý định người dùng
# =====================================================
def analyze_user_intent(username: str, user_input: str) -> dict:
    """AI phân tích người dùng muốn làm gì: tạo, cập nhật hay tóm tắt"""
    from datetime import datetime
    
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
    Người dùng nhập: "{user_input}"
    Ngày hiện tại: {datetime.now().strftime('%Y-%m-%d')}
    
    Xác định hành động phù hợp (create_report, update_report, summarize_report)
    và trích xuất thông tin.
    
    QUAN TRỌNG về format date (YYYY-MM-DD):
    - Nếu user nói "hôm nay" → dùng ngày hiện tại
    - Nếu user nói "ngày 09/10/2025" → chuyển thành "2025-10-09"
    - Nếu user nói "ngày 08/10/2025" → chuyển thành "2025-10-08"
    
    QUAN TRỌNG về update_report:
    - "date" là ngày của report CẦN CẬP NHẬT (report hiện có trong DB)
    - "new_date" là ngày MỚI muốn đổi (nếu user muốn đổi ngày)
    - "update_request" là yêu cầu cập nhật chi tiết
    
    Ví dụ phân tích:
    1. "Tạo report hôm nay, hôm qua làm A, hôm nay làm B"
       → {{"action": "create_report", "date": "2025-10-09", "yesterday": "làm A", "today": "làm B"}}
    
    2. "Cập nhật report ngày 08/10, thêm task C"
       → {{"action": "update_report", "date": "2025-10-08", "update_request": "thêm task C vào today"}}
    
    3. "Cập nhật ngày 08/10/2025 thành ngày 09/10/2025 với nội dung today là X"
       → {{"action": "update_report", "date": "2025-10-08", "new_date": "2025-10-09", "update_request": "đổi date thành 2025-10-09 và today thành X"}}
    
    4. "Tóm tắt báo cáo tuần này"
       → {{"action": "summarize_report"}}
    
    Trả về JSON hợp lệ với keys:
    {{
        "action": "create_report" | "update_report" | "summarize_report",
        "date": "YYYY-MM-DD (ngày của report cần thao tác)",
        "new_date": "YYYY-MM-DD (chỉ có khi user muốn đổi ngày)" (optional),
        "yesterday": "..." (chỉ cho create_report),
        "today": "..." (chỉ cho create_report),
        "update_request": "..." (chỉ cho update_report)
    }}
    """
    ai_response = model.generate_content(prompt).text.strip()
    clean_json = ai_response.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean_json)
    except:
        return {"error": "Không thể hiểu yêu cầu người dùng."}