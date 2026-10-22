"""Narrow state invariants applied after real-model routing."""
import re
from .localization import translated_value


def is_closing(message):
    words = re.sub(r'[^\w\u4e00-\u9fff]+', ' ', message.lower()).strip()
    if words in {'thanks', 'thank you', 'thanks that is all', 'thank you that is all', 'that is all', 'that s all', 'thanks that s all'}:
        return True
    return bool(re.fullmatch(r'(?:好的\s*)?(?:謝謝|谢谢)(?:\s*(?:就這樣|就这样|沒有其他問題了|没有其他问题了))?', words))


def booking_labels(catalog):
    # This single-patient demo's POST /bookings rejects T002 for adult P001.
    options = [t for t in catalog['treatments'] if t['treatment_id'] != 'T002']
    return {
        'doctor_id': '醫生 / Doctor (' + ', '.join(d['doctor_id'] + ' ' + d['full_name'] for d in catalog['doctors']) + ')',
        'treatment_id': '服務 / Treatment (' + '; '.join(t['treatment_id'] + ' ' + translated_value(t['treatment_id'], 'treatment_name', t['treatment_name']) for t in options) + ')',
        'booking_date': '日期 / Date (YYYY-MM-DD)',
        'booking_time': '診所當地時間 / Clinic-local time (HH:MM)',
    }
