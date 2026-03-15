from pymongo import MongoClient
from bson.objectid import ObjectId

MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB_NAME = "AgentZalo"

client = MongoClient(MONGO_URI) 
db = client[MONGO_DB_NAME]

def migrate_legacy_data():
    print("Bắt đầu đồng bộ dữ liệu.")

    #step 1: get list old users 
    users = list(db.Users.find({}))
    if not users:
        print("Không có users nào trong DB. Hủy quá trình")
        return
    all_user_ids = [user["_id"] for user in users]

    owner = next((u for u in users if u.get("username") == "nhatnam"), users[0])
    owner_id = owner["_id"]

    #step 2: Create default group 
    default_group = db.GroupChat.find_one({"group_id": "group001"})

    if not default_group:
        new_group = {
            "group_id" : "group001",
            "group_name" : "Report Daily",
            "owner_id" : owner_id,
            "members" : all_user_ids
        }
        result = db.GroupChat.insert_one(new_group)
        group_object_id = result.inserted_id
        print(f"Đã tạo GroupChat mặc định. _id:{group_object_id}")
    else:
        group_object_id = default_group["_id"]
        print(f"Nhóm mặc định đã có sẵn. _id: {group_object_id}")
    
    #step 3: update all old report add field group_id
    update_result = db.Report.update_many(
        {"group_id":{"$exists": False}},
        {"$set":{"group_id": group_object_id}}
    )

    print(f"Đã cập nhật {update_result.modified_count} báo cáo (Report) cũ!")
    print("Quá trình đồng bộ hoàn tất. Database đã chuẩn Validate!")
if __name__ == "__main__":
    migrate_legacy_data()