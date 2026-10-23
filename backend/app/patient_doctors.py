"""Patient-doctor relationships are database facts, not catalog similarity."""
import re
from opencc import OpenCC
from .answers import upcoming_bookings
from .localization import TRANSLATIONS

SCOPES = ('primary', 'overview', 'history', 'next', 'draft')
_simplify = OpenCC('t2s')


def identity_scope(message):
    """Recognize only standalone identity questions; mixed requests use the router."""
    q = _simplify.convert(message).lower().strip()
    q = re.sub(r'[？?！!。.,，\s]+$', '', q)
    q = re.sub(r'^(?:请问|想问一下|请告诉我|could you tell me |please tell me )', '', q)
    chinese = re.fullmatch(r'(?:我的|我)(主治|家庭|固定|负责|上次看诊的|上次就诊的|上次的|下次看诊的|下次就诊的|下次的|下一次预约的|这次草稿的|草稿里的|刚选的)?(?:医生|医师)(?:是|有|叫)?(?:谁|哪位|哪一位|哪几位)?', q)
    english = re.fullmatch(r'(?:who (?:is|are) my|who\'s my|who is the doctor for my) (?:(primary care|primary|family|attending|previous|last visit|next appointment|next visit|draft|selected) )?doctors?', q)
    if not chinese and not english:
        return None
    label = (chinese or english)[1] or ''
    if label in ('主治', '家庭', '固定', '负责', 'primary care', 'primary', 'family', 'attending'):
        return 'primary'
    if label.startswith('上次') or label in ('previous', 'last visit'):
        return 'history'
    if label.startswith(('下次', '下一次')) or label in ('next appointment', 'next visit'):
        return 'next'
    if label in ('这次草稿的', '草稿里的', '刚选的', 'draft', 'selected'):
        return 'draft'
    return 'overview'


def relationships(profile, bookings, catalog, draft, now=None):
    doctors = {d['doctor_id']: d for d in catalog['doctors']}
    history = []
    for row in sorted(profile.get('history', []), key=lambda r: r['visit_date'], reverse=True):
        # Never include another patient's historical record, even in a bad context.
        if row['patient_id'] == profile['patient_id'] and row['doctor_id'] in doctors:
            history.append({**{k: row[k] for k in ('record_id', 'doctor_id', 'visit_date')},
                            'doctor_name': doctors[row['doctor_id']]['full_name']})
    upcoming = upcoming_bookings([b for b in bookings if b['patient_id'] == profile['patient_id']], now)
    next_visit = ({k: upcoming[0][k] for k in ('booking_id', 'doctor_id', 'doctor_name', 'booking_date', 'booking_time', 'timezone')} if upcoming else None)
    if next_visit:
        next_visit.update({k: upcoming[0][k] for k in ('treatment_id', 'treatment_name', 'clinic_name') if k in upcoming[0]})
    selected = doctors.get(draft.get('doctor_id'))
    return {'primary_assignment': None, 'assignment_note': 'The supplied schema has no assigned primary/attending doctor field. Do not infer assignment from a specialty, past visit, booking or draft.',
            'history': history, 'next_visit': next_visit,
            'draft_doctor': {k: selected[k] for k in ('doctor_id', 'full_name')} if selected else None}


def answer(scope, facts):
    paragraphs, sources = [], []
    if scope in ('primary', 'overview'):
        paragraphs.append('現有資料未指定你的主治／家庭醫生，不能把歷史就診或預約醫生直接視為主治醫生。\nYour records do not identify an assigned primary or attending doctor; a past visit or appointment does not establish that assignment.')
    if scope in ('primary', 'overview', 'history'):
        if facts['history']:
            h = facts['history'][0]
            paragraphs.append(f"最近一筆就診紀錄的醫生是 {h['doctor_name']}（{h['doctor_id']}），日期 {h['visit_date']}（patient_treatment_history.csv，{h['record_id']}）。\nThe doctor in your most recent recorded visit was {h['doctor_name']} ({h['doctor_id']}) on {h['visit_date']} (patient_treatment_history.csv, {h['record_id']}).")
            sources.append({'source': 'patient_treatment_history.csv', 'id': h['record_id'], 'data': h})
        elif scope == 'history':
            paragraphs.append('目前沒有你的歷史就診醫生紀錄。\nThere is no recorded past-visit doctor for you.')
    if scope in ('primary', 'overview', 'next'):
        b = facts['next_visit']
        if b:
            zh_details = en_details = ''
            if all(b.get(k) for k in ('treatment_id', 'treatment_name', 'clinic_name')):
                treatment = TRANSLATIONS.get(b['treatment_id'], {}).get('treatment_name', b['treatment_name'])
                zh_details = f" 服務：{treatment}（{b['treatment_id']}）；診所：{b['clinic_name']}。"
                en_details = f" Service: {b['treatment_name']} ({b['treatment_id']}); clinic: {b['clinic_name']}."
            paragraphs.append(f"下一次已確認預約的醫生是 {b['doctor_name']}（{b['doctor_id']}），{b['booking_date']} {b['booking_time']}（{b['timezone']}；GET /api/bookings，{b['booking_id']}）。{zh_details}\nYour next confirmed appointment is with {b['doctor_name']} ({b['doctor_id']}) on {b['booking_date']} at {b['booking_time']} ({b['timezone']}; GET /api/bookings, {b['booking_id']}).{en_details}")
            sources.append({'source': 'GET /api/bookings', 'id': b['booking_id'], 'data': b})
        elif scope in ('overview', 'next'):
            paragraphs.append('目前沒有未來的已確認預約，因此無法指定下一次就診醫生。\nThere is no upcoming confirmed appointment, so no next-visit doctor can be identified.')
    if scope == 'draft':
        d = facts['draft_doctor']
        paragraphs.append(f"草稿目前選擇 {d['full_name']}（{d['doctor_id']}）；這是未提交的選擇，不是主治醫生指定。\nThe draft currently selects {d['full_name']} ({d['doctor_id']}); this is an unsubmitted selection, not a primary-doctor assignment." if d else '目前的預約草稿尚未選擇醫生。\nNo doctor is selected in the current booking draft.')
        if d:
            sources.append({'source': 'doctors.csv', 'id': d['doctor_id'], 'data': d})
    if scope == 'overview':
        paragraphs.append('你想問的是下一次就診醫生，還是過去看過的醫生？\nDo you mean the doctor for your next visit or a doctor you saw previously?')
    return '\n\n'.join(paragraphs), sources
