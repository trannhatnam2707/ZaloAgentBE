import datetime
from bson import ObjectId
from Database.MongoDB import get_mongo_collection, users_collection
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
    }
    
#Create
def create_report(data: dict) -> dict: 
    # Tìm user theo user_name để lấy user_id
    user = users_collection.find_one({"username": data["user_name"]})
    if not user:
        raise ValueError("User not found")
    
    # Thay thế user_name bằng user_id
    data["user_id"] = user["_id"]
    data.pop("user_name", None)  # Xóa user_name khỏi data
    
    data["created_at"] = datetime.datetime.utcnow()
    data["updated_at"] = datetime.datetime.utcnow()
    
    result = reports_collection.insert_one(data)
    new_report = reports_collection.find_one({"_id": result.inserted_id})
# ✅ Sync ngay sang Pinecone
    from Utils.Embedding import sync_one_report
    sync_one_report(new_report)

    return report_helper(new_report)

#Get All
def get_all_reports() -> list:
    reports = reports_collection.find()
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
        # ✅ Sync ngay sang Pinecone
        from Utils.Embedding import sync_one_report
        sync_one_report(updated)
        return report_helper(updated)
    return None 

#delete
def delete_report(id: str) -> bool:
    """Xóa trong Mongo và Pinecone"""
    result = reports_collection.delete_one({"_id": ObjectId(id)})

    if result.deleted_count:
        # Xóa toàn bộ vector có metadata.report_id = id
        index.delete(filter={"report_id": id})
        print(f" Deleted report {id} khỏi Mongo & Pinecone")
        return True
    else: 
        print(f" Report {id} không tồn tại trong Mongo")
        return False