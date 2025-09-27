from fastapi import APIRouter, HTTPException


from Schemas.Report_schema import ReportCreate, ReportResponse
from Services.Report_service import create_report, delete_report, get_all_reports, get_reports_by_user, update_report


router = APIRouter(prefix="/reports", tags=["Reports"])

#Create Report
@router.post("/", response_model=ReportResponse)
def api_create_report(report: ReportCreate):
    return create_report(report.dict())

#Get All Reports
@router.get("/", response_model=list[ReportResponse])
def api_get_all_reports():
    return get_all_reports()

#Get Reports by User
@router.get("/user/{user_id}", response_model=list[ReportResponse])
def api_get_reports_by_user(user_id: str):
    return get_reports_by_user(user_id)

#Update Report
@router.put("/{report_id}", response_model=ReportResponse | None)
def api_update_report(report_id: str,report: ReportCreate):
    updated = update_report(report_id, report.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Report not found")
    return updated

@router.delete("/{id}")
def api_delete_report(id: str):
    success = delete_report(id)
    if success:
        return{"message": f"Report {id} đã được xoá thành công"}
    else:
        raise HTTPException(status_code=404, detail="Report not found")
