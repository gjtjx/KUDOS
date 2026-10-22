"""Opt-in common questions; reuses isolated databases and reports from expanded acceptance."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import expanded_acceptance as audit

audit.SCENARIOS = [
    ('visit_flow', [('我到醫院的流程是怎樣？', 0, {})]),
    ('hours', [('Metro Care 星期日有開門嗎？星期六呢？', 0, {})]),
    ('contact', [('Sunset Wellness Center 在哪裡？電話多少？', 0, {})]),
    ('language', [('Sarah 醫生會說中文嗎？', 0, {})]),
    ('skin_fee', [('皮膚科服務 T003 和 Elena 醫生分別收多少錢？總共一定要付 420 美元嗎？', 0, {})]),
    ('fasting', [('我做一般健康檢查一定要空腹嗎？', 0, {})]),
    ('allergy', [('我對花生過敏，有專門的過敏檢查可以預約嗎？先不要預約。', 0, {})]),
    ('next_booking', [('我下一次預約是甚麼時候？哪位醫生？', 0, {})]),
    ('cancel_existing', [('幫我取消已確認的 B1001。', 0, {})]),
    ('reschedule_existing', [('把 B1001 改到 2035 年 12 月 8 日上午十點。', 0, {})]),
    ('unsupported_mri', [('你們有 MRI 嗎？多少錢？', 0, {})]),
    ('unknown_insurance', [('我的保險可以全額報銷嗎？', 0, {})]),
    ('english_rash', [('I have a skin rash. What service is available?', 0, {}), ('How much does that service cost?', 0, {}), ('Thanks, that is all.', 0, {})]),
    ('draft_interruption', [
        ('我要預約 Sarah 醫生的一般健康檢查，日期時間還沒決定。', 0, {'draft': {'doctor_id': 'D101', 'treatment_id': 'T001'}}),
        ('先問一下她會說甚麼語言？', 0, {'draft': {'doctor_id': 'D101', 'treatment_id': 'T001'}}),
        ('不用了，取消這個還沒提交的預約。', 0, {'absent_draft': ['doctor_id', 'treatment_id']}),
    ]),
    ('missing_doctor', [('想約 2035 年 12 月 9 日上午十點，還沒決定醫生和服務。', 0, {'absent_draft': ['doctor_id', 'treatment_id']})]),
    ('policy', [('Metro Care 取消預約要提前多久？會罰多少？', 0, {})]),
]
if __name__ == '__main__':
    audit.main()

