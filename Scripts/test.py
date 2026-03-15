# check_pinecone.py
from Database.MongoDB import get_mongo_collection
from Utils.Embedding import sync_one_report

reports_collection = get_mongo_collection("Report")

# Tìm report ngày 20/8
report_20_8 = reports_collection.find_one({"date": {"$regex": "2025-08-20|2024-08-20|20/08"}})
    
if report_20_8:
    print(f"Tìm thấy report ngày 20/8 trong MongoDB:")
    print(f"   - ID: {report_20_8['_id']}")
    print(f"   - Date: {report_20_8.get('date')}")
    print(f"   - Yesterday: {report_20_8.get('yesterday', '')[:50]}...")
    print(f"   - Today: {report_20_8.get('today', '')[:50]}...")
    
    # Sync lại vào Pinecone
    print("\n🔄 Đang đồng bộ lại vào Pinecone...")
    sync_one_report(report_20_8)
    print("✅ Đồng bộ thành công!")
else:
    print("❌ KHÔNG tìm thấy report ngày 20/8 trong MongoDB")
    print("Kiểm tra lại format ngày trong DB:")
    
    # Liệt kê một số report gần đó
    nearby_reports = reports_collection.find().sort("date", -1).limit(5)
    for r in nearby_reports:
        print(f"  - {r.get('date')} | {r.get('user_id')}")