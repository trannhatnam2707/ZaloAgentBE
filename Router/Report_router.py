from fastapi import APIRouter, HTTPException, Depends


from Schemas.Report_schema import ReportCreate, ReportResponse
from Services.Report_service import create_report, delete_report, get_all_reports, get_reports_by_user, update_report, get_reports_by_conversation
from Middleware.Auth_middleware import get_current_user


router = APIRouter(prefix="/reports", tags=["Reports"])

#Create Report
@router.post("/")
def api_create_report(
    report: ReportCreate, 
    current_user: dict = Depends(get_current_user) # Hàm check token của bạn
):
    # 1. IN RA ĐỂ XEM TOKEN ĐANG CHỨA GÌ (Xem log ở Terminal)
    print("DEBUG CURRENT_USER:", current_user)

    # 2. Lấy ID an toàn (Quét mở rộng các key thường dùng trong JWT)
    raw_id = current_user.get("_id") or current_user.get("id") or current_user.get("user_id") or current_user.get("sub")
    
    # 3. CHẶN ĐỨNG NẾU ID BỊ RỖNG
    if not raw_id:
        raise HTTPException(
            status_code=401, 
            detail=f"Không thể xác định ID người dùng! Dữ liệu token hiện tại: {current_user}"
        )

    # 4. Gán ID chuẩn xác vào data
    data = report.dict()
    data["user_id"] = str(raw_id) 
    
    return create_report(data)

#Get All Reports
@router.get("/", response_model=list[ReportResponse])
def api_get_all_reports(current_user: dict = Depends(get_current_user)):
    return get_all_reports()

#Get Reports by User
@router.get("/user/{user_id}", response_model=list[ReportResponse])
def api_get_reports_by_user(user_id: str, current_user: dict = Depends(get_current_user)):
    # Có thể thêm check xem current_user có trùng user_id không nếu cần bảo mật kỹ hơn
    return get_reports_by_user(user_id)

#Get Reports by Conversation
@router.get("/conversation/{conversation_id}", response_model=list[ReportResponse])
def api_get_reports_by_conversation(conversation_id: str, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])
    return get_reports_by_conversation(conversation_id, user_id)

#Update Report
@router.put("/{report_id}", response_model=ReportResponse | None)
def api_update_report(report_id: str, report: ReportCreate, current_user: dict = Depends(get_current_user)):
    updated = update_report(report_id, report.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Report not found")
    return updated

@router.delete("/{id}")
def api_delete_report(id: str, current_user: dict = Depends(get_current_user)):
    success = delete_report(id)
    if success:
        return{"message": f"Report {id} đã được xoá thành công"}
    else:
        raise HTTPException(status_code=404, detail="Report not found")
