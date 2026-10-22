"""Booking consent, withdrawn selections, concurrency and boundary regressions."""
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
FULL = dict(doctor_id="D101", treatment_id="T001", booking_date="2035-12-06", booking_time="10:00")

class ExtendedTests(unittest.TestCase):
    def setUp(self):
        folder = ROOT / "runtime/tests"
        folder.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=folder)
        self.path = Path(self.temp.name) / "test.db"
        with patch.dict(os.environ, {"AI_MODE": "local"}):
            self.app = create_app(self.path, ROOT / "mock-data")
        self.app.state.agent.mode = "llm"
        self.client = TestClient(self.app)
        self.counter = 0
        self.before = self.client.get("/api/bookings").json()

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def action(self, args, key=None):
        self.counter += 1
        call = {"tool_calls": [{"function": {"name": "route_intent", "arguments": json.dumps(args)}}]}
        with patch.object(self.app.state.agent, "llm", AsyncMock(side_effect=[call, {"content": json.dumps({'paragraphs':[{'zh':'草稿尚未提交','en':'Draft not submitted'}]})}])):
            return self.client.post("/api/chat", json={"message": "test turn", "session_id": "edge", "request_id": key or str(self.counter)})

    def test_complete_draft_on_hold_requires_explicit_confirmation(self):
        first = self.action({"intent": "book", "booking_action": "hold", **FULL}).json()
        self.assertIsNone(first["booking"])
        self.assertFalse(any(t["tool"] == "POST /api/bookings" for t in first["tool_trace"]))
        self.assertEqual(self.client.get("/api/bookings").json(), self.before)
        second = self.action({"intent": "book", "booking_action": "collect", "booking_time": "11:00"}).json()
        self.assertIsNone(second["booking"])
        final = self.action({"intent": "book", "booking_action": "confirm"}).json()
        self.assertEqual(final["booking"]["booking_time"], "11:00:00")
        self.assertEqual(len(self.client.get("/api/bookings").json()), len(self.before) + 1)

    def test_ordinary_submit_cannot_override_persisted_hold(self):
        self.action({"intent": "book", "booking_action": "hold", **FULL})
        r = self.action({"intent": "book", "booking_action": "submit", "booking_time": "12:00"}).json()
        self.assertIsNone(r["booking"])
        self.assertTrue(self.app.state.db.state("edge")["booking_hold"])
        self.assertEqual(self.client.get("/api/bookings").json(), self.before)

    def test_collect_with_complete_fields_does_not_write(self):
        r = self.action({"intent": "book", "booking_action": "collect", **FULL}).json()
        self.assertIsNone(r["booking"])
        self.assertEqual(r["draft"]["doctor_id"], "D101")

    def test_withdrawn_date_is_removed_before_missing_field_check(self):
        self.action({"intent": "book", "booking_action": "collect", **FULL, "booking_time": None})
        r = self.action({"intent": "book", "booking_action": "hold", "clear_slots": ["booking_date"], "booking_time": "10:00"}).json()
        self.assertNotIn("booking_date", r["draft"])
        self.assertIsNone(r["booking"])
        confirmed = self.action({"intent": "book", "booking_action": "confirm"}).json()
        self.assertIsNone(confirmed["booking"])
        self.assertEqual(self.client.get("/api/bookings").json(), self.before)

    def test_clear_and_replace_service_selection(self):
        self.action({"intent": "book", "booking_action": "collect", **FULL, "booking_time": None})
        r = self.action({"intent": "book", "booking_action": "submit", "clear_slots": ["doctor_id", "treatment_id"], "doctor_id": "D103", "treatment_id": "T003", "booking_time": "09:00"}).json()
        self.assertEqual(r["booking"]["doctor_id"], "D103")
        self.assertEqual(r["booking"]["treatment_id"], "T003")

    def test_missing_or_invalid_permission_fails_without_writes(self):
        for changes in ({}, {"booking_action": None}, {"booking_action": "yes"}, {"booking_action": True}):
            with self.subTest(changes=changes):
                r = self.action({"intent": "book", **FULL, **changes})
                self.assertEqual(r.status_code, 502)
        self.assertEqual(self.client.get("/api/bookings").json(), self.before)
        self.assertEqual(self.app.state.db.rows("SELECT * FROM sessions"), [])

    def test_invalid_clear_fields_rejected_without_writes(self):
        for clears in (None, "booking_date", ["request_id"], [False], [{}]):
            with self.subTest(clears=clears):
                r = self.action({"intent": "book", "booking_action": "submit", "clear_slots": clears, **FULL})
                self.assertEqual(r.status_code, 502)
        self.assertEqual(self.client.get("/api/bookings").json(), self.before)

    def test_hold_survives_questions_and_restart(self):
        self.action({"intent": "book", "booking_action": "hold", **FULL})
        self.action({"intent": "knowledge", "search_query": "C001 hours"})
        self.client.close()
        with patch.dict(os.environ, {"AI_MODE": "local"}):
            self.app = create_app(self.path, ROOT / "mock-data")
        self.app.state.agent.mode = "llm"
        self.client = TestClient(self.app)
        r = self.action({"intent": "book", "booking_action": "submit"}).json()
        self.assertIsNone(r["booking"])
        self.assertIsNotNone(self.action({"intent": "book", "booking_action": "confirm"}).json()["booking"])

    def test_cancel_clears_hold_and_draft(self):
        self.action({"intent": "book", "booking_action": "hold", **FULL})
        r = self.action({"intent": "cancel_draft"}).json()
        self.assertEqual(r["draft"], {})
        self.assertFalse(self.app.state.db.state("edge")["booking_hold"])
        self.assertIsNotNone(self.action({"intent": "book", "booking_action": "submit", **FULL}).json()["booking"])

    def test_concurrent_identical_rest_requests_create_one_record(self):
        body = {**FULL, "request_id": "concurrent"}
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: self.client.post("/api/bookings", json=body), range(12)))
        self.assertTrue(all(r.status_code == 200 for r in results))
        self.assertEqual(len({r.json()["booking_id"] for r in results}), 1)
        self.assertEqual(len(self.client.get("/api/bookings").json()), len(self.before) + 1)

    def test_concurrent_conflicting_rest_requests_have_one_winner(self):
        bodies = [{**FULL, "request_id": "conflict", "booking_time": t} for t in ("10:00", "11:00")]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda b: self.client.post("/api/bookings", json=b), bodies))
        self.assertEqual(sorted(r.status_code for r in results), [200, 409])
        self.assertEqual(len(self.client.get("/api/bookings").json()), len(self.before) + 1)

    def test_api_boundaries_reject_invalid_payloads_without_mutation(self):
        for change in ({"patient_id": "P002"}, {"doctor_id": "D101'; DROP TABLE patients;--"}, {"booking_time": "10:00+08:00"}, {"booking_date": "2035-02-29"}, {"notes": "字" * 1001}, {"status": "Confirmed"}):
            with self.subTest(change=change):
                r = self.client.post("/api/bookings", json={**FULL, "request_id": "invalid", **change})
                self.assertEqual(r.status_code, 422)
        self.assertEqual(self.client.get("/api/bookings").json(), self.before)
        self.assertEqual(self.app.state.db.profile()["patient_id"], "P001")

    def test_valid_leap_day_and_unicode_notes_persist(self):
        r = self.client.post("/api/bookings", json={**FULL, "request_id": "leap", "booking_date": "2036-02-29", "notes": "病史\nallergy 🏥"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["notes"], "病史\nallergy 🏥")

    def local_chat(self, message):
        self.app.state.agent.mode = "local"
        self.counter += 1
        return self.client.post("/api/chat", json={"message": message, "session_id": "local", "request_id": str(self.counter)}).json()

    def test_local_mode_also_preserves_explicit_hold(self):
        first = self.local_chat("Book D101 T001 2035-12-06 10:00, do not submit, wait")
        self.assertIsNone(first["booking"])
        self.assertIsNone(self.local_chat("11:00")["booking"])
        self.assertEqual(self.local_chat("confirm")["booking"]["booking_time"], "11:00:00")

    def test_local_chinese_hold_and_withdrawal(self):
        self.assertIsNone(self.local_chat("幫我預約 D101 T001 2035-12-06 10:00，先不要提交")["booking"])
        second = self.local_chat("撤回日期")
        self.assertNotIn("booking_date", second["draft"])
        self.assertIsNone(self.local_chat("確認")["booking"])
