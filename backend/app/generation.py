"""Bounded, validated bilingual generation. Invalid output is never rendered."""
import json
import re
from .llm import ProviderError
from .presentation import display_text


def answer_payload(zh, en):
    return {'paragraphs': [{'zh': zh, 'en': en}]}


def validate_answer(content, catalog, on_hold=False, allowed_literals=()):
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        raise ValueError('answer_must_be_json') from None
    if not isinstance(data, dict) or set(data) != {'paragraphs'}:
        raise ValueError('invalid_answer_schema')
    paragraphs = data['paragraphs']
    if not isinstance(paragraphs, list) or not 1 <= len(paragraphs) <= 4:
        raise ValueError('invalid_paragraph_count')
    # Only actual names/values and conventional identifiers may remain in zh.
    literals = {'MRI', 'USD', 'AM', 'PM', 'GET /api/bookings', 'P001', 'John Doe', 'patients.csv', 'patient_treatment_history.csv', 'America/New_York', 'America/Los_Angeles'}
    literals.update(allowed_literals)
    for records in catalog.values():
        for row in records:
            for value in row.values():
                if isinstance(value, str):
                    literals.add(value)
                    literals.update(v.strip() for v in value.split(','))
    rendered = []
    for pair in paragraphs:
        if not isinstance(pair, dict) or set(pair) != {'zh', 'en'} or any(not isinstance(v, str) or not v.strip() or len(v) > 5000 for v in pair.values()):
            raise ValueError('invalid_bilingual_pair')
        zh = ' '.join(display_text(pair['zh'], catalog['doctors']).split())
        en = ' '.join(pair['en'].split())
        if len(re.findall(r'[\u4e00-\u9fff]', zh)) < 2 or not re.search(r'[A-Za-z]{3}', en) or re.search(r'[\u4e00-\u9fff]', en):
            raise ValueError('missing_language_counterpart')
        residue = zh
        for value in sorted(literals, key=len, reverse=True):
            if value:
                residue = residue.replace(value, '')
        residue = re.sub(r'\b[BCDTPH]\d+\b|\b(?:clinics|doctors|treatments)\.csv\b', '', residue)
        if re.search(r'[A-Za-z]{3}', residue):
            raise ValueError('untranslated_word_in_chinese')
        if re.search(r"(?:does not|doesn't|cannot|can't|only)\s+speak|只會(?:說|講)|不(?:會|能)(?:說|講)", zh + '\n' + en, re.I):
            raise ValueError('unsupported_negative_language_claim')
        if not on_hold and (re.search(r'(?:draft|booking|appointment).{0,80}(?:require|need|must).{0,60}(?:confirm|approv)', en, re.I) or re.search(r'(?:需|必須|等待).{0,14}(?:確認|批准).{0,10}(?:提交|送出)', zh)):
            raise ValueError('invented_confirmation_requirement')
        rendered.append(zh + '\n' + en)
    return '\n\n'.join(rendered)


async def generate_answer(llm, messages, catalog, on_hold=False, allowed_literals=()):
    instruction = (
        '\nOutput ONLY a JSON object: {"paragraphs":[{"zh":"繁體中文段落","en":"Full English counterpart"}]}. '
        'Use 1 to 4 pairs. Each en must fully translate its zh; never repeat Chinese in en. '
        'Each zh must be entirely Chinese except exact catalog names, addresses, IDs, filenames, MRI and USD. Never leave words such as listed or Catalog in Chinese prose. '
        'Preserve exact original doctor/clinic and patient/contact names. For emergency-contact questions include the recorded name, relationship and phone; do not omit the name to satisfy language formatting. A list of spoken languages records listed abilities; it is not proof that any unlisted language cannot be spoken. Say not listed and confirm with clinic, never does not speak or only speaks. '
        'Do not discuss hypothetical future booking approval steps. An authorized complete unheld draft is submitted automatically; only an explicit user hold requires confirmation. '
        'Use ordinary contextual Chinese spelling: 只有, 只是, 系統. No HTML, escaped linebreaks or Markdown fences. '
        'Use short paired paragraphs with the same facts and citations in each language.'
    )
    messages = [{'role': 'system', 'content': messages[0]['content'] + instruction}, *messages[1:]]
    for attempt in range(2):
        result = await llm(messages)
        try:
            return validate_answer(result.get('content'), catalog, on_hold, allowed_literals)
        except ValueError as error:
            if attempt:
                raise ProviderError('invalid_bilingual_answer') from None
            messages += [{'role': 'assistant', 'content': result.get('content') or ''},
                         {'role': 'user', 'content': 'Validation failed: ' + str(error) + '. Regenerate the JSON once. Include full English counterparts, preserve catalog names, do not infer negative abilities from absent data, and omit invented approval steps.'}]
