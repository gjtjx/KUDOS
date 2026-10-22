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

## Enable real LLM orchestration

Copy `.env.example` to `.env` in the project root, then configure:

```dotenv
AI_MODE=llm
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=your-tool-calling-model-id
LLM_API_KEY=your-api-key
```

Choose a model that supports Chat Completions function calling and strict tool schemas. Model access is provider/account dependent; no model or key is assumed. Restart the backend. The UI badge must say LLM.

Recognized visit-process questions use a grounded host-side guide in either mode. Other questions in LLM mode dynamically route intent and extracts booking fields with the `route_intent` function schema. The host executes the corresponding retrieval or REST tool, validates every booking, and derives confirmation directly from the saved record. For knowledge questions, retrieved records and patient context ground a second model call.

Only LLM mode transmits conversation, mock patient profile/history, bookings and catalog context to the configured provider. Never commit `.env`. Provider errors return an explicit retryable error, not a silently simulated LLM response.

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
- backend/app/main.py: validated API endpoints, persistence and frontend serving.
- frontend/src/: React chat, evidence and live bookings.
- mock-data/: all six original CSV datasets.
- TECH_DOC.md: design, assumptions and tradeoffs.

## Scope and submission

Single predefined adult patient P001; no authentication; bind locally. New timeslots are assumed available, per assignment. New bookings cannot be in the past. Historical seeded records remain unchanged. This is clinic service navigation, not diagnosis or prescribing.

Real model calls need your own configured credentials. The default demo and mocked tool-contract tests do not prove live provider integration. Optional transcript summarization, Langfuse and Kubernetes are not implemented.

Docker is included as an optional path: `docker compose up --build`. It has not been exercised on this machine. The volume persists the database.

Submission repository: https://github.com/gjtjx/KUDOS. The source excludes .env, .venv, runtime, node_modules and dist (covered by .gitignore); package-lock.json is included. The local delivery also contains prebuilt frontend assets, so start.cmd can use an existing compatible Python environment without rebuilding.
