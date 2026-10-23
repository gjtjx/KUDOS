"""Grounded, concise bilingual answers for the deterministic demo mode."""
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from .knowledge import MATCHES
from .localization import normalize_input, translated_value, FIELD_LABELS


def is_visit_flow(query):
    q = normalize_input(query).lower()
    return bool(re.search(
        r"(就诊|看诊|看病|就医|到院|来院|报到).*(流程|步骤|怎么|如何)|"
        r"(流程|步骤).*(就诊|看诊|医院|诊所)|"
        r"(去|到|来).*(医院|诊所).*(流程|步骤|怎么|如何)|"
        r"(医院|诊所).*(流程|步骤)|"
        r"\b(check[ -]?in|visit process|visit workflow)\b|"
        r"\b(what|how).*(expect|happens|prepare|do).*(visit|arriv|clinic|hospital)|"
        r"\b(walk|guide).*through.*visit", q))


def upcoming_bookings(bookings, now=None):
    now = now or datetime.now(timezone.utc)
    def instant(b):
        return datetime.fromisoformat(b['booking_date']+'T'+b['booking_time']).replace(tzinfo=ZoneInfo(b['timezone']))
    return sorted((b for b in bookings if b['status']=='Confirmed' and instant(b)>=now), key=instant)


def visit_answer(bookings, catalog, booking_text):
    upcoming = upcoming_bookings(bookings)
    text = (
        "可以，我先按『前往診所就診』整理流程。\nHere is a guide to your clinic visit.\n\n"
        "1. 出發前：確認預約的醫生、服務、日期及診所當地時間；如未預約，可在這裡提供這四項資料完成預約。\n"
        "Before leaving: confirm your doctor, treatment, date and clinic-local time. If needed, provide these four details here to book.\n\n"
        "2. 就診準備：依已預約服務的說明準備，並確認診所地址。\n"
        "Prepare: follow the instructions for your booked treatment and confirm the clinic address.\n\n"
        "3. 抵達後：向櫃台確認報到、候診及所需文件；看診時可向醫生說明本次需求、過敏與病史。\n"
        "On arrival: ask reception about check-in, waiting and required documents; discuss your needs, allergies and history with the doctor.\n\n"
        "4. 看診後：向診所確認後續安排及付款方式。資料中沒有各診所的報到、保險、繳費或院內動線規定，以上為一般導覽，實際流程請向診所確認。\n"
        "After the visit: confirm follow-up arrangements and payment with the clinic. The dataset does not specify check-in, insurance, payment or directions inside the clinic; these are general orientation steps, to be confirmed with the clinic."
    )
    sources = []
    if upcoming:
        b = upcoming[0]
        clinic = next(c for c in catalog['clinics'] if c['clinic_id']==b['clinic_id'])
        treatment = next(t for t in catalog['treatments'] if t['treatment_id']==b['treatment_id'])
        text += '\n\n你的下一次預約 / Your next appointment:\n'+booking_text(b)
        text += '\n診所 / Clinic: '+clinic['clinic_name']+'\n地址 / Address: '+clinic['address']
        text += '\n電話 / Phone: '+clinic['phone']
        text += '\n就診前說明 / Preparation: '+translated_value(treatment['treatment_id'],'pre_treatment_instructions',treatment['pre_treatment_instructions'])
        sources = [{'source':'clinics.csv','id':clinic['clinic_id'],'data':clinic},
                   {'source':'treatments.csv','id':treatment['treatment_id'],'data':treatment}]
        text += '\n['+clinic['clinic_id']+' · clinics.csv; '+treatment['treatment_id']+' · treatments.csv; '+b['booking_id']+' · GET /api/bookings]'
    else:
        text += '\n\n目前沒有未來的已確認預約。你想先了解哪間診所，或預約哪項服務？\nThere are no upcoming confirmed appointments. Which clinic or treatment would you like to explore?'
    return text, sources


def local_answer(query, sources, profile, catalog, mapping=None):
    mapping = MATCHES if mapping is None else mapping
    q = normalize_input(query).lower()
    allergy = bool(re.search('allerg|peanut|过敏|花生',q))
    cancellation = bool(re.search('cancel|reschedule|改期|取消',q))
    hours = bool(re.search('hour|open|营业',q))
    preparation = bool(re.search('prepar|instruction|fasting|准备|注意|空腹',q))
    price = bool(re.search('fee|price|cost|费用|价格|多少钱',q))
    location = bool(re.search('address|location|phone|地址|电话|在哪',q))
    fields = (['cancellation_policy','phone'] if cancellation else
              ['operating_hours'] if hours else ['address','phone'] if location else
              ['pre_treatment_instructions'] if preparation else
              ['price_usd','consultation_fee_usd'] if price else [])
    # A field question must not turn into an unrelated treatment recommendation.
    selected = [s for s in sources if not fields or any(k in s['data'] for k in fields)]
    explicit = re.findall(r'\b[cdt]\d{3}\b',q)
    if explicit:
        exact = [s for s in selected if s['id'].lower() in explicit]
        if exact:
            selected = exact
    text = ''
    if allergy:
        text = '已知過敏 / Known allergies: '+profile['known_allergies']+'.\n'
        text += ('目錄沒有專門的過敏檢測或治療項目；可向全科醫生 Dr. Sarah Jenkins (D101) 諮詢，一般健康檢查 (T001) 可用來討論需求。這不是診斷或藥物建議。\n'
                 'The catalog has no dedicated allergy testing or treatment service. Discuss your needs with general practitioner Dr. Sarah Jenkins (D101) through General Health Checkup (T001). This is not a diagnosis or medication advice.\n')
        selected = [s for s in selected if s['id'] in ('T001','D101')]
    if cancellation:
        text += '此 MVP 不提供已確認預約的取消或改期，請聯絡診所。\nThis MVP cannot cancel or reschedule confirmed appointments. Please contact the clinic.\n'
    if not selected:
        return text + ('現有資料不足以回答這個問題。你想了解就診流程、診所營業時間、醫生、服務費用，還是預約？請補充診所、醫生或服務名稱。\n'
                       'The available records do not answer this question. Do you mean the visit process, clinic hours, doctors, service prices or booking? Please specify a clinic, doctor or treatment.')
    for s in selected[:3]:
        row, ident = s['data'], s['id']
        name_key = {'clinics.csv':'clinic_name','doctors.csv':'full_name','treatments.csv':'treatment_name'}[s['source']]
        text += '\n'+translated_value(ident,name_key,row[name_key])+' ('+ident+')\n'
        keys = fields or {'clinics.csv':['operating_hours','address'], 'doctors.csv':['specialty','consultation_fee_usd'],
                          'treatments.csv':['treatment_name','price_usd','duration_minutes']}[s['source']]
        for key in keys:
            if key in row:
                text += FIELD_LABELS.get(key,key)+': '+translated_value(ident,key,row[key])+'\n'
        if not fields and s['source']=='treatments.csv':
            docs = [d for d in catalog['doctors'] if d['doctor_id'] in mapping.get(ident, [])]
            text += '對應醫生 / Doctors: '+', '.join(d['full_name']+' ('+d['doctor_id']+')' for d in docs)+'\n'
        text += '['+s['source']+' · '+ident+']\n'
    return text.strip()
