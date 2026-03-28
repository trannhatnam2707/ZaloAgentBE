# Script_Update_Users.py
from pymongo import MongoClient
from Utils.String_utils import remove_vietnamese_accents

client = MongoClient("mongodb://localhost:27017/")
db = client["AgentZalo"]

users = db.Users.find({"username_unsigned": {"$exists": False}})
for user in users:
    unsigned_name = remove_vietnamese_accents(user.get("username", ""))
    db.Users.update_one(
        {"_id": user["_id"]},
        {"$set": {"username_unsigned": unsigned_name}}
    )
print("Đã cập nhật xong tên không dấu cho các User cũ!")