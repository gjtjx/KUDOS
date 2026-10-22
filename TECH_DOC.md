# ClinicPilot AI — Technical Design

## 1. Requirements and implementation

| Requirement | Implementation | Evidence |
|---|---|---|
| Index clinics/doctors/treatments | SQLite FTS5 index; BM25 ranking; bilingual expansion | knowledge.py; retrieval test |
| Multi-turn intent analysis | Local rules or LLM strict function call; persisted draft/history | agent.py; multi-turn and interleaving tests |
| Personalized context | P001 profile, allergies, visit history and live bookings | profile API and REST tool context |
| Existing booking queries via API/tool | HTTPX GET /api/bookings through ASGI transport | tool trace; query test |
| Automated booking via API/tool | HTTPX POST /api/bookings when four fields are complete | booking test and persisted row |
| Seed six CSV files | Relational schema with foreign keys; insert-if-missing seed | idempotent seed test |
| Request validation and errors | Pydantic, parameterized SQL, typed HTTP errors | validation/error tests |
| React chat and bookings | Chat composer, sources, draft, retry and auto-refresh | production build and browser acceptance |
| Local setup and technical docs | README, this document, Windows launchers | source deliverable |

## 2. Architecture

```text
React workbench
    │ POST /api/chat {session_id, request_id, message}
    ▼
FastAPI → conversation orchestrator
    ├── patient context + GET /api/bookings REST tool
    ├── local router OR LLM route_intent function call
    ├── knowledge intent → FTS5 retrieval → grounded answer
    ├── booking query → joined, patient-scoped booking results
    └── new booking → collect slots → POST /api/bookings REST tool
                                      │
                                      ▼
                              validated SQLite transaction
    ◀── factual result + intent + sources + tool trace + draft
React → GET /api/bookings → refreshed list
```

AI modules live under backend/app rather than a separate network service. The assignment permits a custom Python agent; a single deployable process simplifies a live demonstration without removing module boundaries.

HTTPX ASGITransport dispatches real HTTP request/response objects through the exact FastAPI route handlers, Pydantic validation and error handling. It does not call a repository insert function directly. No loopback socket or hardcoded self-host URL is needed; the booking endpoints are also externally callable as standard REST endpoints.

## 3. Intent and state workflow

State is keyed by opaque browser session ID, always bound to P001. Each state contains an active flag, a four-slot draft with a booking idempotency key, and a capped twenty-message history.

- visit_flow: provide general visit orientation, enriched with the next booking and catalog address/preparation. Missing on-site policies are explicitly unknown; no booking is created and drafts are preserved. In local mode this is deterministic; in LLM mode intent and wording both use the model, with host-provided factual context.
- knowledge: retrieve evidence and answer; leave any active draft intact.
- bookings: read latest records via REST, return next future Confirmed booking plus history.
- book: merge explicitly extracted parameters. Ask for missing doctor, treatment, date and time. Once complete, execute the booking API.
- cancel_draft: clear only the pending draft; do not mutate confirmed appointments.

All parameters remain validated independently of model output. Unknown IDs, inappropriate doctor/service combinations, dates in the past and invalid time formats are rejected. A rejected draft remains editable and is never described as saved.

Local mode is a deterministic fallback for an interview without credentials. LLM mode uses a strict JSON function schema for routing/extraction; the host retains control of side effects. Booking confirmation comes from the API result, not a model-generated claim.

## 4. RAG decisions

Each clinic, doctor and treatment row is one indexed document with source filename and primary ID. Query terms are safely quoted for FTS5 MATCH and bound as SQL parameters. English stopwords are removed; common Chinese and symptom terms expand to catalog specialties. BM25 ranks a maximum of six results.

FTS5 is intentionally a lexical retriever, not a dense embedding vector store. For this eleven-record knowledge catalog it is transparent, deterministic, fully local and easy to audit. It does not understand all synonyms or medical terminology. The LLM can improve the language of the answer, but only catalog evidence is supplied as factual support. For a larger catalog, the retrieval interface can be replaced with hybrid vector/lexical search and evaluated on a labelled question set.

Citations are attached to retrieved rows, not presented as medical research. Patient history is separately injected and is never indexed in the general knowledge corpus. Allergy concerns are routed to a discussion with a general practitioner; the catalog does not contain an allergy-testing service, and the system must not invent one.

## 5. Relational schema and persistence

- clinics(clinic_id PK): contact, hours, cancellation and emergency information.
- doctors(doctor_id PK, clinic_id FK): specialty, languages, consultation fee, biography.
- treatments(treatment_id PK): service category, duration, price and preparation.
- patients(patient_id PK): demographics, allergies and emergency contact.
- patient_bookings(booking_id PK, patient_id FK, doctor_id FK, treatment_id FK): local date/time, status and notes.
- patient_treatment_history(record_id PK, patient_id FK, doctor_id FK): past visits and clinician notes.
- sessions(id PK, state JSON): draft and bounded conversational history.
- requests(id PK, payload, response JSON): exactly-repeatable successful chat responses.
- booking_keys(id PK, payload, booking_id FK): transactional booking deduplication.
- knowledge: FTS5 virtual table, rebuilt from database catalog at startup.

