# File: Utils/Agent.py

import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from Config.Model import generate_gemini_response
from Utils.Logger import AgentLogger
from Utils.Tools import Tools
from Utils.MCP_Client import mcp_client

ADVISOR_SYSTEM_PROMPT = """
Bạn là một TƯ VẤN VIÊN THÔNG MINH và THÂN THIỆN, hỗ trợ quản lý và tra cứu báo cáo công việc.
Bạn đang trò chuyện với người dùng tên là {username}. Hãy xưng hô thân thiện với họ.
"""

class ConversationMemory:
    def __init__(self, max_history: int = 10):
        self.messages: List[Dict] = []
        self.max_history = max_history
        self.action_context: Dict[str, Any] = {}
    
    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content, "timestamp": datetime.now().isoformat()})
        self._trim_history()
    
    def _trim_history(self):
        if len(self.messages) > self.max_history * 2: 
            self.messages = self.messages[-(self.max_history * 2):]
    
    def get_context_string(self) -> str:
        if not self.messages: return "Chưa có cuộc trò chuyện nào."
        return "\n".join([f"{'Người dùng' if msg['role'] == 'user' else 'Tư vấn viên'}: {msg['content']}" for msg in self.messages[-6:]])
    
    def clear(self):
        self.messages = []
        self.clear_action_context()
    
    def clear_action_context(self): 
        self.action_context = {}
    
    def get_summary(self) -> str:
        if not self.messages: return "Chưa có cuộc trò chuyện nào."
        user_messages = [m['content'] for m in self.messages if m['role'] == 'user']
        return f"Đã trao đổi {len(self.messages)} tin nhắn về: {', '.join(user_messages[:3])}"


