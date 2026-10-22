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
    "fee|price|费用|价格": "price_usd consultation_fee_usd",
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