SQLite foreign keys are enabled on every connection. Seed records are inserted only if their IDs do not exist. New bookings never modify the supplied CSV files. Parameterized SQL is used for input values; table names and seed columns are trusted application constants or checked against schema.

Booking INSERT and idempotency-key INSERT share a BEGIN IMMEDIATE transaction. A repeated key/payload returns the original booking; different payload returns 409. The initial draft key derives deterministically from session/request IDs. Even if the booking commits but saving the chat response fails, retrying the same chat request returns the same booking rather than creating another.

An application-level asyncio lock serializes chat state transitions in the single-worker MVP. API booking transactions independently serialize writes. Multi-worker/distributed chat deployments would require transactional per-session locking; they are not supported by the demo launcher.

## 6. Explicit assumptions

- Fixed P001 John Doe; attempts to select another patient are rejected. No authentication is implemented.
- Data gives no doctor-treatment join table. An explicit mapping connects specialty-compatible services: T001→D101, T002→D102, T003→D103, T004→D101/D102, T005→D104.
- P001 is an adult; the pediatric vaccination service is rejected for this patient.
- C001 uses America/New_York and C002 America/Los_Angeles, inferred from supplied addresses. Dates/times remain clinic-local and UI shows the timezone.
- The assignment assumes all requested slots are available. No collision, opening-hours or resource-availability enforcement is performed.
- New appointments must be in the future. Existing historical CSV bookings remain as supplied.
- Consultation fees and service prices are displayed as separate source fields; no combined invoice total is inferred.
- Local relative-date parsing uses New York “tomorrow”; explicit YYYY-MM-DD is recommended for Santa Monica. Advanced ambiguous-date resolution and DST edge-case validation are future work.

## 7. Reliability, privacy and boundaries

The UI retains the original request for network retries and refetches bookings after successful chat. A refresh error is shown separately from a successful booking so it does not pretend the booking failed. Conversation storage persists on the backend, while rendered chat bubbles reset on page reload; a new-chat action starts a new session.

Model failures are explicit 502 responses, with no silent local fallback in LLM mode. Logs contain failure categories, not API keys or patient transcripts. CORS permits only the development origins; the default server binds to 127.0.0.1. No authentication or production hardening is implied.

LLM mode sends mock patient context to the configured provider. The system prompt treats retrieved text as data and restricts answers to service navigation; output is not clinically validated. This application is unsuitable as a diagnostic or emergency triage system.

The implementation uses the documented Chat Completions function calling format: [OpenAI function calling guide](https://developers.openai.com/api/docs/guides/function-calling). Provider-specific support still requires a live integration check with the selected model.

## 8. Verification and known limits

Automated tests exercise persisted records through FastAPI, multi-turn completion, interleaved questions, session isolation, retries, failed chat-save recovery, invalid inputs, existing-record retrieval and mocked LLM function calls. With user-configured credentials, Poe Claude Sonnet 5.5 live acceptance now covers the complete workflow; see LIVE_MODEL_REPORT.md.

Structured transcript extraction is now implemented with a strict application schema and verbatim evidence validation. External tracing, automated clinical evaluations, authentication, rate limiting, long-term session retention and booking cancellation/rescheduling remain outside the MVP. Docker files are supplied but not runtime-tested.


## 9. Regression fix and maintainability

The reported new-chat utterance “我到医院的流程” previously fell through to lexical search with no matching tokens. The fallback then unconditionally mentioned allergies and generic help; other answers dumped full catalog rows. `answers.py` now separates visit guidance from field-specific factual responses, omits unrelated personal context, and preserves conditional preparation instructions. The React application and API client are independently importable for component/unit tests. New chat also clears unsent input. See MAINTENANCE.md for the feature-to-test matrix and operational procedures.

## 10. Claude, RAG and transcript extension / Claude、檢索與摘要擴充

LLM mode no longer calls is_visit_flow before the model. The route_intent schema adds search_query so Claude can resolve references and rewrite a standalone retrieval query. Catalog IDs select actual database rows and related doctor/clinic records; otherwise FTS5/BM25 is used. This is structured/lexical RAG, not embeddings. The model never provides the factual row contents.

LLM 模式每次由 Claude 先判斷意圖；search_query 用於解析上下文及檢索改寫。目錄 ID 只查真實資料列與關聯，不接受模型自造資料；無 ID 時使用 FTS5/BM25。

llm.py supports both API shapes and records provider response ID, model, latency and token usage without credentials or hidden reasoning. Poe's selected Claude model was verified using Chat Completions, auto tool choice and application validation. Empty answers, incomplete output, absent tool calls and provider failures never silently become local answers.

逐字稿摘要以獨立工具 summarize_transcript 提取四個 nullable 欄位及 evidence。所有非空欄位必須有逐字引用，引用必須出現在原文；未提及欄位為 null。這是來源驗證，不是臨床正確性證明。摘要不使用 P001 個資，也不寫入聊天或預約資料表。

The summary endpoint is stateless, does not inject P001 context and does not persist transcripts. It validates evidence provenance but still requires human semantic review. The browser timeout allows two sequential provider calls; server timeout is configurable from 1 to 180 seconds. Chat execution remains single-worker and serialized.
