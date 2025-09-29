from anyio import ConnectionFailed
from pymongo import MongoClient

# kết nôi với MongoDB
MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB_NAME = "AgentZalo"

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
     # test kết nối
    client.admin.command('ping')
    print("Kết nối MongoDB thành công")
    
    db = client[MONGO_DB_NAME]
    reports_collection = db["Report"]
    users_collection = db["Users"]
    
except ConnectionFailed :
    print(f"Kết nối MongoDB thất bại")
    client = None
    db = None
    reports_collection = None   
    users_collection = None

#dùng để thao tác với collection trong DB
def get_mongo_collection(collection_name: str):
    """
    Hàm này để lấy collection trong DB.
    Ví dụ: reports = get_mongo_collection("Report")
    """
    if db is None:
        raise ConnectionFailed("Không thể kết nối đến MongoDB")
    return db[collection_name]
