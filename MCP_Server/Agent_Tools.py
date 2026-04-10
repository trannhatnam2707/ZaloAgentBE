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

def tool_search_reports(query: str, username: str, date_filter: str ="", top_k: int = 5) -> str:
    """
        Sử dụng công cụ này để tìm kiếm và tra cứu các report công việc cũ của người dùng.
        Tham số date_filter (YYYY-MM-DD) là tùy chọn, chỉ truyền vào nếu người dùng chỉ định rõ ngày tháng cụ thể.
        Dùng khi người dùng hỏi các câu như "Hôm qua/tuần qua anh A làm gì", "hay là nội dung X anh A làm vào lúc nào" ,...... 
    """
    try: 
        embedding = get_embedding(f"Báo cáo của {username} về : {query}")

        pincone_filter = None
        if date_filter :
            pincone_filter = {"date": {"$eq":date_filter}}
        results = search_pinecone(embedding, top_k, filter=pincone_filter)
        matches = results.get("matches", [])

        valid_matches = [m for m in matches if m.get('score', 0) >= 0.7]

        if not valid_matches:
            return f"Không tìm thấy báo cáo nào của {username} khớp với {query}"

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

        