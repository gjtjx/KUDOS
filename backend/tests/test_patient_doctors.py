"""Relationship queries must not infer assignment, dump bookings or mutate drafts."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import create_app
from app.db import Database
from app.patient_doctors import identity_scope, relationships, answer
from app.knowledge import retrieve_grounded

ROOT = Path(__file__).resolve().parents[2]


class DoctorRelationshipTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'runtime/tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.path = Path(self.temp.name) / 'test.db'
        with patch.dict(os.environ, {'AI_MODE': 'local'}):
            self.app = create_app(self.path, ROOT / 'mock-data')
        self.client = TestClient(self.app)
        self.db = self.app.state.db
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.client.close)
        self.counter = 0

    def turn(self, text, action=None):
        self.counter += 1
        body = {'message': text, 'session_id': 'doctors', 'request_id': str(self.counter)}
        if action is None:
            r = self.client.post('/api/chat', json=body)
        else:
            self.app.state.agent.mode = 'llm'
            call = {'tool_calls': [{'function': {'name': 'route_intent', 'arguments': json.dumps(action)}}]}
            with patch.object(self.app.state.agent, 'llm', AsyncMock(return_value=call)) as llm:
                r = self.client.post('/api/chat', json=body)
                self.assertEqual(llm.await_count, 1 if r.status_code == 200 else 2)
        return r

    def test_local_primary_and_ambiguous_doctor_are_answered_directly(self):
        for text in ('我的主治医生是哪位？', '我的醫生是？', 'Who is my doctor?', 'Who is my primary care doctor?'):
            with self.subTest(text=text):
                r = self.turn(text).json()
                self.assertEqual(r['intent'], 'patient_doctors')
                self.assertIn('do not identify an assigned', r['reply'])
                self.assertIn('Dr. Sarah Jenkins', r['reply'])
                self.assertIn('H9002', r['reply'])
                self.assertNotIn('B1004', r['reply'])
                self.assertNotIn('Booking history:', r['reply'])
                self.assertIsNone(r['booking'])

    def test_identity_guard_corrects_booking_list_misroute_after_real_routing(self):
        r = self.turn('我的医生是？', {'intent': 'bookings'}).json()
        self.assertEqual(r['intent'], 'patient_doctors')
        self.assertIn('Do you mean', r['reply'])
        self.assertIn('GET /api/patient-doctors', [t['tool'] for t in r['tool_trace']])

    def test_specific_booking_includes_clinic_without_other_bookings(self):
        r = self.turn('B1001 在哪家診所？', {'intent': 'bookings'}).json()
        self.assertIn('Metro Care Health Clinic', r['reply'])
        self.assertIn('B1001', r['reply'])
        self.assertNotIn('B1004', r['reply'])
        self.assertEqual(len(self.client.get('/api/bookings').json()), 2)
        listed = self.turn('Show my bookings', {'intent': 'bookings'}).json()
        self.assertIn('B1001', listed['reply'])
        self.assertIn('B1004', listed['reply'])

    def test_other_patient_booking_id_returns_no_matching_record(self):
        r = self.turn('查 B1002', {'intent': 'bookings'}).json()
        self.assertIn('No matching appointment for you', r['reply'])
        self.assertNotIn('B1001', r['reply'])

    def test_foreign_patient_misrouting_is_rejected_without_booking_dump_or_write(self):
        before = self.client.get('/api/bookings').json()
        for intent in ('bookings', 'book'):
            with self.subTest(intent=intent):
                r = self.turn('查 P002 的病史和預約', {'intent': intent, 'booking_action': 'collect'}).json()
                self.assertIn('only the current patient P001', r['reply'])
                self.assertNotIn('B1001', r['reply'])
                self.assertEqual(self.client.get('/api/bookings').json(), before)

    def test_contact_name_allowed_without_allowing_arbitrary_english(self):
        from app.generation import validate_answer, answer_payload
        catalog = {t: self.db.rows('SELECT * FROM '+t) for t in ('clinics','doctors','treatments')}
        content = json.dumps(answer_payload('您的緊急聯絡人是 Jane Doe。', 'Your emergency contact is Jane Doe.'))
        with self.assertRaises(ValueError):
            validate_answer(content, catalog)
        self.assertIn('Jane Doe', validate_answer(content, catalog, allowed_literals=('Jane Doe',)))
        email = json.dumps(answer_payload('您的電子郵件是 john.doe@example.com。', 'Your email is john.doe@example.com.'))
        self.assertIn('john.doe@example.com', validate_answer(email, catalog, allowed_literals=('john.doe@example.com',)))
        with self.assertRaises(ValueError):
            validate_answer(json.dumps(answer_payload('您的聯絡人是 Invented Person。', 'Invented Person.')), catalog, allowed_literals=('Jane Doe',))

    def test_clinical_history_is_not_rendered_as_appointment_list(self):
        self.app.state.agent.mode = 'llm'
        routing = {'tool_calls': [{'function': {'name': 'route_intent', 'arguments': json.dumps({'intent':'bookings'})}}]}
        answer = {'content': json.dumps({'paragraphs':[{'zh':'您的最近紀錄是年度健康檢查，未記錄咳嗽發燒。','en':'Your latest record is an annual checkup; cough and fever are not recorded.'}]})}
        with patch.object(self.app.state.agent, 'llm', AsyncMock(side_effect=[routing, answer])):
            r = self.client.post('/api/chat', json={'message':'我上次是不是咳嗽發燒三天？','session_id':'clinical','request_id':'0'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['intent'],'knowledge')
        self.assertNotIn('B1001',r.json()['reply'])

    def test_identity_guard_prevents_hallucinated_booking_execution(self):
        before = self.client.get('/api/bookings').json()
        r = self.turn('我的主治医生是哪位？', {'intent': 'book', 'booking_action': 'submit', 'doctor_id': 'D104', 'treatment_id': 'T005', 'booking_date': '2035-12-01', 'booking_time': '10:00'}).json()
        self.assertEqual(r['intent'], 'patient_doctors')
        self.assertEqual(self.client.get('/api/bookings').json(), before)

    def test_model_handles_identity_phrasing_outside_standalone_patterns(self):
        r = self.turn('Which physician treated me at my most recent visit?', {'intent': 'patient_doctors', 'doctor_scope': 'history'}).json()
        self.assertIn('H9002', r['reply'])
        self.assertNotIn('B1001', r['reply'])

    def test_malformed_relation_scope_is_rejected_without_writes(self):
        for action in ({'intent': 'patient_doctors'}, {'intent': 'patient_doctors', 'doctor_scope': 'all_patients'}, {'intent': 'knowledge', 'doctor_scope': 17}):
            self.assertEqual(self.turn('Who treated me?', action).status_code, 502)
        self.assertEqual(len(self.client.get('/api/bookings').json()), 2)

    def test_relation_query_preserves_held_draft_and_subsequent_execution(self):
        full = {'doctor_id': 'D103', 'treatment_id': 'T003', 'booking_date': '2035-11-09', 'booking_time': '10:15'}
        self.turn('Book Elena, but hold', {'intent': 'book', 'booking_action': 'hold', **full})
        before = self.db.state('doctors')
        r = self.turn('我的医生是？', {'intent': 'bookings'}).json()
        after = self.db.state('doctors')
        self.assertEqual(after['draft'], before['draft'])
        self.assertEqual((after['active'], after['booking_hold']), (True, True))
        self.assertIsNone(r['booking'])
        r = self.turn('Confirm now', {'intent': 'book', 'booking_action': 'confirm'}).json()
        self.assertEqual(r['booking']['doctor_id'], 'D103')

    def test_draft_doctor_is_distinct_from_next_visit_doctor(self):
        self.turn('Book Elena', {'intent': 'book', 'booking_action': 'collect', 'doctor_id': 'D103', 'treatment_id': 'T003'})
        r = self.turn('我剛選的醫生是誰？', {'intent': 'patient_doctors', 'doctor_scope': 'draft'}).json()
        self.assertIn('Dr. Elena Rostova', r['reply'])
        self.assertIn('unsubmitted', r['reply'])
        self.assertNotIn('Dr. Sarah Jenkins', r['reply'])

    def test_no_draft_doctor_is_not_guessed(self):
        r = self.turn('我的草稿裡的醫生是誰？').json()
        self.assertIn('No doctor is selected', r['reply'])

    def test_relation_endpoint_is_patient_scoped_and_authoritative(self):
        self.assertEqual(self.client.get('/api/patient-doctors?patient_id=P002').status_code, 403)
        facts = self.client.get('/api/patient-doctors').json()
        self.assertIsNone(facts['primary_assignment'])
        self.assertEqual([h['record_id'] for h in facts['history']], ['H9002'])
        self.assertNotIn('H9001', json.dumps(facts))
        self.assertEqual(self.db.profile()['history'][0]['clinic_name'], 'Metro Care Health Clinic')

    def test_upcoming_doctor_follows_live_database_not_historical_doctor(self):
        with self.db.connect() as c:
            c.execute("UPDATE patient_bookings SET status='Cancelled' WHERE booking_id='B1001'")
            c.execute("UPDATE patient_bookings SET booking_date='2095-11-15' WHERE booking_id='B1004'")
        r = self.turn('我的下一次預約的醫生是誰？').json()
        self.assertIn('Dr. James Wilson', r['reply'])
        self.assertNotIn('Dr. Sarah Jenkins', r['reply'])

    def test_next_visit_answer_includes_joined_service_and_clinic(self):
        r = self.turn('我下一次預約是甚麼？', {'intent': 'patient_doctors', 'doctor_scope': 'next'}).json()
        self.assertIn('General Health Checkup', r['reply'])
        self.assertIn('Metro Care Health Clinic', r['reply'])
        self.assertIn('T001', r['reply'])

    def test_empty_and_other_patient_records_are_not_inferred(self):
        catalog = {'doctors': [{'doctor_id': 'D101', 'full_name': 'Dr. Sarah Jenkins'}]}
        facts = relationships({'patient_id': 'P001', 'history': [{'patient_id': 'P002', 'doctor_id': 'D101', 'record_id': 'other', 'visit_date': '2026-01-01'}]}, [], catalog, {})
        self.assertEqual(facts['history'], [])
        self.assertIn('no recorded past-visit', answer('history', facts)[0])
        self.assertIn('no upcoming confirmed', answer('next', facts)[0])
        self.assertIn('no upcoming confirmed', answer('overview', facts)[0])
        self.assertIn('do not identify an assigned', answer('primary', facts)[0])

    def test_past_and_cancelled_bookings_cannot_choose_next_doctor(self):
        catalog = {'doctors': []}
        b = {'patient_id': 'P001', 'booking_id': 'old', 'doctor_id': 'D101', 'doctor_name': 'Sarah', 'booking_date': '2000-01-01', 'booking_time': '09:00', 'timezone': 'America/New_York', 'status': 'Confirmed'}
        facts = relationships({'patient_id': 'P001', 'history': []}, [b, {**b, 'patient_id': 'P002', 'booking_date': '2099-01-01'}], catalog, {}, datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertIsNone(facts['next_visit'])

    def test_bridge_seed_foreign_keys_and_restart_preserve_changes(self):
        self.assertEqual(sum(map(len, self.db.treatment_doctors().values())), 6)
        with self.assertRaises(sqlite3.IntegrityError), self.db.connect() as c:
            c.execute("INSERT INTO doctor_treatments VALUES('D999','T001')")
        with self.db.connect() as c:
            c.execute("DELETE FROM doctor_treatments WHERE doctor_id='D102' AND treatment_id='T004'")
        Database(self.path, ROOT / 'mock-data')
        self.assertEqual(self.db.treatment_doctors()['T004'], ['D101'])

    def test_retrieval_and_booking_validation_share_database_bridge(self):
        with self.db.connect() as c:
            c.execute("DELETE FROM doctor_treatments WHERE doctor_id='D103' AND treatment_id='T003'")
        sources = retrieve_grounded(self.db, 'T003')
        self.assertNotIn('D103', [s['id'] for s in sources])
        r = self.client.post('/api/bookings', json={'doctor_id': 'D103', 'treatment_id': 'T003', 'booking_date': '2035-12-01', 'booking_time': '10:00', 'request_id': 'bridge'})
        self.assertEqual(r.status_code, 422)

    def test_empty_bridge_is_seeded_on_initialization(self):
        with self.db.connect() as c:
            c.execute('DELETE FROM doctor_treatments')
        Database(self.path, ROOT / 'mock-data')
        self.assertEqual(len(self.db.treatment_doctors()), 5)

    def test_standalone_match_does_not_intercept_attributes_or_mixed_commands(self):
        for text in ('我的醫生會說中文嗎？', '我的醫生是誰？幫我預約 D101 T001', 'Who is my doctor? Book Sarah tomorrow.', 'Sarah is my doctor', 'Who is treating my rash?'):
            self.assertIsNone(identity_scope(text))
        for text, scope in [('Who is my attending doctor?', 'primary'), ('我的家庭醫師是哪位？', 'primary'), ('Who is my previous doctor?', 'history'), ('我上次看診的醫生是誰？', 'history'), ('Who is my next visit doctor?', 'next'), ('Who is my selected doctor?', 'draft')]:
            self.assertEqual(identity_scope(text), scope)


if __name__ == '__main__':
    unittest.main()
