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
    # ... (Nội dung lớp này giữ nguyên, không thay đổi)
    def __init__(self, max_history: int = 10):
        self.messages: List[Dict] = []
        self.max_history = max_history
        self.action_context: Dict[str, Any] = {}
    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content, "timestamp": datetime.now().isoformat()})
        self._trim_history()
    def _trim_history(self):
        if len(self.messages) > self.max_history * 2: self.messages = self.messages[-(self.max_history * 2):]
    def get_context_string(self) -> str:
        if not self.messages: return "Chưa có cuộc trò chuyện nào."
        return "\n".join([f"{'Người dùng' if msg['role'] == 'user' else 'Tư vấn viên'}: {msg['content']}" for msg in self.messages[-6:]])
    def clear(self):
        self.messages = []
        self.clear_action_context()
    def clear_action_context(self): self.action_context = {}
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
            }
            # Search không cần schema ở đây vì nó là tác vụ 1 bước
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
        if action == "create_report":
            required = self.tool_schemas['create_report'].get('required', [])
            # Lấy các tham số đã có trong context
            payload = memory.action_context.get('create_payload', {})
            missing = [p for p in required if p not in payload]
            return missing[0] if missing else None
        return None
        
    def analyze_intent_and_entities(
        self, user_query: str, username: str,
        current_action: Optional[str] = None, missing_param: Optional[str] = None
    ) -> dict:
        """
        🎯 Phân tích intent CÓ NHẬN THỨC BỐI CẢNH (Stateful)
        """
        context_prompt = ""
        # Nếu đang trong một quy trình và chờ tham số, ưu tiên trích xuất tham số đó
        if current_action and missing_param:
            context_prompt = f"""Bối cảnh: Agent đang thực hiện quy trình '{current_action}' và đang chờ người dùng cung cấp thông tin cho tham số '{missing_param}'.
Nhiệm vụ chính: Phân tích câu trả lời của người dùng "{user_query}" để trích xuất giá trị cho tham số '{missing_param}'.
⚠️ QUAN TRỌNG: Nếu câu trả lời có NHIỀU thông tin (ví dụ: cả yesterday VÀ today), hãy trích xuất TẤT CẢ vào create_payload.
Nếu người dùng trả lời không liên quan hoặc muốn hủy, hãy xác định intent phù hợp.
"""
        else:
            context_prompt = f"Nhiệm vụ: Phân tích yêu cầu mới của người dùng '{username}' là \"{user_query}\"."

        prompt = f"""
        {context_prompt}
        1. **Intent**: Xác định một trong các intent: `create_report`, `search_report`, `provide_info`, `cancel_action`, `chitchat`.
           - Nếu người dùng cung cấp thông tin cho tham số đang thiếu, intent là `provide_info`.
           - Nếu người dùng muốn dừng, hủy, thôi -> intent là `cancel_action`.
           
        2. **Entities**: Trích xuất thông tin. Key BẮT BUỘC là `create_payload`.
           - ⚠️ QUAN TRỌNG: Phải trích xuất TẤT CẢ thông tin có trong câu. Nếu câu có cả "yesterday" và "today", phải trả về CẢ HAI.
           - Ví dụ: "hôm qua tôi đi đà nẵng, hôm nay tôi đi hội an" 
             → {{"create_payload": {{"yesterday": "đi đà nẵng", "today": "đi hội an"}}}}
           - Ví dụ: nếu `missing_param` là 'yesterday' và người dùng nói "hôm qua tôi đi ăn cưới"
             → {{"create_payload": {{"yesterday": "đi ăn cưới"}}}}
           - Ví dụ: nếu `missing_param` là 'date' và người dùng nói "ngày 20/10"
             → {{"create_payload": {{"date": "20/10"}}}}

        Chỉ trả về JSON.
        """
        response = generate_gemini_response(question=user_query, system_prompt=prompt)
        try:
            clean_response = response.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_response)
        except Exception as e:
            self.logger.log("PARSE_ERROR", f"Lỗi parse JSON: {e} | Response: {response}")
            # Fallback an toàn: Nếu đang chờ tham số, giả định người dùng đã cung cấp nó
            if missing_param:
                return {"intent": "provide_info", "entities": {"create_payload": {missing_param: user_query}}}
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
            # Đã đủ thông tin, thực thi
            payload = memory.action_context.get("create_payload", {})
            
            # Validate và chuẩn hóa ngày
            date_to_normalize = payload.get("date")
            normalized_date = self._normalize_date(date_to_normalize)
            if not normalized_date:
                memory.action_context.get("create_payload", {}).pop("date", None) # Xóa ngày không hợp lệ
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
            # Vẫn thiếu thông tin, hỏi câu hỏi tiếp theo
            question = self.tool_schemas["create_report"]["questions"].get(missing_param)
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

        analysis = self.analyze_intent_and_entities(user_query, username, current_action, missing_param)
        intent = analysis.get("intent", "chitchat")
        entities = analysis.get("entities", {})
        
        self.logger.log("INTENT_ANALYSIS", f"Intent: {intent} | Entities: {entities} | Current Action: {current_action}")
        print(f"🎯 Intent: {intent} | Entities: {entities} | Current Action: {current_action}")

        if intent == "cancel_action":
            memory.clear_action_context()
            final_result = {"answer": "Dạ vâng, em đã hủy thao tác. Anh cần em giúp gì khác không ạ?"}
        else:
            # Cập nhật context
            if "create_payload" in entities:
                memory.action_context.setdefault("create_payload", {}).update(entities["create_payload"])

            # Bắt đầu action mới nếu chưa có
            if not current_action and intent in self.tool_schemas:
                memory.action_context["intent"] = intent
                current_action = intent

            # Router chính
            if current_action == "create_report":
                final_result = self._handle_create_report(username, memory)
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