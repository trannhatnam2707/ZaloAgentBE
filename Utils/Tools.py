# File: Utils/Tools.py (RAG)

from Database.Pinecone import search_pinecone
from Utils.Embedding import get_embedding

class Tools:
    @staticmethod
    def search_reports(query, top_k=10, date_filter=None):
        """
        Tìm kiếm báo cáo, có thể lọc chính xác theo ngày.
        
        Args:
            query (str): Câu hỏi tìm kiếm.
            top_k (int): Số kết quả.
            date_filter (str, optional): Ngày cần lọc, format "YYYY-MM-DD".
        
        Returns:
            list: Danh sách các báo cáo tìm thấy.
        """
        try:
            print(f"Tool search_reports received date_filter: {date_filter}")
            embedding = get_embedding(query)
            
            pinecone_filter = None
            if date_filter:
                # Tạo filter cho Pinecone. Metadata field phải là "date".
                pinecone_filter = {"date": {"$eq": date_filter}}
            
            # Gọi hàm search_pinecone đã được cập nhật
            results = search_pinecone(embedding, top_k, filter=pinecone_filter)
            
            matches = results.get('matches', [])
            return [m for m in matches if m.get('score', 0) >= 0.4]
        except Exception as e:
            print(f"Error in search_reports: {e}")
            return []