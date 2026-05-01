from pymongo import MongoClient
from bson import ObjectId

client = MongoClient("mongodb://localhost:27017/")
db = client["AgentZalo"]

users = db.Users.find()

for user in users:
    official_friends = [] 
    pending_requests = []   

    if "friends" in user and isinstance(user["friends"], list):
        for item in user["friends"]:
            if isinstance(item, dict) and item.get("status") == "accepted":
                official_friends.append(item["user_id"])
            elif isinstance(item, dict) and item.get("status") == "pending":
                pending_requests.append(item)
            elif isinstance(item, ObjectId):
                official_friends.append(item)

    db.Users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "friends": official_friends,
                "friend_requests": pending_requests
            }
        }
    )

