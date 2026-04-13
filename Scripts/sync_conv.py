import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Database.MongoDB import reports_collection
from Utils.Embedding import sync_one_report



reports = reports_collection.find({})
for r in reports:
    sync_one_report(r)
print("Đã đồng bộ xong dữ liệu chuẩn lên Pinecone!")