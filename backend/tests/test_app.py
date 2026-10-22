import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.db import Database
from app.knowledge import retrieve

DATA = Path(__file__).resolve().parents[2] / "mock-data"

class AppTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[2] / "runtime" / "tests"
        test_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        self.path = Path(self.temp.name) / "test.db"
        with patch.dict(os.environ, {"AI_MODE": "local"}):
            self.app = create_app(self.path, DATA)
        self.client = TestClient(self.app)
        self.counter = 0

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def chat(self, text, session="test", key=None):
        self.counter += 1
        return self.client.post("/api/chat", json={"message": text, "session_id": session, "request_id": key or str(self.counter)})

    def booking(self, **changes):
        return {"doctor_id": "D101", "treatment_id": "T001", "booking_date": "2035-11-08", "booking_time": "09:30", "request_id": "booking-test", **changes}

    def test_seed_all_six_tables_and_idempotent(self):
        before = {t: len(self.app.state.db.rows("SELECT * FROM " + t)) for t in ("clinics","doctors","treatments","patients","patient_bookings","patient_treatment_history")}
        self.assertTrue(all(before.values()))
        Database(self.path, DATA)
        after = {t: len(self.app.state.db.rows("SELECT * FROM " + t)) for t in before}
        self.assertEqual(before, after)

    def test_profile_and_patient_isolation(self):
        self.assertIn("Peanuts", self.client.get("/api/profile").json()["known_allergies"])
        self.assertEqual(self.client.get("/api/bookings?patient_id=P002").status_code, 403)
        self.assertEqual(self.client.post("/api/bookings", json=self.booking(patient_id="P002")).status_code,422)
        self.assertTrue(all(b["patient_id"] == "P001" for b in self.client.get("/api/bookings").json()))

    def test_retrieval_citations_and_allergies(self):
        r = self.chat("我有花生过敏，可以咨询谁？").json()
        self.assertEqual(r["intent"], "knowledge")
        self.assertIn("沒有專門的過敏", r["reply"])
        self.assertTrue(r["sources"])
        self.assertIn("D101",r["reply"])
        self.assertTrue(retrieve(self.app.state.db,"rash"))
        self.assertEqual(retrieve(self.app.state.db, '" OR 1=1 -- unknownzzzzz'), [])

    def test_multiturn_booking_calls_rest_and_updates_database(self):
        baseline = len(self.client.get("/api/bookings").json())
        a = self.chat("I want to book an appointment").json()
        self.assertEqual(a["intent"],"book")
        self.assertIsNone(a["booking"])
        b = self.chat("Dr. Sarah Jenkins for a checkup").json()
        self.assertEqual(b["draft"]["doctor_id"], "D101")
        self.assertIsNone(b["booking"])
        c = self.chat("2035-11-08 at 9:30 am").json()
        self.assertIsNotNone(c["booking"])
        self.assertIn("POST /api/bookings",[t["tool"] for t in c["tool_trace"]])
        self.assertEqual(len(self.client.get("/api/bookings").json()),baseline+1)

    def test_existing_queries_via_rest(self):
        r = self.chat("When is my next appointment?").json()
        self.assertEqual(r["intent"], "bookings")
        self.assertIn("B1001",r["reply"])
        self.assertEqual(r["tool_trace"][0]["tool"], "GET /api/bookings")

    def test_interleaved_question_preserves_draft(self):
        self.chat("Book D101 T001")
        self.chat("What are the clinic opening hours?")
        r = self.chat("2035-11-08 10:00").json()
        self.assertIsNotNone(r["booking"])

    def test_sessions_are_separate_and_cancel_draft(self):
        self.chat("Book D101 T001", session="one")
        self.assertEqual(self.chat("2035-11-08 10:00",session="two").json()["intent"],"knowledge")
        r = self.chat("cancel booking draft",session="one").json()
        self.assertEqual(r["draft"],{})
        self.assertIsNone(r["booking"])

    def test_invalid_dates_and_mismatched_catalog(self):
        for change in ({"booking_date":"2020-01-01"},{"booking_date":"2035-02-30"},{"booking_time":"25:00"},{"doctor_id":"D999"},{"doctor_id":"D103"},{"treatment_id":"T999"}):
            self.assertEqual(self.client.post("/api/bookings",json=self.booking(**change)).status_code,422)

    def test_booking_idempotency_and_conflicting_reuse(self):
        body=self.booking()
        a=self.client.post("/api/bookings",json=body)
        b=self.client.post("/api/bookings",json=body)
        self.assertEqual(a.status_code,200)
        self.assertEqual(a.json()["booking_id"],b.json()["booking_id"])
        self.assertEqual(self.client.post("/api/bookings",json=self.booking(booking_time="11:00")).status_code,409)

    def test_chat_retry_has_exactly_one_booking(self):
        msg="Book D101 T001 2035-11-08 09:30"
        a=self.chat(msg,key="retry").json()
        b=self.chat(msg,key="retry").json()
        self.assertEqual(a,b)
        self.assertEqual(self.chat("different",key="retry").status_code,409)

    def test_validation_and_adult_context(self):
        self.assertEqual(self.chat(" ").status_code,422)
        self.assertEqual(self.client.post("/api/bookings",json=self.booking(doctor_id="D102",treatment_id="T002")).status_code,422)
        r=self.chat("Book D103 T001 2035-11-08 09:30").json()
        self.assertIsNone(r["booking"])
        self.assertIn("not saved",r["reply"])
        self.assertIsNotNone(self.chat("D101").json()["booking"])

    def test_restart_retains_bookings_and_draft(self):
        self.chat("Book D101 T001")
        self.client.post("/api/bookings",json=self.booking())
        with patch.dict(os.environ,{"AI_MODE":"local"}):
            other=TestClient(create_app(self.path,DATA))
        try:
            self.assertTrue(any(b["booking_date"]=="2035-11-08" for b in other.get("/api/bookings").json()))
            r=other.post("/api/chat",json={"message":"2035-12-01 10:00","session_id":"test","request_id":"new"}).json()
            self.assertIsNotNone(r["booking"])
        finally: other.close()

    def test_llm_tool_call_contract(self):
        self.app.state.agent.mode="llm"
        response={"tool_calls":[{"function":{"name":"route_intent","arguments":json.dumps({"intent":"book","booking_action":"submit","doctor_id":"D101","treatment_id":"T001","booking_date":"2035-11-08","booking_time":"09:30"})}}]}
        with patch.object(self.app.state.agent,"llm",AsyncMock(return_value=response)) as model:
            r=self.chat("Please make this appointment").json()
        self.assertEqual(r["mode"],"llm")
        self.assertIsNotNone(r["booking"])
        self.assertTrue(model.call_args.args[1])

    def test_traditional_chinese_workflow_and_bilingual_sources(self):
        question = self.chat("我有花生過敏，可以諮詢誰？").json()
        self.assertIn("目錄沒有專門", question["reply"])
        self.assertIn("no dedicated allergy", question["reply"])
        self.assertIn("服務 / Treatment", question["reply"])
        self.assertEqual(self.chat("我的下一次預約是甚麼時候？").json()["intent"], "bookings")
        self.chat("幫我預約 D101 的一般健康檢查")
        result = self.chat("2035-11-08 09:30").json()
        self.assertIn("預約已儲存 / Booking confirmed", result["reply"])
        self.assertIn("一般健康檢查 / General Health Checkup", result["reply"])
        self.assertEqual(result["booking"]["treatment_name"], "General Health Checkup")
        self.assertEqual(result["booking"]["status_label"], "已確認 / Confirmed")
        self.assertIn("空腹 8 小時", result["booking"]["pre_treatment_instructions_zh"])
        self.assertIn("欄位格式不正確", self.client.post("/api/bookings",json=self.booking(booking_time="25:00")).json()["detail"])

    def test_traditional_retrieval_and_llm_language_instruction(self):
        self.assertTrue(retrieve(self.app.state.db, "皮膚過敏"))
        catalog = self.client.get("/api/catalog").json()
        self.assertEqual(catalog["doctors"][0]["zh"]["specialty"], "全科")
        self.app.state.agent.mode = "llm"
        route = {"tool_calls":[{"function":{"name":"route_intent","arguments":json.dumps({"intent":"knowledge"})}}]}
        with patch.object(self.app.state.agent, "llm", AsyncMock(side_effect=[route, {"content":"診所資訊 / Clinic information"}])) as model:
            self.chat("診所營業時間")
            self.assertIn("paired Traditional Chinese", model.call_args_list[1].args[0][0]["content"])

    def test_llm_failure_never_reports_success(self):
        self.app.state.agent.mode="llm"
        with patch.object(self.app.state.agent,"llm",AsyncMock(return_value={})):
            self.assertEqual(self.chat("Book an appointment").status_code,502)

    def test_chat_save_failure_retry_cannot_duplicate_booking(self):
        msg="Book D101 T001 2035-11-08 09:30"
        baseline=len(self.client.get("/api/bookings").json())
        import sqlite3
        with patch.object(self.app.state.db,"save",side_effect=sqlite3.OperationalError("disk")):
            self.assertEqual(self.chat(msg,key="same").status_code,503)
        r=self.chat(msg,key="same")
        self.assertEqual(r.status_code,200)
        self.assertEqual(len(self.client.get("/api/bookings").json()),baseline+1)

if __name__ == "__main__":
    unittest.main()
