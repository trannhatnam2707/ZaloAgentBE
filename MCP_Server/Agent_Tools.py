from Config.ModelAI import get_embedding
from Database.Pinecone import search_pinecone
from Services.Report_service import create_report, delete_report, update_report


def tool_create_report(user_name: str, date: str, yesterday: str, today: str, conversation_id: str) -> str:
    """
        Sử dụng Tool này để tạo 1 report mới cho người dùng.
        Bắt buộc phải thu thập đầy đủ 5 Thông tin sau: user_name, date, yesterday, today, conversation_id.
    """
    try:
        report_data = {
            "user_name": user_name,
            "date" : date,
            "yesterday" : yesterday,
            "today": today,
            "conversation_id" : conversation_id
        }
        created = create_report(report_data)
        return f"Đã tạo thành công báo cáo ngày {created.get(date)} cho {user_name}. ID báo cáo: {created.get("id")}"
    except Exception as e:
        return f"Lỗi khi tạo báo cáo: {str(e)}"

def tool_update_report(report_id: str, date: str = "", yesterday: str = "", today: str = "") -> str:
    """
        Sử dụng tool này để sửa/cập nhật nội dung một báo cáo Có sẵn (dựa vào report_id).
        Chỉ truyển vào những tham số mà người dùng muốn sửa. Các tham số không cần sửa thì để trống.
    """
    try:
        update_data = {}
        if date: update_data["date"] = date
        if yesterday: update_data["yesterday"] = yesterday
        if today : update_data["today"] = today

        if not update_data:
            return f"Vui lòng cung cấp  ít nhất 1 trường cần cập nhật"
        
        updated = update_report(report_id, update_data)
        if updated:
            return f"Đã cập nhật thành công report ID: {report_id}"
        return "Không tìm thấy báo cáo có ID này"
    except Exception as e:
        return f"Lỗi khi cập nhật báo cáo: {str(e)}"

def tool_delete_report(report_id: str) -> str:
    """
        Sử dụng tool này để xóa vĩnh viễn report khỏi hệ thống.
        Bắt buộc phải có report_id. Nếu người dùng yêu cầu xóa mà chưa cung cấp ID, thì phải hỏi lại hoặc dùng tool_search_reports để tìm ID đó rồi mới xóa. 
    """
    try: 
        success = delete_report(report_id)
        if success:
            return f"Đã xóa thành công report có ID: {report_id}"
        return f"Không tìm thấy được report có ID: {report_id} để xóa"
    except Exception as e:
        return f"Lỗi khi xóa report: {str(e)}"

def tool_search_reports(
    query: str,
    username: str,
    conversation_id: str,
    date_filter: str = "",
    filter_reporter_name: str = "",
    top_k: int = 20,
) -> str:
    """
    Tham số date_filter (YYYY-MM-DD) là tùy chọn, hãy lọc theo yêu cầu của người dùng. Không nhất thiết là phải đủ cả ngày, tháng, năm cụ thể mới search.
    Tìm báo cáo trong phòng chat (đã giới hạn bởi conversation_id). Truy vấn semantic chỉ mô tả
    nội dung cần tìm (công việc, chủ đề, ngày...). KHÔNG ghép tên người đang chat vào `query`
    trừ khi user hỏi cụ thể về một người — khi đó đặt tên đó vào `filter_reporter_name`.

    - username: người đang hỏi (chỉ để message/log, không dùng để lọc vector).
    - filter_reporter_name: tùy chọn, lọc theo metadata user_name khi user hỏi về một người cụ thể.
    """
    try:
        embedding = get_embedding(query)
        if not embedding:
            return "Không tạo được embedding cho câu tìm kiếm."

        pincone_filter: dict = {"conversation_id": {"$eq": conversation_id}}

        if (filter_reporter_name or "").strip():
            pincone_filter["user_name"] = {"$eq": (filter_reporter_name or "").strip()}

        results = search_pinecone(embedding, top_k, filter=pincone_filter)
        matches = results.get("matches", [])

        valid_matches = [m for m in matches if m.get("score", 0) >= 0.5]

        if date_filter:
            valid_matches = [
                m for m in valid_matches
                if m.get("metadata",{}).get("date", "").startswith(date_filter)
            ]

        if not valid_matches:
            return f"Không tìm thấy báo cáo nào trong phòng chat này khớp với từ khóa tìm kiếm: {query!r}"

        res_text = f" Tìm thấy {len(valid_matches)} báo cáo:\n\n"
        for i, match in enumerate(valid_matches,1):
            meta = match.get("metadata",{})
            res_text += f"--- Kết quả {i} (Độ tin cậy: {match.get("score",0):.2f})---\n"
            res_text += f"Ngày: {meta.get("date")}\n"
            res_text += f"Nội dung: {meta.get("text")}\n"
            res_text += f"Người báo cáo: {meta.get("user_name")}\n\n"
        return res_text

    except Exception as e:
        return f"Lỗi khi tìm kiếm trên pinecone: {str(e)}"
GEMINI_TOOLS = [
    tool_create_report,
    tool_update_report,
    tool_delete_report,
    tool_search_reports
]

        