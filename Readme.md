# AGENTZALO Backend

Backend API cho hệ thống chat + báo cáo công việc, tích hợp:
- FastAPI (REST API)
- MongoDB (lưu người dùng, hội thoại, tin nhắn, report)
- Pinecone (vector search cho report)
- Gemini (`google-genai`) cho embedding và Agent hỏi đáp có tool-calling

---

## 1) Mục tiêu hệ thống

Hệ thống hỗ trợ 2 nhóm use case chính:

1. **Chat & báo cáo công việc hằng ngày**
   - Người dùng gửi tin nhắn vào phòng chat.
   - Nếu tin nhắn bắt đầu bằng `report` hoặc `/report`, hệ thống tự parse và tạo report.
   - Report mới được đồng bộ sang Pinecone để phục vụ tra cứu ngữ nghĩa.

2. **Hỏi đáp thông minh qua Agent**
   - Endpoint `/ask` gọi Agent dùng Gemini + tool-calling.
   - Agent có thể gọi các tool CRUD report và tìm kiếm report trong Pinecone.

---

## 2) Kiến trúc tổng quan

### Core layers

- `Main.py`: khởi tạo app FastAPI và đăng ký router.
- `Router/`: định nghĩa endpoint HTTP.
- `Controller/`: điều phối request/response.
- `Services/`: nghiệp vụ chính (user, message, report, ask...).
- `Database/`: kết nối MongoDB và Pinecone.
- `Config/ModelAI.py`: tích hợp Gemini (embedding + generate content).
- `MCP_Client/Agent.py`: Agent hội thoại giữ memory theo session.
- `MCP_Server/Agent_Tools.py`: danh sách tool cho Gemini gọi.

### Dữ liệu chính

- MongoDB collections:
  - `Users`
  - `Conversations`
  - `Messages`
  - `Report`
- Pinecone index:
  - metadata chính: `report_id`, `user_id`, `user_name`, `conversation_id`, `date`, `text`

---

## 3) Yêu cầu môi trường

- Python 3.11+ (khuyến nghị)
- MongoDB đang chạy local hoặc remote
- Pinecone API key hợp lệ
- Google API key hợp lệ (cho Gemini)

---

## 4) Cài đặt và build

### Bước 1: Tạo virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Bước 2: Cài dependencies

```powershell
pip install -r requirements.txt
```

### Bước 3: Tạo file `.env`

Tạo file `.env` tại root project với mẫu:

```env
GOOGLE_API_KEY=your_google_api_key
PINECONE_API_KEY_V2=your_pinecone_api_key
PINECONE_INDEX=agentzalo
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRES_MINUTES=60
REFRESH_TOKEN_EXPIRES_DAY=7
```

> Lưu ý:
> - Không commit `.env` lên git.
> - Nếu key Google bị thu hồi/leaked, embedding sẽ fail và report sẽ không sync được lên Pinecone.

### Bước 4: Chạy API server

```powershell
uvicorn Main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI:
- `http://127.0.0.1:8000/docs`

---

## 5) API chính

- `POST /users/register`, `POST /users/login`, `POST /users/refresh-token`, `POST /users/logout`
- `GET /users/search`, `GET /users/{username}`
- `POST /conservations`, `GET /conservations`
- `POST /messages`, `GET /messages/{conversation_id}`
- `POST /reports`, `GET /reports`, `PUT /reports/{report_id}`, `DELETE /reports/{id}`
- `POST /ask`

---

## 6) Luồng chạy khi dùng "thường" (không qua Agent)

### 6.1 Gửi tin nhắn chat thường

1. Client gọi `POST /messages`.
2. `MessageService.send_message()` kiểm tra:
   - conversation tồn tại
   - user thuộc `members`
3. Nếu là tin nhắn bình thường: lưu vào `Messages`, cập nhật `Conversations.updated_at`, trả response.

### 6.2 Gửi lệnh report bằng text

Khi `content` bắt đầu bằng `report` hoặc `/report`:

1. `MessageService._handle_report_command()` được gọi.
2. Parse `date`, `yesterday`, `today` từ text.
3. Gọi `create_report()` trong `Report_service`.
4. Report được lưu MongoDB.
5. `sync_one_report()` (trong `Utils/Embedding.py`) tạo embedding và upsert lên Pinecone.
6. Hệ thống tạo một `report_card` message để hiển thị trong chat.

---

## 7) Luồng chạy khi dùng MCP / Agent

Endpoint chính: `POST /ask`

### 7.1 Luồng tổng quát

1. `Ask_router` nhận request `{question, username, session_id, top_k}`.
2. `Ask_service.ask_agent()` gọi `conversational_agent.run(...)`.
3. `MCP_Client/Agent.py`:
   - tạo/lấy memory theo `session_id`
   - khởi tạo Gemini chat với `system_instruction`
   - nạp `GEMINI_TOOLS` từ `MCP_Server/Agent_Tools.py`
4. Gemini quyết định:
   - trả lời trực tiếp, hoặc
   - gọi tool phù hợp
5. Tool thao tác vào MongoDB/Pinecone:
   - `tool_create_report`
   - `tool_update_report`
   - `tool_delete_report`
   - `tool_search_reports`
6. Agent trả `answer` + `logs` về client.

### 7.2 Khi nào nên dùng Agent

- Câu lệnh ngôn ngữ tự nhiên cần suy luận (ví dụ: “tìm report của Nam tuần trước”).
- Tác vụ cần gọi nhiều bước liên tiếp (search -> xác nhận -> update/delete).

### 7.3 Khi nào nên dùng API thường

- Frontend đã có form dữ liệu rõ ràng (create/update report trực tiếp).
- Cần luồng CRUD đơn giản, deterministic, dễ kiểm soát.

---

## 8) Kiểm thử nhanh sau khi chạy

1. Đăng ký hoặc đăng nhập lấy token.
2. Tạo conversation.
3. Gọi `POST /messages` với nội dung:
   - text thường -> kiểm tra message lưu MongoDB.
   - `report ...` -> kiểm tra:
     - có record mới trong `Report`
     - terminal có log sync Pinecone thành công
4. Gọi `POST /ask` với câu hỏi tra cứu report để xác nhận Agent + tool hoạt động.

---

## 9) Sự cố thường gặp

1. **Report không sync Pinecone**
   - Nguyên nhân phổ biến: `GOOGLE_API_KEY` lỗi/leaked -> embedding trả lỗi 403.
   - Cách xử lý: thay key mới, restart server, thử lại.

2. **Import package không nhận trong venv**
   - Luôn dùng `.\.venv\Scripts\python` và `.\.venv\Scripts\pip`.
   - Tránh cài package bằng Python global.

3. **`.env` bị mất local sau khi `git rm --cached .env`**
   - Lệnh đúng chỉ bỏ khỏi git index, không nên xóa file local.
   - Nếu lỡ mất, tạo lại `.env` theo mẫu ở mục 4.

---

## 10) Bảo mật & vận hành

- Không commit `.env` hoặc API keys.
- Rotate key định kỳ (Google/Pinecone).
- Bật logging ở mức phù hợp khi production.
- Nên thêm test tự động cho các flow:
  - `/messages` với report command
  - `create_report` + `sync_one_report`
  - `/ask` với tool-calling.

