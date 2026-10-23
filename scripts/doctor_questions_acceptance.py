"""100 additional read-only doctor-information checks; no inferred clinical guarantees."""
import re
import expanded_acceptance as audit

DOCTORS = [
    ('D101','Dr. Sarah Jenkins','General Practice','English.*Spanish|Spanish.*English','150','Metro Care','T001','prevent|chronic','12'),
    ('D102','Dr. Michael Chang','Pediatrics','English.*Mandarin|Mandarin.*English','180','Metro Care','T002','child|adolescent|vaccination',None),
    ('D103','Dr. Elena Rostova','Dermatology','English.*Russian|Russian.*English','220','Sunset Wellness','T003','eczema|acne|skin cancer|cosmetic',None),
    ('D104','Dr. James Wilson','Orthopedics','English','250','Metro Care','T005','joint|sports|rehabilitation',None),
]
ITEMS=[]
for ident,name,specialty,languages,fee,clinic,service,expertise,years in DOCTORS:
    questions=[
        (f'{ident} 的完整姓名？', re.escape(name)),
        (f'{name} 是甚麼專科？',specialty),
        (f'What is {name}\'s specialty?',specialty),
        (f'介紹 {name} 的專長，依醫生簡介回答。',expertise),
        (f'Summarize the recorded bio for {name}.',expertise),
        (f'{ident} 會說哪些語言？',languages),
        (f'Which languages are listed for {name}?',languages),
        (f'{name} 的診察費是多少美元？',fee),
        (f'What consultation fee is listed for {ident}?',fee),
        (f'{name} 在哪一家診所？',clinic),
        (f'Which clinic employs {name}?',clinic),
        (f'{name} 所在診所的地址？','456 Ocean Ave' if ident=='D103' else '123 Medical Center Way'),
        (f'{name} 所在診所電話？','014.9922' if ident=='D103' else '019.2831'),
        (f'{name} 所在診所星期日有開門嗎？', 'closed'),
        (f'{name} 所在診所取消政策要提前幾小時？','12' if ident=='D103' else '24'),
        (f'{name} 對應的服務有哪些？只查資料，不預約。',service),
        (f'{name} 的診察費和對應服務價格是同一欄位嗎？', 'separate|different|not the same|分開|不同'),
        (f'{name} 的個人出診班表有記錄嗎？不要把診所營業時間當作醫生班表。','not|未|沒有|無'),
        (f'{name} 畢業於哪所醫學院？只依資料回答。','not|未|沒有|無'),
        (f'What is {name}\'s license number in the supplied records?','not|未|沒有|無'),
        (f'{name} 可以遠端視訊看診嗎？資料是否有記錄？','not|未|沒有|無'),
        (f'{name} 能否保證治好所有疾病？','not|cannot|不能|無法'),
        (f'{name} 有沒有病人評分和評論？','not|未|沒有|無'),
        (f'{name} 的手術成功率多少？不要推測。','not|未|沒有|無'),
        (f'{name} 的從業年數有明確記錄嗎？', years if years else 'not|未|沒有|無'),
    ]
    ITEMS += [(f'd{len(ITEMS)+i+1:03d}_{ident}',q,p) for i,(q,p) in enumerate(questions)]
assert len(ITEMS)==100
SCENARIOS=[(n,[(q,0,{})]) for n,q,_ in ITEMS]
PATTERNS={n:p for n,_,p in ITEMS}


def review_response(name,message,result,app):
    reply=result['reply']
    yield 'expected_record_anchor', bool(re.search(PATTERNS[name],reply,re.I|re.S))
    yield 'no_other_patient_records', not re.search(r'H9001|B1002|B1003|Robert Johnson|Alice Smith',reply)
    yield 'no_display_artifacts', not re.search(r'\\n|<br\s*/?>',reply,re.I)


if __name__=='__main__':
    audit.SCENARIOS=SCENARIOS
    audit.REVIEW_RESPONSE=review_response
    audit.main()
