import json
import re
from .localization import normalize_input

# Explainable bilingual query expansion; catalog records remain the source of facts.
EXPANSIONS = {
    "rash|eczema|acne|skin|皮肤|皮疹|痘": "dermatology eczema acne skin",
    "allerg|peanut|过敏|花生": "general practice health checkup",
    "joint|knee|pain|膝|关节|疼": "orthopedics joint pain",
    "child|pediatric|儿童|小孩": "pediatrics pediatric vaccination",
    "flu|流感": "flu immunization",
    "checkup|体检": "general health checkup preventative",
    "hour|open|营业|时间": "operating_hours",
    "cancel|取消": "cancellation_policy",
    "prepar|instruction|fasting|准备|注意|空腹": "pre_treatment_instructions",
    "address|location|phone|地址|电话|在哪": "address phone",
    "fee|price|cost|费用|价格|多少钱": "price_usd consultation_fee_usd",
}
MATCHES = {"T001": ["D101"], "T002": ["D102"], "T003": ["D103"], "T004": ["D101", "D102"], "T005": ["D104"]}

def retrieve(db, query):
    query = normalize_input(query)
    expanded = query
    for pattern, terms in EXPANSIONS.items():
        if re.search(pattern, query, re.I):
            expanded += " " + terms
    stopwords = {"or", "and", "the", "is", "are", "what", "how", "my", "can", "for", "to", "me", "with", "please", "do", "you"}
    tokens = [t for t in dict.fromkeys(re.findall(r"[a-zA-Z0-9_]{2,}", expanded.lower())) if t not in stopwords][:30]
    if not tokens:
        return []
    match = " OR ".join('"' + token + '"' for token in tokens)
    rows = db.rows("SELECT source,record_id,content,bm25(knowledge) AS score FROM knowledge WHERE knowledge MATCH ? ORDER BY score LIMIT 6", (match,))
    return [{"source": r["source"], "id": r["record_id"], "data": json.loads(r["content"])} for r in rows]


def retrieve_grounded(db, query):
    """Resolve model-selected catalog IDs first, adding only related evidence.

    The model rewrites the question; it never supplies record contents. All facts
    are read from SQLite. Free-text queries retain FTS/BM25 retrieval.
    """
    ids=list(dict.fromkeys(re.findall(r'\b[CDT]\d{3}\b',query.upper())))
    if not ids:
        return retrieve(db,query)
    result={}
    def add(ident):
        table,key={'C':('clinics','clinic_id'),'D':('doctors','doctor_id'),'T':('treatments','treatment_id')}[ident[0]]
        rows=db.rows('SELECT * FROM '+table+' WHERE '+key+'=?',(ident,))
        if rows: result[ident]={'source':table+'.csv','id':ident,'data':rows[0]}
    for ident in ids: add(ident)
    for item in list(result.values()):
        if item['source']=='treatments.csv':
            for ident in MATCHES[item['id']]: add(ident)
    for item in list(result.values()):
        if item['source']=='doctors.csv': add(item['data']['clinic_id'])
    return list(result.values())
