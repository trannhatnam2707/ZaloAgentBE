# AGENTZALO Backend

Backend API for a chat and daily work-reporting system, integrated with:
- FastAPI (REST API)
- MongoDB (users, conversations, messages, reports)
- Pinecone (vector search for reports)
- Gemini (`google-genai`) for embeddings and tool-calling agent workflows

---

## 1) System Goals

The system supports two primary use-case groups:

1. **Chat & daily reporting**
   - Users send messages to chat conversations.
   - If a message starts with `report` or `/report`, the system parses the content and creates a report automatically.
   - New reports are synchronized to Pinecone for semantic retrieval.

2. **Agent-powered Q&A**
   - The `/ask` endpoint invokes an Agent powered by Gemini + tool-calling.
   - The Agent can call tools to create, update, delete, and search reports.

---

## 2) Architecture Overview

### Core layers

- `Main.py`: initializes FastAPI and registers routers.
- `Router/`: HTTP endpoint definitions.
- `Controller/`: request/response orchestration.
- `Services/`: core business logic (user, message, report, ask, etc.).
- `Database/`: MongoDB and Pinecone integration.
- `Config/ModelAI.py`: Gemini integration (embedding + content generation).
- `MCP_Client/Agent.py`: conversational Agent with per-session memory.
- `MCP_Server/Agent_Tools.py`: tool registry available to Gemini.

### Main data stores

- MongoDB collections:
  - `Users`
  - `Conversations`
  - `Messages`
  - `Report`
- Pinecone index:
  - key metadata fields: `report_id`, `user_id`, `user_name`, `conversation_id`, `date`, `text`

---

## 3) Environment Requirements

- Python 3.11+ (recommended)
- MongoDB running locally or remotely
- Valid Pinecone API key
- Valid Google API key (Gemini)

---

## 4) Setup & Build

### Step 1: Create virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 2: Install dependencies

```powershell
pip install -r requirements.txt
```

### Step 3: Create `.env` file

Create `.env` in the project root:

```env
GOOGLE_API_KEY=your_google_api_key
PINECONE_API_KEY_V2=your_pinecone_api_key
PINECONE_INDEX=agentzalo
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRES_MINUTES=60
REFRESH_TOKEN_EXPIRES_DAY=7
```

> Notes:
> - Never commit `.env` to git.
> - If the Google key is revoked/leaked, embedding will fail and reports will not sync to Pinecone.

### Step 4: Run API server

```powershell
uvicorn Main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI:
- `http://127.0.0.1:8000/docs`

---

## 5) Main APIs

- `POST /users/register`, `POST /users/login`, `POST /users/refresh-token`, `POST /users/logout`
- `GET /users/search`, `GET /users/{username}`
- `POST /conservations`, `GET /conservations`
- `POST /messages`, `GET /messages/{conversation_id}`
- `POST /reports`, `GET /reports`, `PUT /reports/{report_id}`, `DELETE /reports/{id}`
- `POST /ask`

---

## 6) Runtime Flow: Standard Mode (without Agent)

### 6.1 Standard chat message flow

1. Client calls `POST /messages`.
2. `MessageService.send_message()` validates:
   - conversation exists
   - current user belongs to `members`
3. For normal messages: save to `Messages`, update `Conversations.updated_at`, return response.

### 6.2 Report command via text

When `content` starts with `report` or `/report`:

1. `MessageService._handle_report_command()` is triggered.
2. It parses `date`, `yesterday`, `today` from text.
3. Calls `create_report()` in `Report_service`.
4. Report is saved to MongoDB.
5. `sync_one_report()` (in `Utils/Embedding.py`) creates embeddings and upserts vectors to Pinecone.
6. A `report_card` message is created for the chat UI.

---

## 7) Runtime Flow: MCP / Agent Mode

Main endpoint: `POST /ask`

### 7.1 End-to-end flow

1. `Ask_router` receives `{question, username, session_id, top_k}`.
2. `Ask_service.ask_agent()` calls `conversational_agent.run(...)`.
3. `MCP_Client/Agent.py`:
   - creates/gets memory by `session_id`
   - creates a Gemini chat with `system_instruction`
   - injects `GEMINI_TOOLS` from `MCP_Server/Agent_Tools.py`
4. Gemini decides to:
   - reply directly, or
   - call one or more tools
5. Tools execute on MongoDB/Pinecone:
   - `tool_create_report`
   - `tool_update_report`
   - `tool_delete_report`
   - `tool_search_reports`
6. Agent returns `answer` + `logs` to client.

### 7.2 When to use Agent mode

- Natural-language requests requiring interpretation (e.g., “find Nam’s reports from last week”).
- Multi-step operations (search -> confirm -> update/delete).

### 7.3 When to use standard APIs

- Frontend already has structured forms (direct create/update report).
- You need deterministic CRUD behavior with predictable validation paths.

---

## 8) Quick Verification Checklist

1. Register/login and obtain token.
2. Create a conversation.
3. Call `POST /messages` with:
   - normal text -> verify message is stored in MongoDB.
   - `report ...` -> verify:
     - new document in `Report`
     - successful Pinecone sync logs in terminal
4. Call `POST /ask` with a report-related query to validate Agent + tools.

---

## 9) Common Issues

1. **Report does not sync to Pinecone**
   - Typical cause: invalid/revoked `GOOGLE_API_KEY` -> embedding fails (often 403).
   - Fix: replace key, restart server, test again.

2. **Package import works globally but not in venv**
   - Always use `.\.venv\Scripts\python` and `.\.venv\Scripts\pip`.
   - Avoid installing dependencies with global Python for this project.

3. **`.env` disappears locally after `git rm --cached .env`**
   - Correct command only untracks from git index; local file should remain.
   - If missing, recreate `.env` from the template in section 4.

---

## 10) Security & Operations

- Never commit `.env` or API keys.
- Rotate credentials periodically (Google/Pinecone).
- Keep production logging at an appropriate level.
- Add automated tests for:
  - `/messages` report-command handling
  - `create_report` + `sync_one_report`
  - `/ask` tool-calling flow

