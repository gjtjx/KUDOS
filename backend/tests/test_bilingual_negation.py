"""A correct caution was rejected after JSON repair in a real provider run."""
import json
import unittest
from unittest.mock import AsyncMock
from app.generation import answer_payload, generate_answer, unsupported_language_claim, validate_answer
from app.llm import ProviderError

CATALOG={'doctors':[{'full_name':'Dr. Sarah Jenkins','languages_spoken':'English, Spanish'}]}


class BilingualNegationTests(unittest.IsolatedAsyncioTestCase):
    def test_negated_inference_is_valid_in_both_languages(self):
        for zh,en in [
            ('這不代表她不會說其他語言。','This does not mean she cannot speak other languages.'),
            ('未列出普通話不表示她不能說普通話。',"This does not imply that she can't speak Mandarin."),
            ('不能據此斷定其他語言能力。',"This doesn't prove the doctor only speaks English."),
        ]:
            with self.subTest(en=en):self.assertIn(en,validate_answer(json.dumps(answer_payload(zh,en)),CATALOG))

    def test_actual_negative_claims_remain_rejected(self):
        for text in ('She cannot speak Mandarin.','She does not speak Mandarin.','She only speaks English.','她不會說普通話。','她只會說英語。'):
            with self.subTest(text=text):self.assertTrue(unsupported_language_claim(text))

    def test_exception_does_not_hide_separate_or_contrasting_claim(self):
        for text in (
            'This does not mean she cannot speak other languages. She cannot speak Mandarin.',
            'This does not mean anything, but she cannot speak Mandarin.',
            'This does not prove the records are complete; she only speaks English.',
            '不代表她不能說其他語言。但她不會說普通話。',
            '不表示其他結論，但她不會說普通話。',
        ):
            with self.subTest(text=text):self.assertTrue(unsupported_language_claim(text))

    async def test_original_failure_repairs_once_then_renders_valid_caution(self):
        good=answer_payload('所列語言是英語與西班牙語；這不代表她不會說其他語言。',
                            'The listed languages are English and Spanish; this does not mean she cannot speak other languages.')
        model=AsyncMock(side_effect=[{'content':'plain paired text'},{'content':json.dumps(good)}])
        answer=await generate_answer(model,[{'role':'system','content':'Use source facts.'}],CATALOG)
        self.assertIn('does not mean she cannot speak',answer)
        self.assertEqual(model.await_count,2)

    async def test_invalid_actual_claim_still_fails_after_bounded_repair(self):
        model=AsyncMock(return_value={'content':json.dumps(answer_payload('她不會說普通話。','She cannot speak Mandarin.'))})
        with self.assertRaises(ProviderError):await generate_answer(model,[{'role':'system','content':'Use source facts.'}],CATALOG)
        self.assertEqual(model.await_count,2)