class ConversationalAgent:
    def __init__(self):
        self.logger = AgentLogger()
        self.sessions: Dict[str, ConversationMemory] = {}
        self.tool_schemas = {
            "create_report": {
                "required": ["date", "yesterday", "today"],
                "questions": {
                    "date": "Chắc chắn rồi ạ! Anh muốn tạo báo cáo cho ngày nào thế?",
                    "yesterday": "Okie. Nội dung công việc anh đã làm hôm qua là gì?",
                    "today": "Và cuối cùng, nội dung công việc hôm nay của anh là gì?"
                }
            },
            "update_report": {
                "required": ["date", "update_request"],
                "questions": {
                    "date": "Được rồi ạ! Anh muốn cập nhật báo cáo ngày nào?",
                    "update_request": "Anh muốn cập nhật gì cho báo cáo này? (Ví dụ: thêm task mới, sửa nội dung hôm qua/hôm nay, đổi ngày...)"
                }
            }
        }

    def get_or_create_session(self, session_id: str) -> ConversationMemory:
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationMemory(max_history=10)
        return self.sessions[session_id]

    def clear_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def _get_missing_param(self, action: Optional[str], memory: ConversationMemory) -> Optional[str]:
        """Xác định tham số còn thiếu cho một action."""
        if action in self.tool_schemas:
            required = self.tool_schemas[action].get('required', [])
            payload = memory.action_context.get('update_payload' if action == 'update_report' else 'create_payload', {})
            missing = [p for p in required if p not in payload or not payload[p]]
            return missing[0] if missing else None
        return None
        
    def analyze_intent_and_entities(
        self, user_query: str, username: str,
        current_action: Optional[str] = None, missing_param: Optional[str] = None
    ) -> dict:
        """
        🎯 Phân tích intent CÓ NHẬN THỨC BỐI CẢNH (Stateful) - FIXED VERSION
        
        QUAN TRỌNG: 
        - Nếu đang có current_action và missing_param → ƯU TIÊN trích xuất thông tin cho missing_param
        - CHỈ phân tích intent mới khi KHÔNG có context
        """
        
        # 🔴 CRITICAL: Nếu đang trong quy trình, BUỘC phải là provide_info trừ khi user muốn hủy
        if current_action and missing_param:
            # Kiểm tra xem user có muốn hủy không
            cancel_keywords = ['hủy', 'thôi', 'dừng', 'cancel', 'không', 'bỏ']
            if any(keyword in user_query.lower() for keyword in cancel_keywords):
                return {"intent": "cancel_action", "entities": {}}
            
            # Xác định payload key
            payload_key = "update_payload" if current_action == "update_report" else "create_payload"
            
            # Trích xuất thông tin TRỰC TIẾP cho missing_param
            context_prompt = f"""
🎯 NHIỆM VỤ CHÍNH: Trích xuất TẤT CẢ thông tin từ câu trả lời của người dùng.

Bối cảnh:
- Đang thực hiện: {current_action}
- Đang chờ thông tin chính: {missing_param}
- Câu trả lời: "{user_query}"

⚠️ QUY TẮC QUAN TRỌNG:
1. Intent BUỘC PHẢI là "provide_info" (trừ khi user muốn hủy)
2. **TRÍCH XUẤT TẤT CẢ thông tin có trong câu, KHÔNG CHỈ {missing_param}**
3. Nếu user cung cấp NHIỀU thông tin cùng lúc → trích xuất HẾT TẤT CẢ
4. Nhận diện các từ khóa: "yesterday"/"hôm qua", "today"/"hôm nay", ngày tháng

Ví dụ quan trọng:
- Missing: "yesterday", User: "hôm qua tôi làm A, hôm nay tôi làm B" 
  → {{"intent": "provide_info", "entities": {{"create_payload": {{"yesterday": "làm A", "today": "làm B"}}}}}}
  ⚠️ PHẢI LẤY CẢ HAI, không chỉ yesterday!
  
- Missing: "yesterday", User: "yesterday làm docs và today làm code"
  → {{"intent": "provide_info", "entities": {{"create_payload": {{"yesterday": "làm docs", "today": "làm code"}}}}}}

- Missing: "update_request", User: "yesterday đi ăn" 
  → {{"intent": "provide_info", "entities": {{"update_payload": {{"update_request": "sửa yesterday thành 'đi ăn'"}}}}}}
  
- Missing: "today", User: "hôm nay đi họp và code"
  → {{"intent": "provide_info", "entities": {{"create_payload": {{"today": "đi họp và code"}}}}}}

Chỉ trả về JSON với format:
{{
    "intent": "provide_info",
    "entities": {{
        "{payload_key}": {{
            // Trích xuất TẤT CẢ fields có trong câu, không chỉ {missing_param}
        }}
    }}
}}
"""
        else:
            # Phân tích intent mới (không có context)
            context_prompt = f"""
🎯 NHIỆM VỤ: Phân tích yêu cầu MỚI của người dùng '{username}'.

Câu hỏi: "{user_query}"

Xác định intent:
- `create_report`: Tạo báo cáo mới (từ khóa: tạo, create, viết report mới)
- `update_report`: Sửa/cập nhật báo cáo đã có (từ khóa: sửa, update, cập nhật, thay đổi, chỉnh)
- `search_report`: Tìm kiếm (từ khóa: tìm, search, xem, báo cáo nào)
- `chitchat`: Trò chuyện thường

Trích xuất entities tương ứng:
- Với CREATE: {{"create_payload": {{"date": "...", "yesterday": "...", "today": "..."}}}}
- Với UPDATE: {{"update_payload": {{"date": "...", "update_request": "..."}}}}

Ví dụ:
- "Tạo report hôm nay" → {{"intent": "create_report", "entities": {{"create_payload": {{"date": "hôm nay"}}}}}}
- "Cập nhật báo cáo ngày 15/10" → {{"intent": "update_report", "entities": {{"update_payload": {{"date": "15/10"}}}}}}
- "Sửa report hôm qua, thêm task X" → {{"intent": "update_report", "entities": {{"update_payload": {{"date": "hôm qua", "update_request": "thêm task X"}}}}}}

Chỉ trả về JSON.
"""

        response = generate_gemini_response(question=user_query, system_prompt=context_prompt)
        try:
            clean_response = response.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_response)
            
            # 🛡️ SAFETY: Đảm bảo intent luôn là provide_info nếu đang có context
            if current_action and missing_param and parsed.get("intent") not in ["cancel_action"]:
                parsed["intent"] = "provide_info"
            
            return parsed
        except Exception as e:
            self.logger.log("PARSE_ERROR", f"Lỗi parse JSON: {e} | Response: {response}")
            # Fallback an toàn
            if missing_param:
                payload_key = "update_payload" if current_action == "update_report" else "create_payload"
                return {"intent": "provide_info", "entities": {payload_key: {missing_param: user_query}}}
            return {"intent": "chitchat", "entities": {}}
            
    def _normalize_date(self, date_str: str) -> Optional[str]:
        if not date_str: return None
        try:
            if 'hôm nay' in date_str.lower(): return datetime.now().strftime("%Y-%m-%d")
            if 'hôm qua' in date_str.lower(): return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            day, month, *year_parts = map(int, re.split(r'[/.-]', date_str))
            year = year_parts[0] if year_parts else datetime.now().year
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            self.logger.log("DATE_NORM_ERROR", f"Không chuẩn hóa được ngày: {date_str}")
            return None

    def _handle_create_report(self, username: str, memory: ConversationMemory) -> dict:
        """✅ Xử lý quy trình tạo báo cáo (Stateful)."""
        missing_param = self._get_missing_param("create_report", memory)
        
        if not missing_param:
            payload = memory.action_context.get("create_payload", {})
            
            # Validate và chuẩn hóa ngày
            date_to_normalize = payload.get("date")
            normalized_date = self._normalize_date(date_to_normalize)
            if not normalized_date:
                memory.action_context.get("create_payload", {}).pop("date", None)
                return {"answer": f"Ngày '{date_to_normalize}' không hợp lệ. Anh vui lòng cung cấp lại ngày báo cáo nhé."}
            
            payload["date"] = normalized_date
            
            try:
                mcp_msg = f"Thực hiện 'create_report' cho '{username}' với dữ liệu: {json.dumps(payload)}"
                res = mcp_client.ask_mcp(username=username, message=mcp_msg)
                answer = "✅ Xong! Báo cáo của anh đã được tạo. Cần em giúp gì thêm không ạ?" if res.get("success") else f"❌ Lỗi: {res.get('error', 'Không rõ')}"
            except Exception as e:
                self.logger.log("CREATE_ERROR", f"Lỗi gọi MCP: {e}")
                answer = f"❌ Lỗi nghiêm trọng khi thực thi: {e}"
            
            memory.clear_action_context()
            return {"answer": answer}
        else:
            question = self.tool_schemas["create_report"]["questions"].get(missing_param)
            return {"answer": question}

    def _handle_update_report(self, username: str, memory: ConversationMemory) -> dict:
        """🔄 Xử lý quy trình cập nhật báo cáo (Stateful)."""
        missing_param = self._get_missing_param("update_report", memory)
        
        if not missing_param:
            payload = memory.action_context.get("update_payload", {})
            
            # Validate và chuẩn hóa ngày
            date_to_normalize = payload.get("date")
            normalized_date = self._normalize_date(date_to_normalize)
            if not normalized_date:
                memory.action_context.get("update_payload", {}).pop("date", None)
                return {"answer": f"Ngày '{date_to_normalize}' không hợp lệ. Anh vui lòng cung cấp lại ngày cần cập nhật nhé."}
            
            payload["date"] = normalized_date
            
            try:
                # Gọi MCP với action update
                mcp_msg = f"Thực hiện 'update_report' cho '{username}' với dữ liệu: {json.dumps(payload)}"
                res = mcp_client.ask_mcp(username=username, message=mcp_msg)
                answer = "✅ Đã cập nhật báo cáo thành công! Cần em giúp gì thêm không ạ?" if res.get("success") else f"❌ Lỗi: {res.get('error', 'Không rõ')}"
            except Exception as e:
                self.logger.log("UPDATE_ERROR", f"Lỗi gọi MCP: {e}")
                answer = f"❌ Lỗi nghiêm trọng khi cập nhật: {e}"
            
            memory.clear_action_context()
            return {"answer": answer}
        else:
            question = self.tool_schemas["update_report"]["questions"].get(missing_param)
            return {"answer": question}

    def _handle_search_report(self, username: str, user_query: str, top_k: int) -> dict:
        """🔍 Xử lý tìm kiếm (Stateless)."""
        try:
            self.logger.log("SEARCH_START", f"Tìm kiếm cho '{username}': {user_query}")
            matches = Tools.search_reports(query=f"báo cáo của {username} về {user_query}", top_k=top_k)
            
            if not matches:
                return {"answer": f"Rất tiếc, em không tìm thấy báo cáo nào liên quan đến '{user_query}'."}
            
            self.logger.log("SEARCH_RESULT", f"Tìm thấy {len(matches)} kết quả")
            context = "\n\n---\n\n".join([m.get("metadata", {}).get("text", "") for m in matches])
            
            answer_prompt = f"""{ADVISOR_SYSTEM_PROMPT.format(username=username)}
Dựa vào các thông tin tìm được sau đây:
{context}
Hãy trả lời câu hỏi của người dùng một cách tự nhiên và thân thiện: "{user_query}"
"""
            final_answer = generate_gemini_response(question=user_query, system_prompt=answer_prompt)
            return {"answer": final_answer}
        except Exception as e:
            self.logger.log("SEARCH_ERROR", f"Lỗi tìm kiếm: {e}")
            return {"answer": f"❌ Có lỗi xảy ra khi tìm kiếm: {e}"}

    def run(self, user_query: str, username: str, session_id: str, top_k: int = 10) -> dict:
        memory = self.get_or_create_session(session_id)
        memory.add_message("user", user_query)

        current_action = memory.action_context.get("intent")
        missing_param = self._get_missing_param(current_action, memory)

        # 🔴 DEBUG LOG
        print(f"🔍 BEFORE ANALYSIS:")
        print(f"   - current_action: {current_action}")
        print(f"   - missing_param: {missing_param}")
        print(f"   - action_context: {memory.action_context}")

        analysis = self.analyze_intent_and_entities(user_query, username, current_action, missing_param)
        intent = analysis.get("intent", "chitchat")
        entities = analysis.get("entities", {})
        
        self.logger.log("INTENT_ANALYSIS", f"Intent: {intent} | Entities: {entities} | Current Action: {current_action}")
        print(f"🎯 Intent: {intent} | Entities: {entities} | Current Action: {current_action}")

        if intent == "cancel_action":
            memory.clear_action_context()
            final_result = {"answer": "Dạ vâng, em đã hủy thao tác. Anh cần em giúp gì khác không ạ?"}
        else:
            # Cập nhật context với key phù hợp
            if "create_payload" in entities:
                memory.action_context.setdefault("create_payload", {}).update(entities["create_payload"])
            if "update_payload" in entities:
                memory.action_context.setdefault("update_payload", {}).update(entities["update_payload"])

            # Bắt đầu action mới nếu chưa có
            if not current_action and intent in self.tool_schemas:
                memory.action_context["intent"] = intent
                current_action = intent
            
            # 🔴 DEBUG LOG
            print(f"🔍 AFTER UPDATE:")
            print(f"   - current_action: {current_action}")
            print(f"   - action_context: {memory.action_context}")

            # Router chính
            if current_action == "create_report":
                final_result = self._handle_create_report(username, memory)
            elif current_action == "update_report":
                final_result = self._handle_update_report(username, memory)
            elif intent == "search_report":
                final_result = self._handle_search_report(username, user_query, top_k)
            else:
                final_result = {"answer": generate_gemini_response(
                    question=user_query,
                    system_prompt=f"{ADVISOR_SYSTEM_PROMPT.format(username=username)}\n{memory.get_context_string()}"
                )}

        final_result["logs"] = self.logger.get_logs()
        memory.add_message("assistant", final_result["answer"])
        final_result["session_info"] = {
            "session_id": session_id,
            "message_count": len(memory.messages),
            "summary": memory.get_summary()
        }
        return final_result

conversational_agent = ConversationalAgent()