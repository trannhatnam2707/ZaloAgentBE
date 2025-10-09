import requests
from typing import Optional

class MCPClient:
    """Client để gọi HTTP request đến MCP Server"""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
    
    def ask_mcp(self, username: str, message: str) -> dict:
        """
        Gọi endpoint /ask của MCP Server
        
        Args:
            username: Tên user
            message: Câu hỏi/yêu cầu từ user
            
        Returns:
            dict: Response từ MCP Server
        """
        try:
            url = f"{self.base_url}/ask"
            payload = {
                "username": username,
                "message": message
            }
            
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Lỗi khi gọi MCP Server: {e}")
            return {
                "success": False,
                "error": f"Không thể kết nối đến MCP Server: {str(e)}"
            }
        except Exception as e:
            print(f"❌ Lỗi không xác định: {e}")
            return {
                "success": False,
                "error": f"Lỗi: {str(e)}"
            }
    
    def health_check(self) -> bool:
        """Kiểm tra MCP Server có hoạt động không"""
        try:
            response = requests.get(f"{self.base_url}/docs", timeout=5)
            return response.status_code == 200
        except:
            return False


# Singleton instance
mcp_client = MCPClient()