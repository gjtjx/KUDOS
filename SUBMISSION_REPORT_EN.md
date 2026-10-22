# ClinicPilot AI — Submission Overview

**Making every follow-up visit easier.**

- **Repository:** [gjtjx/KUDOS](https://github.com/gjtjx/KUDOS)
- **Stack:** React, Vite, FastAPI, Python and SQLite
- **Documentation reviewed:** October 23, 2026
- **Latest functional acceptance:** October 23, 2026

## 1. Project overview

ClinicPilot is a working clinic assistant prototype for a predefined mock patient. It supports catalog-grounded questions, doctor and service recommendations, existing appointment queries and conversational booking with actual database persistence.

The workbench includes paired Traditional Chinese and English interface text, source references, an appointment list, a booking draft, transcript summarization and a model-activity panel.

## 2. Assignment coverage

| Requirement | Delivered implementation |
|---|---|
| Clinic, doctor and treatment RAG | Exact-ID retrieval and SQLite FTS5/BM25 over the supplied catalog |
| Multi-turn intent and parameter extraction | Structured routing, recent conversation history and persistent booking state |
| Existing appointment tool | GET /api/bookings through the actual FastAPI REST handlers |
| New appointment execution | POST /api/bookings with validation, transaction and idempotency |
| Fixed patient context | P001 profile, allergies, treatment history and current appointments |
| Relational persistence | Six CSV-seeded business tables, plus state and reliability tables |
| React workbench | Chat, retry, automatic/manual booking refresh and source display |
| Optional transcript summary | Four-field JSON with verbatim evidence and null for unmentioned facts |
| Optional observability | Persistent request/generation traces, timing, usage and error categories |
| Optional deployment | Docker Compose and Kubernetes manifests; runtime acceptance pending |

The project selects REST from the assignment's REST-or-MCP alternatives and implements custom Python orchestration. The full requirement mapping is in [REQUIREMENTS_REVIEW.md](REQUIREMENTS_REVIEW.md).

## 3. Architecture and design

The language model interprets intent, resolves references and extracts parameters. The application owns state, submission controls, validation and database writes.

Each turn reads current bookings through REST and combines them with patient context and the small catalog. Knowledge questions are rewritten for exact-ID or lexical retrieval, then answered using selected evidence. Dense embeddings and a vector database are not implemented. The router currently sees the full small catalog; larger datasets would require candidate retrieval before routing.

Booking state persists doctor, treatment, date and time independently of bounded conversational history. Explicit withdrawals clear old fields. Interleaved questions preserve the draft. A request to wait creates a persistent hold, so complete information does not automatically override submission intent.

REST tools use HTTPX ASGITransport against the same FastAPI application. They execute real request validation and database transactions within one process. The booking and its idempotency record are committed atomically. Chat response caching is a separate transaction; stable booking keys protect retries after a post-booking chat-save failure.

Booking confirmation is based on the API result, not another model-generated success claim. Provider failures are explicit, with no silent fallback to local templates.

See [TECH_DOC.md](TECH_DOC.md) for the architecture, data model, assumptions and tradeoffs.

## 4. Additional features

The transcript endpoint accepts written doctor-patient conversation text in LLM mode and extracts chief complaint, diagnosis, medication and doctor instructions. Missing information remains null; non-null output requires quotations from the source. A single repair attempt is allowed for invalid extraction. This is text summarization, not speech recognition or clinical validation.

Local tracing records parent requests and individual model calls, including latency, reported tokens, errors and caching. Trace tables contain metadata rather than prompts or credentials; conversation tables still retain chat content. No external Langfuse integration or cost estimation is included.

Deployment configuration uses one worker, persistent storage, non-root execution and probes. It has been checked offline, but container builds and cluster behavior have not been runtime-validated.

## 5. Setup and demonstration

Start with [README.md](README.md#quick-start), which is the maintained source for prerequisites, startup and provider profiles. A fresh installation defaults to a clearly labelled local demo. Live operation requires a matching provider URL, model, API style and private key.

Startup reads .env only, with process environment variables taking precedence. Credential files, runtime databases and raw reports are excluded from the repository. No usable key is included in this document.

Suggested demonstration:

1. Ask about a clinic or service and inspect the sources.
2. Follow up using a reference to the recommended doctor.
3. Query the current patient's appointments.
4. Start a new booking and supply details across turns.
5. Ask a preparation question, hold the draft, then explicitly confirm.
6. Verify the saved booking ID in the refreshed list and after restart.
7. Inspect a text summary and model activity.

Use a future date and an isolated demonstration database.

## 6. Recorded validation

The October 23 fresh-clone review recorded **118 backend tests and the unchanged prior 28 frontend tests passing**, with a successful production build. DeepSeek passed **82 core checks** and **27 hold/withdrawal checks** after fixes. Poe Sonnet's **82-check result is historical, from October 22**, and was not rerun in this review. Later broad testing exposed failures that were corrected and retested with 112 targeted checks plus 82 full checks; see [FIX_VALIDATION.md](FIX_VALIDATION.md). The whole 64-case suite was not rerun. See [SUBMISSION_CHECK.md](SUBMISSION_CHECK.md) for earlier browser evidence.

These checks cover fourteen chat turns, two transcript summaries, persistence, restart, deduplication, corrections and trace accounting. They are not 82 independent clinical cases or a general model benchmark. Earlier failures were retained and informed regression fixes, including an auxiliary-word retrieval match and over-cautious interpretation of selecting booking details.

[Test coverage and limits](VALIDATION.md) and [provider comparison and reproduction](MODEL_COMPARISON.md) contain the detailed results. No successful cloud CI or container/cluster runtime acceptance is claimed.

## 7. Scope and next steps

This is a single-patient local demonstration without authentication, production authorization or validated horizontal scaling. A global chat lock and synchronous SQLite access limit concurrency.

The assignment assumes available timeslots, so conflict checking is outside scope. Existing appointment cancellation/rescheduling, audio transcription and clinical certification are not implemented. Exact evidence matching does not prove medical or semantic correctness.

Future work should prioritize a labelled routing/retrieval evaluation set, access control, data retention and concurrency design. Hybrid retrieval can then be evaluated against the lexical baseline if catalog scale or recall warrants it.

## 8. Supporting documentation

- [README.md](README.md): setup, configuration and demonstration.
- [TECH_DOC.md](TECH_DOC.md): architecture and design decisions.
- [VALIDATION.md](VALIDATION.md): test evidence and unverified boundaries.
- [MODEL_COMPARISON.md](MODEL_COMPARISON.md): live provider compatibility and comparison.
- [MAINTENANCE.md](MAINTENANCE.md): backup, troubleshooting and release operations.
- [DEPLOYMENT.md](DEPLOYMENT.md): container and Kubernetes procedures.
- [OBSERVABILITY.md](OBSERVABILITY.md): trace fields, retention and privacy.
