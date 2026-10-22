"""Display translations only; original CSV values and database records stay unchanged."""
INPUT_PAIRS = {
    "預約": "预约", "醫生": "医生", "體檢": "体检", "健康檢查": "体检", "皮膚": "皮肤",
    "關節": "关节", "諮詢": "咨询", "過敏": "过敏", "兒童": "儿童",
    "幫": "帮", "查詢": "查询", "放棄": "放弃", "確認": "确认",
    "威爾遜": "威尔逊", "張": "张", "營業": "营业", "時間": "时间",
    "費用": "费用", "價格": "价格", "流感": "流感",
}
def normalize_input(value):
    for traditional, simplified in INPUT_PAIRS.items():
        value = value.replace(traditional, simplified)
    return value

TRANSLATIONS = {
    "C001": {
        "operating_hours": "週一至週五 08:00–18:00；週六 09:00–13:00；週日休診",
        "cancellation_policy": "請至少提前 24 小時取消。逾時取消或未到診可能收取 50 美元。",
        "emergency_instructions": "危及生命的緊急情況，請立即撥打 911 或前往最近的醫院急診室。",
    },
    "C002": {
        "operating_hours": "週一至週五 09:00–17:00；週六及週日休診",
        "cancellation_policy": "請至少提前 12 小時通知取消，以免產生取消費用。",
        "emergency_instructions": "營業時間外若有緊急醫療需要，請致電診所總機並按 9，聯絡值班分診護理人員。",
    },
    "D101": {"specialty": "全科", "languages_spoken": "英語、西班牙語", "bio": "具專科認證的家庭醫師，擁有超過 12 年預防保健及慢性病管理經驗。"},
    "D102": {"specialty": "兒科", "languages_spoken": "英語、普通話", "bio": "兒科專科醫師，專注兒童發展、青少年醫學及兒童疫苗接種。"},
    "D103": {"specialty": "皮膚科", "languages_spoken": "英語、俄語", "bio": "皮膚科醫師，專長包括濕疹、痤瘡治療、常規皮膚癌篩查及美容療程。"},
    "D104": {"specialty": "骨科", "languages_spoken": "英語", "bio": "骨科專科醫師，專注關節疼痛、運動損傷及身體復健指導。"},
    "T001": {"treatment_name": "一般健康檢查", "category": "預防保健", "pre_treatment_instructions": "如已安排抽血檢查，請於就診前至少空腹 8 小時。"},
    "T002": {"treatment_name": "兒童疫苗接種", "category": "兒科", "pre_treatment_instructions": "請攜帶兒童的正式疫苗接種紀錄冊。"},
    "T003": {"treatment_name": "皮膚科諮詢", "category": "皮膚科", "pre_treatment_instructions": "請保持待檢查部位的皮膚清潔，避免化妝或塗抹厚重乳液。"},
    "T004": {"treatment_name": "流感疫苗注射", "category": "免疫接種", "pre_treatment_instructions": "無須事前準備。如目前發燒，請告知醫師。"},
    "T005": {"treatment_name": "關節與疼痛諮詢", "category": "骨科", "pre_treatment_instructions": "請穿著寬鬆衣物，以便檢查相關關節。"},
}
FIELD_LABELS = {
    "clinic_id": "診所編號 / Clinic ID", "clinic_name": "診所 / Clinic",
    "address": "地址 / Address", "phone": "電話 / Phone",
    "operating_hours": "營業時間 / Opening hours", "cancellation_policy": "取消政策 / Cancellation policy",
    "emergency_instructions": "緊急指引 / Emergency instructions",
    "doctor_id": "醫生編號 / Doctor ID", "full_name": "醫生 / Doctor",
    "specialty": "專科 / Specialty", "languages_spoken": "語言 / Languages",
    "consultation_fee_usd": "診金（美元） / Consultation fee (USD)", "bio": "簡介 / Biography",
    "treatment_id": "服務編號 / Treatment ID", "treatment_name": "服務 / Treatment",
    "category": "類別 / Category", "duration_minutes": "時長（分鐘） / Duration (minutes)",
    "price_usd": "價格（美元） / Price (USD)", "pre_treatment_instructions": "就診前說明 / Preparation",
}
STATUS = {"Confirmed": "已確認 / Confirmed", "Completed": "已完成 / Completed", "Cancelled": "已取消 / Cancelled"}

def translated_value(ident, key, value):
    zh = TRANSLATIONS.get(ident, {}).get(key)
    return f"{zh} / {value}" if zh else str(value)

def localized_booking(row):
    return {**row, "treatment_name_zh": TRANSLATIONS.get(row["treatment_id"], {}).get("treatment_name", ""),
            "pre_treatment_instructions_zh": TRANSLATIONS.get(row["treatment_id"], {}).get("pre_treatment_instructions", ""),
            "status_label": STATUS.get(row["status"], row["status"])}

