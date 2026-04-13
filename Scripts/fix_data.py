import sys
import os
from bson import ObjectId

# Bắt buộc: Đưa đường dẫn thư mục gốc vào hệ thống trước khi import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Database.MongoDB import reports_collection, users_collection
from Utils.Embedding import sync_one_report

def fix_database_issues():
    print("🚀 BẮT ĐẦU CHẠY SCRIPT FIX DATA...")
    
    # Khai báo các ID
    old_user_id_str = "68db8148dbfaa86f5b2992b8"
    new_user_id_str = "69dc994f03bf44666d27524f"
    friend_to_add_str = "68db7e22dbfaa86f5b2992b1"

    # Ép kiểu sang ObjectId của MongoDB
    old_user_id = ObjectId(old_user_id_str)
    new_user_id = ObjectId(new_user_id_str)
    friend_to_add = ObjectId(friend_to_add_str)

    # ==========================================
    # TASK 1: CHUYỂN CHỦ SỞ HỮU REPORT
    # ==========================================
    print("\n--- 1. CẬP NHẬT REPORT & ĐỒNG BỘ PINECONE ---")
    
    # Tìm tất cả report của user cũ
    reports_to_update = list(reports_collection.find({"user_id": old_user_id}))
    
    if not reports_to_update:
        print(f"⚠️ Không tìm thấy báo cáo nào của user {old_user_id_str}.")
    else:
        print(f"📦 Tìm thấy {len(reports_to_update)} báo cáo cần chuyển đổi.")
        for r in reports_to_update:
            # 1. Update trong MongoDB
            reports_collection.update_one(
                {"_id": r["_id"]},
                {"$set": {"user_id": new_user_id}}
            )
            print(f"✅ Đã đổi user_id trong Mongo cho report {r['_id']}")
            
            # 2. Cập nhật object r hiện tại và đồng bộ lại Pinecone
            r["user_id"] = new_user_id
            
            # Lấy username mới để Pinecone lưu metadata user_name cho chuẩn
            new_user = users_collection.find_one({"_id": new_user_id})
            if new_user:
                r["user_name"] = new_user.get("username", "Unknown")
                
            sync_one_report(r)
        print("🎉 Hoàn tất cập nhật Report!")

    # ==========================================
    # TASK 2: VÁ LỖI DANH SÁCH BẠN BÈ
    # ==========================================
    print("\n--- 2. CẬP NHẬT DANH SÁCH BẠN BÈ ---")
    
    # Dùng $addToSet để thêm ID bạn bè. 
    # ($addToSet cực an toàn: nếu đã có rồi nó sẽ bỏ qua, chưa có nó mới thêm vào)
    result = users_collection.update_one(
        {"_id": new_user_id},
        {"$addToSet": {"friends": friend_to_add}}
    )
    
    if result.modified_count > 0:
        print(f"✅ Đã thêm {friend_to_add_str} vào danh sách bạn bè của {new_user_id_str}.")
    else:
        print(f"⚠️ Không có thay đổi nào (Người dùng không tồn tại hoặc đã là bạn bè từ trước).")

if __name__ == "__main__":
    fix_database_issues()