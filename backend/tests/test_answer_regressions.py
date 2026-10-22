"""Failures discovered by the 64-scenario live audit."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.presentation import display_text
from app.transcripts import summarize, FIELDS

ROOT = Path(__file__).resolve().parents[2]
FULL = dict(doctor_id='D104', treatment_id='T005', booking_date='2035-12-10', booking_time='14:30')


class AnswerRegressions(unittest.TestCase):
    def setUp(self):
        folder = ROOT / 'runtime/tests'
        folder.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=folder)
        with patch.dict(os.environ, {'AI_MODE': 'local'}):
            self.app = create_app(Path(self.temp.name) / 'test.db', ROOT / 'mock-data')
        self.app.state.agent.mode = 'llm'
        self.client = TestClient(self.app)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.client.close)

    def chat(self, text, action, answer='錯誤回答 / Wrong answer', key='1'):
        call = {'tool_calls': [{'function': {'name': 'route_intent', 'arguments': json.dumps(action)}}]}
        zh, en = answer.split(' / ', 1)
        output = {'content': json.dumps({'paragraphs': [{'zh': zh, 'en': en}]})}
        with patch.object(self.app.state.agent, 'llm', AsyncMock(side_effect=[call, output])) as model:
            result = self.client.post('/api/chat', json={'message': text, 'session_id': 'regression', 'request_id': key})
        return result, model

    def test_complete_english_request_with_grounded_authorization_executes(self):
        text = 'Book Dr. James Wilson for a joint consultation on December 10, 2035 at 2:30 pm clinic local time.'
        r, model = self.chat(text, {'intent': 'book', 'booking_action': 'collect', 'authorization_quote': 'Book Dr. James Wilson', 'hold_quote': None, **FULL})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['booking']['doctor_id'], 'D104')
        self.assertEqual(model.await_count, 1)

    def test_assistant_text_cannot_authorize_write(self):
        # A fabricated quote is rejected by both bounded routing attempts.
        action = {'intent': 'book', 'booking_action': 'collect', 'authorization_quote': 'Book Dr. James Wilson', 'hold_quote': None, **FULL}
        call = {'tool_calls': [{'function': {'name': 'route_intent', 'arguments': json.dumps(action)}}]}
        with patch.object(self.app.state.agent, 'llm', AsyncMock(return_value=call)):
            r = self.client.post('/api/chat', json={'message': 'Only asking about cost', 'session_id': 'regression', 'request_id': 'quote'})
        self.assertEqual(r.status_code, 502)
        self.assertEqual(len(self.client.get('/api/bookings').json()), 2)

    def test_permission_evidence_never_releases_persisted_hold(self):
        text = 'Book Dr. James Wilson, but do not submit.'
        r, _ = self.chat(text, {'intent': 'book', 'booking_action': 'collect', 'authorization_quote': 'Book Dr. James Wilson', 'hold_quote': 'do not submit', **FULL})
        self.assertIsNone(r.json()['booking'])
        r, _ = self.chat('Change the time to 15:00.', {'intent': 'book', 'booking_action': 'collect', 'authorization_quote': 'Book Dr. James Wilson', 'hold_quote': None, 'booking_time': '15:00'}, key='2')
        self.assertIsNone(r.json()['booking'])
        self.assertTrue(self.app.state.db.state('regression')['booking_hold'])

    def test_lookup_uses_database_result_without_contradictory_rewrite(self):
        r, model = self.chat('List my appointments', {'intent': 'bookings'})
        self.assertIn('B1001', r.json()['reply'])
        self.assertIn('B1004', r.json()['reply'])
        self.assertNotIn('Wrong answer', r.json()['reply'])
        self.assertEqual(model.await_count, 1)

    def test_missing_fields_do_not_invent_additional_confirmation(self):
        r, model = self.chat('Book James', {'intent': 'book', 'booking_action': 'collect', 'doctor_id': 'D104'})
        self.assertIn('Date', r.json()['reply'])
        self.assertNotIn('confirm', r.json()['reply'].lower())
        self.assertEqual(model.await_count, 1)

    def test_clinic_only_retrieval_does_not_hide_service_inventory(self):
        r, model = self.chat('Do you have MRI? What price?', {'intent': 'knowledge', 'search_query': 'C001'}, '目錄沒有列出 MRI。 / MRI is not listed.')
        system = model.call_args_list[-1].args[0][0]['content']
        evidence, _ = json.JSONDecoder().raw_decode(system.split('Evidence: ', 1)[1])
        self.assertEqual(len(evidence['sources']), 1)
        self.assertEqual(len(evidence['catalog_inventory']['treatments']), 5)
        self.assertEqual(evidence['catalog_inventory']['treatments'][0]['price_usd'], 150)

    def test_display_normalization_preserves_ids_names_numbers(self):
        text = r'张医师（Dr. Michael Chang）<br>它们会说普通话。\nD102 $180 14:30'
        result = display_text(text, [{'full_name': 'Dr. Michael Chang'}])
        self.assertEqual(result, 'Dr. Michael Chang\n它們會說普通話。\nD102 $180 14:30')


class SummaryPresentationRegression(unittest.IsolatedAsyncioTestCase):
    async def test_summary_display_is_traditional_but_evidence_remains_verbatim(self):
        evidence = {k: [] for k in FIELDS}
        evidence['chief_complaint'] = ['头痛两天']
        args = {**dict.fromkeys(FIELDS), 'chief_complaint': r'头痛两天。\nHeadache for two days.', 'evidence': evidence}
        result = {'tool_calls': [{'function': {'name': 'summarize_transcript', 'arguments': json.dumps(args)}}]}
        with patch('app.transcripts.complete', AsyncMock(return_value=(result, {'tool': 'LLM summarize_transcript', 'status': 'ok'}))):
            answer = await summarize('病人：头痛两天')
        self.assertEqual(answer['summary']['chief_complaint'], '頭痛兩天。\nHeadache for two days.')
        self.assertEqual(answer['evidence']['chief_complaint'], ['头痛两天'])
