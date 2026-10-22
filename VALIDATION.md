# Validation — 2026-10-22

## Bilingual update / 繁英對照更新

17 backend tests passed after the Traditional Chinese / English update. Added coverage for Traditional Chinese intent routing, service selection, bilingual retrieved facts, booking labels, validation messages and LLM output-language instructions. React production build also passed. A browser check on an isolated database verified the Traditional Chinese booking suggestion, bilingual missing-field prompt, bilingual booking confirmation/preparation/allergy reminder and list update from 2 to 3 records. Original CSV values remain unchanged; translations are display metadata. Live LLM output remains unverified without provider credentials.

## Automated acceptance

15 unittest cases passed against isolated SQLite databases, using Python 3.13 and the pinned FastAPI/httpx/Pydantic versions.

- All six CSV tables seeded; repeat startup does not duplicate rows.
- P001 allergy/history context loaded; alternate patient IDs rejected.
- FTS retrieval and record-level source citations, including Chinese allergy queries.
- Multi-turn missing-parameter collection → REST booking creation → live database list.
- Existing booking queries via REST and correct upcoming/historical distinction.
- Unrelated questions preserve an active draft; separate sessions do not share drafts.
- Cancelling a draft does not cancel persisted bookings.
- Invalid dates/times, unknown IDs, doctor-service mismatch and adult pediatric vaccination rejected.
- REST and chat idempotency; same key with changed content rejected.
- Database restart preserves bookings and unfinished drafts.
- Chat response storage failure after booking commit does not create a duplicate on retry.
- Mocked LLM function-call routing executes the real booking endpoint.
- Invalid model response returns an error instead of a false booking confirmation.

Commands:

    $env:PYTHONPATH="backend"
    python -m unittest discover -s backend/tests -v
    cd frontend
    npm.cmd run build

React production build passed with Vite 6.4.5. npm dependency audit after updating Vite reported zero known vulnerabilities (18 installed packages).

## Browser acceptance

Used an isolated local server and runtime/browser-test.db, not the delivery database.

1. Page loaded the fixed John Doe profile and two seeded P001 bookings.
2. Clicked “帮我预约 D101 的 T001 体检”.
3. Assistant requested date and local time, showing D101 and T001 in the draft.
4. Entered “2035-11-08 09:30”.
5. Assistant returned a new persisted booking ID and preparation/allergy reminders.
6. Bookings panel changed from 2 to 3 entries.
7. Reloaded the page; all three entries remained, including the new record.
8. Browser captured no console errors/warnings during this flow.

The restricted execution environment initially prevented SQLite/HTTP integration tests; the successful results above were obtained outside that restriction. No application logic was weakened to bypass those failures.

## Not yet verified

GitHub Actions run #1 was blocked before any test steps started. GitHub reported: "The job was not started because your account is locked due to a billing issue." See https://github.com/gjtjx/KUDOS/actions/runs/39775522266. The repository owner must resolve the account issue before rerunning CI; local acceptance results above remain valid.

- Live remote LLM/provider calls (no API key or model supplied). Tests use mocked model responses, explicitly distinct from a live model check.
- Docker image/runtime, macOS/Linux startup and clinical correctness.
- Multi-worker deployment, load testing, daylight-saving ambiguous-time edge cases and production authentication.
- No real patient data or real clinic appointments were used. Supplied CSVs are mock data.
