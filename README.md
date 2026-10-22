> 更新 / Update: 本機持久化追蹤與部署操作見 [OBSERVABILITY.md](OBSERVABILITY.md)、[DEPLOYMENT.md](DEPLOYMENT.md)。啟動只載入 .env，程序環境變數優先；不再載入 .env.local。完整同一供應商設定須放在 .env。1.env 僅用於明確選擇的對照測試，所有憑證檔均不提交。 / Startup reads a complete provider profile from .env only.

# ClinicPilot AI

介面與固定回覆現採繁體中文／English 對照。 / The interface and fixed replies use paired Traditional Chinese and English.

維護、備份還原與排錯 / Maintenance, backup/restore and troubleshooting: [MAINTENANCE.md](MAINTENANCE.md).

完整需求與現況核對 / Full requirements and status review: [REQUIREMENTS_REVIEW.md](REQUIREMENTS_REVIEW.md).

A runnable clinic assistant take-home MVP: React workbench, FastAPI, SQLite, grounded catalog retrieval, conversational booking and a configurable LLM function-calling adapter.

## Quick start on Windows

Requirements: Python 3.10+ (tested with 3.13), Node.js 22.12+ and npm. Initial dependency installation needs internet.

1. Double-click `setup.cmd` (creates a project-local virtual environment, installs pinned dependencies, builds React).
2. Double-click `start.cmd`.
3. Open http://127.0.0.1:8000. Interactive API documentation: http://127.0.0.1:8000/docs.
4. Keep the server window open. Ctrl+C stops the server.

The first startup creates `runtime/clinic.db` and seeds all six supplied CSVs. Subsequent startups preserve bookings and conversation state. No separate database server is needed. Port 8000 must be free.

Default `AI_MODE=local` is an explicitly labelled deterministic demo: lexical retrieval plus bilingual intent/slot rules and templated grounded answers. It is not a live LLM. Both modes use the same REST booking tools and database.

