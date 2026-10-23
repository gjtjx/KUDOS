"""Opt-in real-provider checks for patient/doctor relationship questions."""
import expanded_acceptance as audit

SCENARIOS = [
    ('p01_primary_simplified', [('我的主治医生是哪位？', 0, {})]),
    ('p02_primary_traditional', [('我的主治醫師是誰？', 0, {})]),
    ('p03_ambiguous_short', [('我的医生是？', 0, {})]),
    ('p04_ambiguous_english', [('Who is my doctor?', 0, {})]),
    ('p05_primary_english', [('Who is my primary care doctor?', 0, {})]),
    ('p06_history_natural', [('Which physician treated me at my most recent visit?', 0, {})]),
    ('p07_next_doctor', [('我下次看診的醫生是誰？', 0, {})]),
    ('p08_no_draft', [('我的草稿裡的醫生是誰？', 0, {})]),
    ('p09_draft_interruption', [
        ('我要預約 D103 的 T003，先不要提交。', 0, {'draft': {'doctor_id': 'D103', 'treatment_id': 'T003'}}),
        ('我剛選的醫生是誰？', 0, {'draft': {'doctor_id': 'D103', 'treatment_id': 'T003'}}),
        ('我的主治医生是哪位？', 0, {'draft': {'doctor_id': 'D103', 'treatment_id': 'T003'}}),
        ('2035-11-09 10:15，現在確認提交。', 1, {'doctor_id': 'D103', 'treatment_id': 'T003'}),
    ]),
    ('p10_doctor_attribute', [
        ('我的医生是？', 0, {}),
        ('我指下一次預約的 Sarah，她會說哪些語言？', 0, {}),
    ]),
]


def review_response(name, message, result, app):
    reply = result['reply']
    if name == 'p10_doctor_attribute' and '語言' in message:
        yield 'answers_requested_language', 'English' in reply and 'Spanish' in reply
        yield 'no_booking_dump', 'B1004' not in reply
        return
    if name == 'p09_draft_interruption' and ('我要預約' in message or '現在確認提交' in message):
        return
    yield 'relationship_intent', result['intent'] == 'patient_doctors'
    yield 'database_relationship_tool', any(t['tool'] == 'GET /api/patient-doctors' for t in result['tool_trace'])
    yield 'no_booking_dump', 'B1004' not in reply
    if name == 'p08_no_draft':
        yield 'empty_draft_not_inferred', 'No doctor is selected' in reply
    elif '剛選' in message:
        yield 'draft_not_assignment', 'Dr. Elena Rostova' in reply and 'unsubmitted' in reply
    else:
        yield 'doctor_identity_correct', 'Dr. Sarah Jenkins' in reply
        if name == 'p07_next_doctor':
            yield 'joined_service_and_clinic', 'General Health Checkup' in reply and 'Metro Care Health Clinic' in reply
        if name not in ('p06_history_natural', 'p07_next_doctor'):
            yield 'assignment_not_inferred', 'do not identify an assigned' in reply
            yield 'history_evidence', 'H9002' in reply
        if name == 'p06_history_natural':
            yield 'history_not_booking', 'H9002' in reply and 'B1001' not in reply
    if name == 'p09_draft_interruption':
        state = app.state.db.state(name)
        yield 'hold_preserved', state.get('booking_hold') is True and state['draft'].get('doctor_id') == 'D103'


if __name__ == '__main__':
    audit.SCENARIOS = SCENARIOS
    audit.REVIEW_RESPONSE = review_response
    audit.main()
