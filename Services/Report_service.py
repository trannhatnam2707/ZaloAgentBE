import datetime
from bson import ObjectId
from fastapi import HTTPException
from Database.MongoDB import get_mongo_collection, users_collection, db
from Database.Pinecone import index


#collection Report
reports_collection = get_mongo_collection("Report")

#Helpers: convert ObjectId to string
def report_helper(report) -> dict:
    user = users_collection.find_one({"_id": ObjectId(report["user_id"])})
    user_name = user["username"] if user else "Unknown"

    return {
        "id": str(report["_id"]),
        "user_id": str(report["user_id"]),   # map tới Users._id
        "user_name": user_name,              # lấy từ Users.username
        "date": report["date"],
        "yesterday": report["yesterday"],
        "today": report["today"],
        "created_at": report["created_at"],
        "updated_at": report["updated_at"],
        "conversation_id": str(report.get("conversation_id", ""))
    }
    
#Create
def create_report(data: dict) -> dict: 

    user_id = data.get("user_id")
    

    # Check trùng lặp chuẩn xác tuyệt đối
    existing_report = reports_collection.find_one({
        "user_id": {"$in": [user_id, str(user_id), ObjectId(user_id)]},
        "date": data["date"]
    })
    
    if existing_report:
        raise HTTPException(
            status_code=400,
            detail=f"Bạn đã có báo cáo cho ngày {data['date']} rồi! Hãy cập nhật nếu bạn muốn sửa đổi lại nội dung report."
        )
    data["user_id"] = ObjectId(str(user_id))
    data["created_at"] = datetime.datetime.utcnow()
    data["updated_at"] = datetime.datetime.utcnow()
    
    result = reports_collection.insert_one(data)
    new_report = reports_collection.find_one({"_id": result.inserted_id})
    #Sync ngay sang Pinecone
    from Utils.Embedding import sync_one_report
    sync_one_report(new_report)

    return report_helper(new_report)

#Get All
def get_all_reports() -> list:
    reports = reports_collection.find()
    return [report_helper(report) for report in reports]

#Get by conversation_id
def get_reports_by_conversation(conversation_id: str, current_user_id: str) -> list:
    try:
        conv_id = ObjectId(conversation_id)
    except:
        raise HTTPException(status_code=400, detail="ID phòng chat không hợp lệ")

    conversation = db.Conversations.find_one({"_id": conv_id})
    if not conversation:
        print(f"DEBUG: Không tìm thấy conversation với ID: {conv_id}")
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng chat")
    user_str = str(current_user_id)
    member_list_str = [str(m) for m in conversation.get("members", [])]
    if user_str not in member_list_str:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem báo cáo này")

    reports = reports_collection.find({"conversation_id": conv_id}).sort("created_at", -1)
    return [report_helper(report) for report in reports]

#get by user_id
def get_reports_by_user(user_id: str) -> list:
    reports = reports_collection.find({"user_id": ObjectId(user_id)})
    return [report_helper(report) for report in reports]

#Update
def update_report(id: str, data: dict) -> dict | None :
    data["updated_at"] = datetime.datetime.utcnow()
    result = reports_collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": data}
    )
    if result.modified_count:
        updated = reports_collection.find_one({"_id": ObjectId(id)})
        # Sync ngay sang Pinecone
        from Utils.Embedding import sync_one_report
        sync_one_report(updated)
        return report_helper(updated)
    return None 

#delete
# Services/Report_service.py

def delete_report(id: str) -> bool:
    """Xóa trong Mongo (cả bảng Report và Messages) và Pinecone"""
    try:
        report_id_obj = ObjectId(id)
        
        # 1. Tìm thông tin report trước khi xóa để lấy dữ liệu đồng bộ
        report = reports_collection.find_one({"_id": report_id_obj})
        if not report:
            return False

        # 2. XÓA TIN NHẮN TƯƠNG ỨNG TRONG BẢNG MESSAGES (Quan trọng để mất trên UI)
        # Chúng ta tìm tin nhắn có metadata.report_id trùng với id của report đang xóa
        from Database.MongoDB import db
        db.Messages.delete_many({"metadata.report_id": id}) 

        # 3. Xóa trong bảng Report
        result = reports_collection.delete_one({"_id": report_id_obj})

        # 4. Xóa trong Pinecone (giữ nguyên logic cũ của bạn)
        try:
            from Database.Pinecone import index
            index.delete(filter={"report_id": id})
            print(f" Deleted report {id} khỏi Mongo & Pinecone")
            return True

        except Exception as e:
            print(f"Lỗi xóa Pinecone: {e}")

        return result.deleted_count > 0
    except Exception as e:
        print(f"Lỗi khi xóa report: {e}")
        return False