# 提交前驗收 / Submission review

Reviewed **2026-10-23 (Asia/Shanghai)**. Fresh public baseline: `459e58a`; the changes and tests below are included with this report.

## 1. 結論 / Decision

**可演示的作業 MVP，仍有已記錄的模型格式失敗。 / Demonstrable assignment MVP with a retained intermittent model-format failure.** Required features are mapped in [REQUIREMENTS_REVIEW.md](REQUIREMENTS_REVIEW.md). Live mode requires private provider configuration; a fresh install defaults to local mode. This is bounded acceptance, not production or clinical certification.

| 驗證 / Validation | 結果 / Result |
|---|---|
| 後端單元／整合 / Backend tests | 152 passed; 97.49% combined line/branch coverage |
| 前端單元／元件 / Frontend tests | 29 passed; production build passed |
| DeepSeek 核心 / Live core acceptance | Latest: 78/78 checks without summary flag; earlier 82/82 includes summaries |
| 患者醫生關係 / Patient-doctor relationships | Latest: 123/124 checks; one invalid-bilingual-answer 502 retained. Earlier: 127/127 |
| 完整回歸 / Full regression | 64 scenarios / 83 turns / 525 checks passed; all 8 expected writes |
| 復診常見問題 / Follow-up questions | 100 questions / 701 checks passed; zero booking writes |
| 醫生資訊 / Doctor information | 100 questions / 700 checks passed; zero writes |
| 指南擴展 / Research-based follow-up | 60 questions / 480 checks passed; source and limits below |
| 部署設定 / Deployment configuration | 2 Compose variants / 5 Kubernetes resources checked offline |
| 容器、叢集與雲端 CI / Runtime and cloud CI | Not verified |

## 2. 乾淨安裝與演示 / Setup and demonstration

- Cloned the public baseline and actually ran `setup.cmd`: backend installation, npm dependency installation and production build passed. All six parsed CSV datasets match the original supplied records; newline encoding differs only.
- Port 8000 was occupied during the fresh review; used the README manual startup pattern on isolated ports 8030 (local) and 8031 (LLM). The default-port `start.cmd` path was not separately exercised with 8000 free. Root, health, readiness and API docs returned HTTP 200.
- Local browser: visit guidance, skin-service recommendation, next appointment, multi-turn booking, list refresh and persistence after restart passed. Local summaries correctly require LLM mode.
- DeepSeek browser: Elena/T003 draft survived an interleaved preparation question; an explicit hold caused zero writes, and confirmation caused exactly one write. A four-field transcript summary retained source quotations and explicit no-medication wording; the trace panel showed actual model use.
- New doctor queries were demonstrated in the browser. The final extra next-visit service/clinic fields were added afterwards and verified by unit and live relationship tests. Full browser coverage of every question is not claimed.

## 3. 資料關係與修正 / Relationship design

The former route could treat “我的医生是？” as a request for all bookings. Catalog similarity cannot establish patient-doctor assignment. The source schema does not record an assigned primary/attending doctor.

The implementation joins patient history to doctors/clinics and live bookings to doctors/services/clinics. A read-only relationship API distinguishes assignment unknown, most recent historical doctor, next confirmed future appointment and session draft doctor. Narrow standalone identity guards preserve drafts and prevent accidental writes after actual model routing. See the [relationship diagram](TECH_DOC.md).

The follow-up test found omitted clinic details in booking replies and an omitted emergency-contact name. Specific booking IDs now select the matching patient-owned row and include the clinic; source contact names are permitted by the bilingual validator and requested explicitly in generation. Explicit other-patient IDs are rejected after routing, instead of showing P001 bookings in response. Regression tests cover all three. The initial birthday assertion incorrectly required ISO formatting; equivalent written dates are now accepted, with the initial failure retained.

The new `doctor_treatments` bridge holds six documented demo links absent from the original CSVs. Retrieval expansion, router compatibility context and transaction validation read the same table; nonempty maintained mappings survive restart. Empty mappings bootstrap again. This is an additive change; original CSVs remain unchanged.

