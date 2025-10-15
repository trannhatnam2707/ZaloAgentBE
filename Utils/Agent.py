# File: Utils/Agent.py
import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

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
        context_parts = [f"{'Người dùng' if msg['role'] == 'user' else 'Tư vấn viên'}: {msg['content']}" for msg in self.messages[-6:]]
        return "\n".join(context_parts)

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
                    "date": "Chắc chắn rồi ạ! Bạn muốn tạo báo cáo cho ngày nào thế?",
                    "yesterday": "Okie. Nội dung công việc bạn đã làm hôm qua là gì?",
                    "today": "Và cuối cùng, nội dung công việc hôm nay của bạn là gì?"
                }
            },
            "update_report": {
                "required": ["yesterday", "today"],
                "questions": {
                    "yesterday": "Bạn muốn cập nhật nội dung công việc hôm qua thành gì?",
                    "today": "Và nội dung công việc hôm nay cần cập nhật là gì?"
                }
            }
        }

    def get_or_create_session(self, session_id: str) -> ConversationMemory:
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationMemory(max_history=10)
        return self.sessions[session_id]

    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id].clear()
            return True
        return False

    def analyze_intent_and_entities(self, user_query: str, chat_history: str, username: str) -> dict:
        prompt = f"""
        Phân tích yêu cầu mới của người dùng '{username}' là "{user_query}" dựa trên lịch sử hội thoại.
        LỊCH SỬ: {chat_history}
        
        Trả về một JSON object DUY NHẤT với các trường:
        - "intent": (Bắt buộc) Một trong các giá trị: "create_report", "update_report", "search_report", "chitchat", "provide_info", "confirm_yes", "confirm_no", "cancel_action".
        - "entities": (Bắt buộc) Một JSON object chứa các thông tin được trích xuất. Ví dụ: {{"date": "hôm qua", "yesterday": "làm task A"}}. Nếu không có, trả về object rỗng {{}}.
        
        VÍ DỤ:
        - Yêu cầu: "cập nhật report hôm qua" -> {{"intent": "update_report", "entities": {{"date": "hôm qua"}}}}
        - Yêu cầu: "nội dung hôm qua là ở nhà" -> {{"intent": "provide_info", "entities": {{"yesterday": "ở nhà"}}}}
        - Yêu cầu: "thôi hủy đi" -> {{"intent": "cancel_action", "entities": {{}}}}
        """
        response = generate_gemini_response(question=user_query, system_prompt=prompt)
        try:
            clean = response.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except Exception:
            return {"intent": "search_report", "entities": {}, "reason": "Lỗi phân tích, mặc định tìm kiếm."}

    def handle_question(self, user_query: str, username: str, chat_history: str, top_k: int = 10) -> dict:
        matches = Tools.search_reports(f"Thông tin của {username}: {user_query}", top_k=top_k)
        context = "\n\n---\n\n".join([m.get("metadata", {}).get("text", "") for m in matches])
        answer_prompt = f"{ADVISOR_SYSTEM_PROMPT.format(username=username)}\nLịch sử:\n{chat_history}\nDữ liệu:\n{context}\nTrả lời câu hỏi: '{user_query}'"
        final_answer = generate_gemini_response(question=user_query, context=context, system_prompt=answer_prompt)
        return {"answer": final_answer, "logs": self.logger.get_logs()}

    def run(self, user_query: str, username: str, session_id: str, top_k: int = 10) -> dict:
        memory = self.get_or_create_session(session_id)
        memory.add_message("user", user_query)
        chat_history = memory.get_context_string()

        analysis = self.analyze_intent_and_entities(user_query, chat_history, username)
        intent = analysis.get("intent", "chitchat")
        entities = analysis.get("entities", {})
        print(f"🎯 Intent: {intent} | Entities: {entities}")

        # Xử lý HỦY BỎ trước tiên
        if intent == 'cancel_action':
            memory.clear_action_context()
            final_result = {"answer": "Dạ vâng, đã hủy thao tác. Bạn cần tôi giúp gì khác không ạ?"}
        else:
            # === LOGIC MỚI: Xử lý `entities` an toàn ===
            if entities and isinstance(entities, dict):
                memory.action_context.update(entities)
            
            current_action = memory.action_context.get("intent")
            if not current_action and intent in self.tool_schemas:
                current_action = intent
                memory.action_context["intent"] = current_action

            # === LOGIC CHO UPDATE_REPORT ===
            if current_action == 'update_report':
                final_result = self._handle_update_report_flow(username, intent, memory)
            # === Xử lý các action khác ===
            elif current_action in self.tool_schemas:
                final_result = self._handle_action_execution(username, memory)
            elif intent == "search_report":
                final_result = self.handle_question(user_query, username, chat_history, top_k)
            else: # chitchat
                final_result = {"answer": generate_gemini_response(question=user_query, system_prompt=f"{ADVISOR_SYSTEM_PROMPT.format(username=username)}\n{chat_history}")}

        final_result["logs"] = self.logger.get_logs()
        memory.add_message("assistant", final_result["answer"])
        final_result["session_info"] = {"session_id": session_id, "message_count": len(memory.messages), "summary": memory.get_summary()}
        return final_result

    def _handle_update_report_flow(self, username: str, intent: str, memory: ConversationMemory) -> dict:
        # Giai đoạn 1: Tìm và xác nhận report
        if 'report_id' not in memory.action_context:
            if 'found_report_for_confirmation' in memory.action_context:
                if intent == "confirm_yes":
                    confirmed_report = memory.action_context.pop('found_report_for_confirmation')
                    memory.action_context['report_id'] = confirmed_report['id']
                    return {"answer": self.tool_schemas['update_report']['questions']['yesterday']}
                else: # confirm_no hoặc hủy
                    memory.clear_action_context()
                    return {"answer": "Dạ vâng. Khi nào cần, bạn cứ gọi nhé."}
            else:
                if 'date' not in memory.action_context:
                    return {"answer": "Chắc chắn rồi ạ. Bạn muốn cập nhật báo cáo của ngày nào thế?"}
                else:
                    search_date_str = memory.action_context['date']
                    normalized_date = self._normalize_date(search_date_str)
                    if not normalized_date:
                        memory.action_context.pop('date', None)
                        return {"answer": "Xin lỗi, tôi chưa hiểu rõ ngày bạn cung cấp. Bạn có thể nói rõ hơn không, ví dụ: 'hôm qua' hoặc '17/10'?"}
                    else:
                        matches = Tools.search_reports(query=f"báo cáo của {username} ngày {normalized_date}", top_k=1, date_filter=normalized_date)
                        if matches:
                            report = matches[0]
                            memory.action_context['found_report_for_confirmation'] = {'id': report['id'], 'text': report['metadata']['text']}
                            return {"answer": f"Tôi tìm thấy báo cáo ngày {normalized_date}:\n\n> {report['metadata']['text']}\n\n**Đây có phải báo cáo bạn muốn cập nhật không ạ?**"}
                        else:
                            memory.clear_action_context()
                            return {"answer": f"Rất tiếc, tôi không tìm thấy báo cáo nào của bạn vào ngày {normalized_date}."}
        # Giai đoạn 2: Thu thập thông tin và thực thi
        else:
            return self._handle_action_execution(username, memory)

    def _handle_action_execution(self, username: str, memory: ConversationMemory) -> dict:
        current_action = memory.action_context.get("intent")
        schema = self.tool_schemas[current_action]
        
        required_params = schema["required"]
        if current_action == 'update_report':
            required_params = ['report_id'] + required_params
            
        missing_params = [p for p in required_params if p not in memory.action_context]
        
        if not missing_params:
            try:
                params = memory.action_context.copy()
                action = params.pop("intent")
                mcp_msg = f"Thực hiện '{action}' cho '{username}' với dữ liệu: {json.dumps(params)}"
                res = mcp_client.ask_mcp(username=username, message=mcp_msg)
                answer = "✅ Xong! Cần tôi giúp gì thêm không?" if res.get("success") else f"❌ Lỗi: {res.get('error', 'Không rõ')}"
                result = {"answer": answer, "mcp_result": res}
            except Exception as e:
                result = {"answer": f"❌ Lỗi nghiêm trọng khi gọi MCP: {e}"}
            memory.clear_action_context()
        else:
            next_param = missing_params[0]
            result = {"answer": schema["questions"].get(next_param, f"Bạn vui lòng cung cấp {next_param} nhé.")}
        return result

    def _normalize_date(self, date_str: str) -> str | None:
        try:
            if 'hôm nay' in date_str.lower(): return datetime.now().strftime("%Y-%m-%d")
            if 'hôm qua' in date_str.lower(): return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            day, month, *year = map(int, re.split(r'[/.-]', date_str))
            return datetime(year[0] if year else datetime.now().year, month, day).strftime("%Y-%m-%d")
        except Exception:
            return None

conversational_agent = ConversationalAgent()