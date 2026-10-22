"""State and language regressions found by the complete 64-scenario run."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.generation import validate_answer, generate_answer, answer_payload
from app.conversation import is_closing, booking_labels
from app.presentation import display_text
from app.llm import ProviderError

ROOT = Path(__file__).resolve().parents[2]
FULL = dict(doctor_id='D104', treatment_id='T005', booking_date='2035-12-10', booking_time='14:30')


class RemainingAPIRegressions(unittest.TestCase):
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
        self.counter = 0

    def turn(self, text, action):
        self.counter += 1
        call = {'tool_calls': [{'function': {'name': 'route_intent', 'arguments': json.dumps(action)}}]}
        with patch.object(self.app.state.agent, 'llm', AsyncMock(return_value=call)) as model:
            result = self.client.post('/api/chat', json={'message': text, 'session_id': 'remaining', 'request_id': str(self.counter)})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(model.await_count, 1)  # Real routing still precedes the invariant.
        return result.json()

    def test_closing_cannot_reopen_completed_booking_even_if_router_says_book(self):
        self.turn('Book James now', {'intent': 'book', 'booking_action': 'submit', **FULL})
        before = self.client.get('/api/bookings').json()
        result = self.turn('Thanks, that is all.', {'intent': 'book', 'booking_action': 'submit', **FULL})
        self.assertEqual(result['intent'], 'knowledge')
        self.assertEqual(result['draft'], {})
        self.assertFalse(self.app.state.db.state('remaining')['active'])
        self.assertEqual(self.client.get('/api/bookings').json(), before)

    def test_closing_preserves_an_active_held_draft(self):
        self.turn('Hold the draft', {'intent': 'book', 'booking_action': 'hold', **FULL})
        before = self.app.state.db.state('remaining')
        self.turn('謝謝', {'intent': 'cancel_draft'})
        after = self.app.state.db.state('remaining')
        self.assertEqual(after['draft'], before['draft'])
        self.assertTrue(after['active'])
        self.assertTrue(after['booking_hold'])

    def test_thanks_with_new_booking_instruction_is_not_a_pure_closing(self):
        result = self.turn('Thanks, book James now.', {'intent': 'book', 'booking_action': 'submit', **FULL})
        self.assertIsNotNone(result['booking'])

    def test_missing_service_prompt_never_offers_pediatric_vaccine(self):
        result = self.turn('I want to book', {'intent': 'book', 'booking_action': 'collect'})
        self.assertNotIn('T002', result['reply'])
        self.assertIn('T004', result['reply'])


class BilingualValidationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.catalog = {'doctors': [{'full_name': 'Dr. Sarah Jenkins'}], 'clinics': [], 'treatments': []}

    def render(self, zh, en):
        return validate_answer(json.dumps(answer_payload(zh, en)), self.catalog)

    def test_missing_or_repeated_chinese_english_is_rejected(self):
        for text in ('plain text', '{"paragraphs":[]}', json.dumps(answer_payload('目錄沒有列出。', '目錄沒有列出。'))):
            with self.assertRaises(ValueError):
                validate_answer(text, self.catalog)

    def test_unlisted_language_is_not_a_negative_ability_claim(self):
        with self.assertRaisesRegex(ValueError, 'negative_language'):
            self.render('她不會說普通話。', 'She does not speak Mandarin.')
        self.assertIn('not listed', self.render('未列出普通話，請向診所確認。', 'Mandarin is not listed; confirm with the clinic.'))

    def test_catalog_names_allowed_but_stray_english_words_rejected(self):
        self.assertIn('Dr. Sarah Jenkins', self.render('Dr. Sarah Jenkins 的診金已列出。', 'The fee is listed.'))
        with self.assertRaisesRegex(ValueError, 'untranslated_word'):
            self.render('服務 listed 價格為兩百美元。', 'The listed service price is USD 200.')

    def test_unsolicited_future_confirmation_requirement_rejected(self):
        with self.assertRaisesRegex(ValueError, 'confirmation_requirement'):
            self.render('草稿需要確認後提交。', 'The draft requires explicit confirmation before submission.')

    async def test_invalid_bilingual_counterpart_repaired_once(self):
        bad = {'content': json.dumps(answer_payload('沒有列出該服務。', '沒有列出該服務。'))}
        good = {'content': json.dumps(answer_payload('沒有列出該服務。', 'The service is not listed.'))}
        model = AsyncMock(side_effect=[bad, good])
        reply = await generate_answer(model, [{'role': 'system', 'content': 'Use evidence.'}], self.catalog)
        self.assertIn('The service is not listed.', reply)
        self.assertEqual(model.await_count, 2)

    async def test_repair_is_bounded_without_local_fallback(self):
        model = AsyncMock(return_value={'content': 'invalid'})
        with self.assertRaisesRegex(ProviderError, 'invalid_bilingual_answer'):
            await generate_answer(model, [{'role': 'system', 'content': 'Use evidence.'}], self.catalog)
        self.assertEqual(model.await_count, 2)

    def test_contextual_homographs_do_not_corrupt_existing_traditional_text(self):
        result = display_text('只有抽血，只是查詢。此系统及此係統。一隻有斑點的貓。')
        self.assertEqual(result, '只有抽血，只是查詢。此系統及此系統。一隻有斑點的貓。')

    def test_pure_closing_patterns_are_anchored(self):
        self.assertTrue(is_closing("Thanks, that's all."))
        self.assertFalse(is_closing('Thanks, can you tell me the price?'))