RAG still uses exact IDs and FTS5/BM25. Both router and knowledge generation receive the complete small catalog alongside selected evidence. It is not dense/vector retrieval; the full-catalog context is an explicit scaling limitation.

## 4. 復診 100 題 / Follow-up evaluation

[The runnable inventory](scripts/followup_questions_acceptance.py) contains ten questions each for identity, history, patient profile, appointments, doctors, services, preparation, clinics, policies and boundaries. Every question uses an independent seeded database and expects zero writes. Checks cover HTTP success, real model routing, unchanged bookings, record anchors, other-patient identifiers and display artifacts. The 64-scenario suite additionally covers multi-turn state and eight intended booking writes.

Regex fact anchors are deliberately visible and limited: they can detect missing expected facts but cannot prove every sentence correct. [Doctor inventory](scripts/doctor_questions_acceptance.py): 25 questions for each of four doctors, covering names, specialties, biography, languages, fees, clinic, services and unrecorded credentials or schedules. All 100 are read-only.

[Research-based inventory](scripts/researched_followup_acceptance.py): 60 original questions inspired by [NHS](https://www.nhs.uk/nhs-services/gps/what-to-ask-your-doctor/), [NIH NIA](https://www.nia.nih.gov/health/medical-care-and-appointments/what-should-i-ask-my-doctor-during-checkup) and [AHRQ](https://www.ahrq.gov/health-literacy/improve/precautions/tool6.html), accessed October 23, 2026. These cover preparation, symptom changes, medicines, tests, treatment decisions, recovery, coordination, understanding, access and continuity. They test unchanged clinical records and bookings, HTTP/real routing, privacy and formatting. These checks do not grade clinical advice. The sources define question categories only; they are not loaded as clinic policy, services or patient facts, and NHS-specific procedures are not adopted for the US mock clinics.

No broad language, clinical or prompt-injection success rate is inferred. The expected next appointment is date-dependent (B1001 as of this review).

## 5. 可重現證據 / Reproduction and retained evidence

Use [VALIDATION.md](VALIDATION.md) for offline tests and provider setup. Paid tests use ignored runtime reports and isolated databases:

```powershell
.venv/Scripts/python.exe scripts/patient_doctors_acceptance.py --env-file .env --api-style responses --tool-choice auto --no-strict-tools
.venv/Scripts/python.exe scripts/followup_questions_acceptance.py --env-file .env --api-style responses --tool-choice auto --no-strict-tools
.venv/Scripts/python.exe scripts/doctor_questions_acceptance.py --env-file .env --api-style responses --tool-choice auto --no-strict-tools
.venv/Scripts/python.exe scripts/researched_followup_acceptance.py --env-file .env --api-style responses --tool-choice auto --no-strict-tools
```

| Run ID | Result |
|---|---|
| `13f732954e4e4476a3ddcdf5b3b0b795` | Core acceptance: 82 passed; before the final optional next-visit detail addition |
| `e963a01dafa24b34af1621e43d4ac435` | Earlier relationship suite: 14 turns / 127 checks passed |
| `aea6bd869d4846cf9dbd4adcc59bce27` | Latest core rerun: 78/78 checks; summary flag omitted |
| `4073ae67767a445fabe95822e710a320` | Latest relationship rerun: 123/124 checks; p10 doctor-language follow-up returned invalid_bilingual_answer 502 |
| `53ada1e62c464c8c967ec807f74247ed` | 32 turns; 191 checks; 0 failed |
| `989f5b69c664454cbf829c19b27f04c8` | 51 turns; 334 checks; 0 failed |
| `2a5aec2a0ed94a0ebf2255863f5b3a7a` | 25 turns; 175 checks; 0 failed |
| `efc0db4e95744ff8a8c16ea20a4ea31a` | 25 turns; 175 checks; 0 failed |
| `2b546732080c47ec996ec6a95647e02e` | 25 turns; 175 checks; 0 failed |
| `36a9cf7686fc4829bb1ed5e8b2fce9c9` | 25 turns; 176 checks; 0 failed |
| `ec34321b8bc844e58ce9e56efbe8caf5` | 25 turns; 175 checks; 0 failed |
| `4c4644eb38dc43ba81c23dfd7f028d26` | 25 turns; 175 checks; 0 failed |
| `bc0b9a365a4e493c89bf1bd5e2719199` | 25 turns; 175 checks; 0 failed |
| `327f88356f824f578747939521ec7b9f` | 25 turns; 175 checks; 0 failed |
| `15130399b06746698b0473270b7acfd7` | 20 turns; 160 checks; 0 failed |
| `cdf9b46e3df14e3095da411ad871fd41` | 20 turns; 160 checks; 0 failed |
| `2e32d79f22454b758ec0b34de59946ea` | 20 turns; 160 checks; 0 failed |
| `7b6a87ea0a3a45db92242ffa527b0d69` | Earlier complete 64-scenario run: two provider transport failures (ReadError / ConnectError), retained |
| `847033c34509462fa1adc9243dc68c6f` | The two transport-affected questions subsequently passed 12 checks |

The latest relationship rerun returned invalid_bilingual_answer once (123/124 checks), after two bounded generation attempts. No booking was written. This remains a provider-output limitation, not an all-pass claim. The latest core rerun passed 78 checks; its summary flag was omitted, so the earlier 82-check run and browser summary evidence retain their separate scope. Final follow-up refinements were retested in their affected batches; the 64-scenario run precedes the final clinical-history route guard and email-literal refinement.

The complete latest 64 scenarios were partitioned into nonoverlapping batches; their results are aggregated above, not added to earlier partial runs. Earlier tool-session interruptions left incomplete reports (`cd93bcffdd36470dba51e6d0f885f433`, `9d065054904a4c4b8ffe1257275588d1`, `5b104dd563e640928234ec1e74f744bf`, `f185acad222f4981b44915bbea9f43f0`); these are not counted as passes. No automatic provider transport retries were introduced.

Earlier functional failures remain in [DIVERSE_QUESTIONS_REPORT.md](DIVERSE_QUESTIONS_REPORT.md), [FIX_VALIDATION.md](FIX_VALIDATION.md) and [REMAINING_FIXES_REPORT.md](REMAINING_FIXES_REPORT.md). Their run counts describe different revisions and are not cumulative. Sonnet was not rerun in this review; its comparison remains dated separately.

### 本輪保留的失敗 / Retained follow-up findings

The initial birthday check was a test false positive (written dates versus ISO). Other findings were real omissions/misrouting: missing contact name, missing clinic in booking details, a patient-scope question rendered as P001 bookings, a legitimate email rejected by the bilingual validator, and a past-symptom question routed to appointments. Original failed reports remain unchanged; affected batches were rerun after corrections. Regex anchors were not weakened to accept incorrect facts.

| Run ID | Original failed checks |
|---|---|
| `78a58f3c457c4019a41f3526aa68cf03` | f023_patient-1 review/expected_record_anchor |
| `21d0e137026f43e3a6ea1d588cda7a75` | f027_patient-1 review/expected_record_anchor, f034_appointments-1 review/expected_record_anchor |
| `31c04b494290421b958ae036f96111d7` | f091_boundaries-1 review/expected_record_anchor |
| `a7ae212cee7d4db8ac83b2222e704871` | f029_patient-1 HTTP |
| `feb42bf7b390483ea2cb28be584fc2d7` | f093_boundaries-1 review/expected_record_anchor, f100_boundaries-1 review/expected_record_anchor |

## 6. 安全與未驗證邊界 / Security and limits

Known local credentials were checked against tracked files and reachable Git history before publication; credentials, private configuration and raw runtime reports are excluded from commits. Private key files remain unchanged. Trace metadata does not include prompts or keys, but conversation state stores chat text and live requests send required mock context to the provider.

No successful cloud CI is claimed. The earlier [Actions run](https://github.com/gjtjx/KUDOS/actions/runs/39775522266) failed; current billing eligibility was not inspected. Docker/Kubernetes received offline manifest checks only. Authentication, saved-booking cancellation/rescheduling, audio transcription and validated multi-worker operation are not implemented. Provider connectivity can fail explicitly with 502. Submission email and deadline receipt are outside this technical verification.
