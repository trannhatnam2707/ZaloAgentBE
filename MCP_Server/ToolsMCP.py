import json
import os
from datetime import datetime
from bson import ObjectId
import google.generativeai as genai
from dotenv import load_dotenv

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
def summarize_report(content: str) -> str:
    """Tóm tắt nội dung report bằng AI"""
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"Tóm tắt nội dung sau:\n{content}"
    response = model.generate_content(prompt)
    return response.text.strip()


# =====================================================
# 🧠 Tool: Tạo mới / cập nhật report
# =====================================================
def save_report_tool(username: str, date: str, yesterday: str = None, today: str = None, update_request: str = None) -> dict:
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
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
    Người dùng nhập: "{user_input}"
    Xác định hành động phù hợp (create_report, update_report, summarize_report)
    và trích xuất thông tin (date, yesterday, today, update_request).
    Trả về JSON hợp lệ với keys:
    {{
        "action": "create_report" | "update_report" | "summarize_report",
        "date": "...",
        "yesterday": "...",
        "today": "...",
        "update_request": "..."
    }}
    """
    ai_response = model.generate_content(prompt).text.strip()
    clean_json = ai_response.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean_json)
    except:
        return {"error": "Không thể hiểu yêu cầu người dùng."}