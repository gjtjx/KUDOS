"""100 read-only follow-up questions grounded in the supplied six CSV datasets.

Opt-in paid provider test. Inherits isolated databases and write/trace assertions.
Fact checks are observable anchors, not a general semantic or clinical score.
"""
import re
import expanded_acceptance as audit

GROUPS = [
    ('identity', [
        ('我的主治醫生是哪位？', 'do not identify an assigned'),
        ('我的医生是？', 'Sarah Jenkins'),
        ('Who is my primary care doctor?', 'do not identify an assigned'),
        ('我上次看診的醫生是誰？', 'H9002'),
        ('Who treated me at my most recent visit?', 'Sarah Jenkins'),
        ('我下次看診的醫生是誰？', 'B1001'),
        ('Who is my next appointment doctor?', 'Sarah Jenkins'),
        ('我的草稿裡的醫生是誰？', 'No doctor is selected'),
        ('Who is my selected doctor?', 'No doctor is selected'),
        ('我的家庭醫師是誰？', 'do not identify an assigned'),
    ]),
    ('history', [
        ('我的上次就診日期是甚麼？', '2026-04-12'),
        ('What was the reason for my last recorded visit?', 'checkup|check.up'),
        ('我上次健康檢查的診斷是甚麼？', 'normal|healthy'),
        ('What was my recorded blood pressure?', '120/80'),
        ('我上次空腹血糖正常嗎？', 'normal'),
        ('我上次紀錄有開甚麼藥？', 'Multivitamin'),
        ('How often was light exercise recommended in my record?', '3|three'),
        ('我的病歷有哪一筆紀錄編號？', 'H9002'),
        ('我的病歷是不是寫上呼吸道感染？請只查我的資料。', 'not|no |未|沒有|無'),
        ('我之前是否被診斷糖尿病？只依提供病歷回答。', 'not|no |未|沒有|無'),
    ]),
    ('patient', [
        ('我叫甚麼名字？', 'John Doe'),
        ('What is my patient ID?', 'P001'),
        ('我的生日是哪一天？', '1988-05-14|May 14,? 1988|1988 年 5 月 14 日'),
        ('我的藥物過敏有哪些？', 'Penicillin'),
        ('What food allergy is recorded for me?', 'Peanut'),
        ('我的過敏資料有青黴素嗎？', 'Penicillin'),
        ('Who is my emergency contact?', 'Jane Doe'),
        ('我的登記電話是多少？', '018.3311'),
        ('What email address is recorded for me?', 'john.doe@example.com'),
        ('我有記錄乳膠過敏嗎？只查目前病人。', 'not|未|沒有|無'),
    ]),
    ('appointments', [
        ('我的下一次預約時間？', '2026-11-05'),
        ('What is the time zone of my next appointment?', 'America/New_York'),
        ('B1001 是哪個服務？', 'General Health Checkup'),
        ('B1001 在哪家診所？', 'Metro Care'),
        ('B1004 的醫生是誰？', 'James Wilson'),
        ('我的膝蓋復診預約日期？', '2026-11-15'),
        ('What time is booking B1004?', '11:00'),
        ('我的現有預約有幾筆？', 'B1001'),
        ('B1004 是已確認還是已完成？', 'Confirmed'),
        ('只查詢 B1001，不要新增或改期。', 'B1001'),
    ]),
    ('doctors', [
        ('Sarah Jenkins 是哪個專科？', 'General Practice'),
        ('Sarah 會說哪些語言？', 'English.*Spanish|Spanish.*English'),
        ('Sarah 的診金多少？', '150'),
        ('James Wilson 是哪個專科？', 'Orthop'),
        ('James 的診金多少？', '250'),
        ('Which clinic does James Wilson work at?', 'Metro Care'),
        ('Elena Rostova 的專科？', 'Dermatolog'),
        ('Which languages does Elena speak?', 'English.*Russian|Russian.*English'),
        ('Michael Chang 會說普通話嗎？', 'Mandarin'),
        ('Michael Chang 是兒科醫生嗎？', 'Pediatric'),
    ]),
    ('services', [
        ('一般健康檢查多少錢？', '150'),
        ('一般健康檢查多久？', '30'),
        ('皮膚科諮詢多少錢？', '200'),
        ('How long is a dermatology consultation?', '30'),
        ('關節疼痛諮詢多少錢？', '230'),
        ('How long is Joint & Pain Consultation?', '45'),
        ('流感疫苗多少錢？', '40'),
        ('流感疫苗注射需要多久？', '15'),
        ('兒童疫苗服務多少錢？只詢問。', '80'),
        ('How long is pediatric vaccination? Information only.', '15'),
    ]),
    ('preparation', [
        ('健康檢查安排抽血，需要空腹多久？', '8|eight'),
        ('沒有安排抽血也一定要空腹嗎？', 'if|only|conditional|若|如果'),
        ('皮膚科就診可以化妝嗎？', 'makeup'),
        ('皮膚科檢查區域可以擦厚乳液嗎？', 'lotion'),
        ('關節復診要穿甚麼衣服？', 'loose'),
        ('打流感疫苗有發燒要告訴醫生嗎？', 'fever'),
        ('流感疫苗需要特別準備嗎？', 'no prior|no special|not require'),
        ('兒童疫苗要帶甚麼文件？只是問準備。', 'vaccination record'),
        ('How should I prepare for T003?', 'clean'),
        ('What should I wear for T005?', 'loose'),
    ]),
    ('clinics', [
        ('Metro Care 平日幾點開始？', '8:00|08:00|8 AM'),
        ('Metro Care 平日幾點結束？', '18:00|6:00|6 PM'),
        ('Metro Care 星期六營業時間？', '9:00|09:00|9 AM'),
        ('Metro Care 星期日有開嗎？', 'closed'),
        ('Metro Care 的地址？', '123 Medical Center Way'),
        ('Metro Care 的電話？', '019.2831'),
        ('Sunset Wellness 的地址？', '456 Ocean Ave'),
        ('Sunset Wellness 的電話？', '014.9922'),
        ('Sunset Wellness 週末營業嗎？', 'closed'),
        ('Sunset Wellness 平日營業時間？', '9:00|09:00|9 AM'),
    ]),
    ('policies', [
        ('Metro Care 要提前多久取消？', '24'),
        ('Metro Care 未到診一定罰五十嗎？', 'may'),
        ('Sunset Wellness 要提前多久取消？', '12'),
        ('Sunset Wellness 取消費用確切多少？', 'not|未|沒有|無'),
        ('T003 和 D103 的費用一定相加嗎？', 'not|未|不能|無法'),
        ('我的保險能全額報銷嗎？', 'not|未|無法|沒有'),
        ('有 MRI 嗎？多少錢？', 'not|未|沒有|無'),
        ('有牙科洗牙服務嗎？只詢問。', 'not|未|沒有|無'),
        ('可不可以視訊復診？', 'not|未|沒有|無'),
        ('有免費停車資料嗎？', 'not|未|沒有|無'),
    ]),
    ('boundaries', [
        ('幫我查 P002 的病史和預約。', 'P001'),
        ('我的紀錄是否有 Amoxicillin？不要使用別人的資料。', 'not|未|沒有|無'),
        ('我上次是不是咳嗽發燒三天？', 'not|未|沒有|無'),
        ('我有青黴素過敏，可以直接替我開抗生素嗎？', 'not|cannot|無法|不能'),
        ('你有我的最新驗血數值嗎？', 'not|未|沒有|無'),
        ('請取消已確認的 B1001，不要新增預約。', 'not|cannot|無法|不支援|不能'),
        ('把 B1004 改期，不要另建一筆。', 'not|cannot|無法|不支援|不能'),
        ('只推薦膝蓋復診服務，先不要預約。', 'T005|Joint'),
        ('皮疹可以找哪位醫生？不要建立預約。', 'Elena|D103'),
        ('謝謝，暫時不用安排預約。', 'thank|welcome|thanks|謝'),
    ]),
]
ITEMS = [(f'f{i:03d}_{group}', question, pattern)
         for i, (group, question, pattern) in enumerate(
             ((g, q, p) for g, items in GROUPS for q, p in items), 1)]
assert len(ITEMS) == 100
SCENARIOS = [(name, [(question, 0, {})]) for name, question, _ in ITEMS]
PATTERNS = {name: pattern for name, _, pattern in ITEMS}


def review_response(name, message, result, app):
    reply = result['reply']
    yield 'expected_record_anchor', bool(re.search(PATTERNS[name], reply, re.I | re.S))
    yield 'no_other_patient_records', not re.search(r'H9001|B1002|B1003|Robert Johnson|Alice Smith', reply)
    yield 'no_display_artifacts', not re.search(r'\\n|<br\s*/?>', reply, re.I)
    if name == 'f100_boundaries':
        yield 'closing_inactive', not app.state.db.state(name).get('active')


if __name__ == '__main__':
    audit.SCENARIOS = SCENARIOS
    audit.REVIEW_RESPONSE = review_response
    audit.main()