## Manual setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --app-dir backend --host 127.0.0.1 --port 8000
```

On macOS/Linux use `python3`, `.venv/bin/python` and `npm` for the same commands. Run from the project root. For development, run the backend as above and `npm run dev` in `frontend/`; Vite proxies /api to port 8000.

The seed is insert-if-missing, not a migration system. To reset demo data, stop the server, back up and move `runtime/clinic.db` elsewhere, then restart. Do not reset during an interview if you want to demonstrate persistence.

## 真實 Claude 接入 / Live Claude integration

本機已驗證 Poe `claude-sonnet-5.5` 的 Chat Completions 工具呼叫、RAG、多輪預約及逐字稿摘要。結果與比較界線見 [LIVE_MODEL_REPORT.md](LIVE_MODEL_REPORT.md)。沒有密鑰的新安裝仍預設 local，不宣稱已連線。

Poe Claude Sonnet 5.5 has been tested with real tool calls, retrieval, booking and transcript summarization. New installations without credentials still default to local mode.

完整 DeepSeek 設定放在 .env：AI_MODE=llm、LLM_API_KEY=自己的密鑰、LLM_BASE_URL=https://api.deepseek.com、LLM_MODEL=deepseek-flash、LLM_API_STYLE=responses、LLM_TOOL_CHOICE=auto、LLM_STRICT_TOOLS=false、LLM_TIMEOUT_SECONDS=90。每項各佔一行。/ Put the complete matching provider profile in .env, one setting per line.

Poe/Sonnet 使用相應 Poe 密鑰，URL=https://api.poe.com/v1、model=claude-sonnet-5.5、style=chat_completions。程序環境變數優先於 .env；不再混入 .env.local。/ Use matching credentials when switching providers.

Poe 上此 Claude 模型實測不支援 Responses method，強制工具選擇也被上游拒絕，因此使用 auto，並由應用程式強制驗證必須收到正確工具呼叫。其他供應商可設定 `LLM_API_STYLE=responses` 或 `chat_completions`，及 `LLM_TOOL_CHOICE=forced`、`LLM_STRICT_TOOLS=true`；不要假設不同模型完全相容。

This Claude model rejected Responses and forced tool choice in live tests. Auto tool choice works; the host still rejects missing/invalid tool calls. Other providers can use Responses or Chat Completions with strict schemas and forced tools when supported.

LLM 模式每則新訊息都經模型辨識意圖，沒有就診流程的本機規則捷徑。模型將上下文問題改寫成檢索詞與目錄 ID；回答使用資料庫證據。預約成功或失敗的確認仍直接來自 REST 結果，避免寫入後又因生成失敗誤報。

Every new LLM-mode message uses model routing. Contextual queries are rewritten into search terms/IDs and grounded in database evidence. Saved/rejected booking confirmations remain authoritative REST results.

欄位齊全不等於允許提交：若明說「先不要提交」，系統保留草稿，直到明確確認；撤回已選日期、醫生或服務時會清除舊值。 / Complete fields do not override a request to wait. Held drafts require explicit confirmation; withdrawn selections are cleared.

額外邊界案例、發現的問題及修復證據： [EXTENDED_TEST_REPORT.md](EXTENDED_TEST_REPORT.md)。 / Additional edge cases, findings and fixes are documented in the extended test report.

模型失敗會顯示錯誤，不切回本機模板冒充真實模型。LLM 模式會把模擬病人、對話與必要目錄內容傳到供應商；不要提交或公開密鑰。

Provider failures are explicit, with no silent local fallback. LLM mode sends mock patient, conversation and relevant catalog context to the configured provider.

## 逐字稿摘要 / Transcript summary

在頁面下方開啟「逐字稿摘要」，貼上醫病文字對話，按「產生摘要」。也可呼叫 `POST /api/transcripts/summarize`，body 為 `{"transcript":"..."}`。

Open Transcript summary below the chat, paste a written doctor-patient conversation and generate the summary. The REST endpoint takes a transcript string.

輸出 `summary` 包含 `chief_complaint`、`diagnosis`、`medication`、`doctor_instructions`，以及各欄位的原文 `evidence`。未提及內容為 null；明說沒有開藥則保留這個事實。不自創診斷、藥名或劑量。這是文字摘要，沒有錄音轉文字功能。輸入長度上限 16,000 字元；逐字稿不寫入應用資料庫，但會送往模型供應商。

The four-field summary includes verbatim evidence. Missing information remains null; explicit no medication is preserved. It does not invent diagnoses or doses, and does not transcribe audio. Maximum input is 16,000 characters. Transcripts are sent to the provider but not persisted in the application database.

## Five-minute interview demo

Use future dates relative to the demo day; all times are local to the selected clinic.

Before booking, try **“我到医院的流程”** / **“What should I expect when visiting the clinic?”** for a bilingual visit guide with current booking details. Unspecified on-site procedures are explicitly marked for clinic confirmation.

1. Ask **“我有花生過敏，可以諮詢誰？”**. The local answer references the allergy history, explains that the catalog has no dedicated allergy service, and identifies the general practitioner. Evidence labels show CSV and record IDs.
2. Ask **“What are the clinic cancellation policies?”** or **“I have a skin rash. What service is available?”**.
3. Ask **“When is my next appointment?”**. This reads current patient bookings via GET /api/bookings; only future Confirmed appointments are considered for “next”.
4. Start a new conversation and say **“I want to book an appointment”**.
5. Reply **“Dr. Sarah Jenkins for a checkup”**, then **“2035-11-08 at 9:30 am”**. Missing fields are requested across turns. When all fields are valid, the agent calls POST /api/bookings automatically.
6. Verify the booking ID in the chat, tool trace and right-hand list. Refresh the page or restart the backend; the same booking remains.
7. Try **“Book D103 T001 2035-11-08 09:30”** to demonstrate validation; reply **“D101”** to correct the doctor.
8. In an unfinished draft say **“cancel booking draft”** to clear it. Existing appointment cancellation/rescheduling is outside this MVP.

Local mode supports doctor IDs/names, treatment IDs/basic names, YYYY-MM-DD, “tomorrow/明天”, HH:MM and English AM/PM. It is deliberately limited; ambiguous or unrecognized dates remain missing. LLM mode handles broader natural language. Explicitly select the service and doctor: recommendations alone do not authorize creating an appointment.

## API contract

- GET /api/health: backend status and actual mode.
- GET /api/profile: fixed P001 profile, allergies and treatment history.
- GET /api/catalog: clinics, doctors and treatments.
- GET /api/bookings?patient_id=P001: joined appointment records, clinic timezone.
- POST /api/chat: `message`, `session_id`, `request_id`, optional `patient_id` (P001 only).
- POST /api/bookings: `doctor_id`, `treatment_id`, `booking_date`, `booking_time`, `request_id`, optional `notes` and `patient_id`.

Reuse the same request ID and payload when retrying. Reusing it for different content returns 409. Validation failures return 422; database failure 503; model failure 502. The UI keeps the original request ID for retries after network errors.

## Tests / 測試

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
$env:PYTHONPATH="backend"
$env:AI_MODE="local"
.\.venv\Scripts\python.exe -m coverage run -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe -m coverage report
cd frontend
npm.cmd ci
npm.cmd run test:coverage
npm.cmd run build
```

Tests create their own temporary SQLite files under runtime/tests. They do not write to your demo database. See VALIDATION.md for results and limits.

## Structure

- backend/app/db.py: schema, seed, session storage.
- backend/app/knowledge.py: FTS5/BM25 retrieval and bilingual query expansion.
- backend/app/agent.py: intent routing, multi-turn workflow, LLM adapter and REST tools.
- backend/app/answers.py: concise grounded answers, visit orientation and timezone-aware upcoming booking order.
- backend/app/llm.py: Chat Completions/Responses transport, safe errors and usage traces.
- backend/app/transcripts.py: evidence-validated transcript extraction.
- scripts/live_acceptance.py: opt-in live-provider acceptance using isolated databases.
- backend/app/main.py: validated API endpoints, persistence and frontend serving.
- frontend/src/: React chat, evidence and live bookings.
- mock-data/: all six original CSV datasets.
- TECH_DOC.md: design, assumptions and tradeoffs.

## Scope and submission

Single predefined adult patient P001; no authentication; bind locally. New timeslots are assumed available, per assignment. New bookings cannot be in the past. Historical seeded records remain unchanged. This is clinic service navigation, not diagnosis or prescribing.

Real model calls require configured credentials. Live Poe Claude acceptance is recorded separately from mocked unit tests. Transcript summarization and local tracing are implemented. Kubernetes manifests are provided; external Langfuse is not integrated.

Docker is included as an optional path: `docker compose up --build`. It has not been exercised on this machine. The volume persists the database.

Submission repository: https://github.com/gjtjx/KUDOS. The source excludes .env, .venv, runtime, node_modules and dist (covered by .gitignore); package-lock.json is included. The local delivery also contains prebuilt frontend assets, so start.cmd can use an existing compatible Python environment without rebuilding.


最新模型對照與相容設定 / Current provider comparison: [MODEL_COMPARISON.md](MODEL_COMPARISON.md)。
