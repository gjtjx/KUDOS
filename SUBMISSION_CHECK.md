# 提交前驗收 / Submission review

審查日期 / Reviewed: **2026-10-23 (Asia/Shanghai)**. Fresh public repository baseline: `c6c849e`; the fixes described below are included with this report.

## 1. 結論 / Decision

**歷史擴大測試，後續修復見 [FIX_VALIDATION](FIX_VALIDATION.md) / Historical broad review, subsequently corrected:** [64 scenarios / 83 turns](DIVERSE_QUESTIONS_REPORT.md) originally found answer-quality issues: an overbroad claim from incomplete retrieved evidence, intermittent extra-confirmation wording and formatting/name-localization issues. Mechanical passes must not be interpreted as all response content being correct. This qualifies the bounded submission assessment below.

**所列剩餘問題已修復並通過加強後的完整複測，可作為本機演示的 MVP 提交。 / The listed remaining issues were fixed and the strengthened full retest passed; ready as a locally demonstrated MVP.** See [REMAINING_FIXES_REPORT.md](REMAINING_FIXES_REPORT.md): 64 scenarios, 83 turns, 525 checks, plus 130 backend tests and 82 core checks. Historical reviews below retain their original scope; no universal language/clinical or production-readiness claim is made. Configure a valid key for LLM mode; fresh installs default to local mode.

This is a bounded review, not a guarantee for every model response. Cloud CI, container execution and Kubernetes cluster execution are not verified. Authentication, existing-booking cancellation/rescheduling, vector embeddings and audio transcription are outside the implemented scope; see [README.md](README.md).

## 2. 乾淨安裝與演示 / Fresh setup and browser demonstration

- Cloned the public GitHub repository, ran `setup.cmd`, installed backend dependencies and built the frontend. A short Windows path was needed for the optional Kubernetes validation dependency; a deeply nested checkout exceeded Windows path limits.
- Port 8000 was already occupied. Used the README's manual startup command on isolated ports 8018 (local) and 8019 (LLM). The default-port `start.cmd` route was not separately validated with port 8000 free.
- Local browser: visit guidance, rash-related service lookup, next appointment, multi-turn booking, updated booking list and persistence after server restart/reload passed. Local summary controls correctly required LLM mode.
- Live DeepSeek browser: selected dermatologist/service, interrupted with a preparation question, supplied date/time with an explicit hold, then confirmed. The held draft created no record; confirmation created one record and updated the list.
- A synthetic doctor-patient transcript produced all four fields with matching quotations, including an explicit statement that no medication was prescribed. The activity panel showed the actual `deepseek-flash` summary call, latency and tokens.

## 3. 當時驗證結果 / Earlier review results

For current results use [REMAINING_FIXES_REPORT.md](REMAINING_FIXES_REPORT.md); the table below records the earlier fresh-clone review.

| Check | Result | Scope |
|---|---|---|
| Backend tests | 110 passed; 98.01% combined coverage | Unit and integration tests |
| Frontend tests | 28 passed | Unit/component tests |
| Frontend production build | Passed | Fresh dependency installation and Vite build |
| Deployment configuration | Passed | Offline checks: two Compose variants and five Kubernetes resources |
| DeepSeek core acceptance | 82/82 checks | Final code; conversation, REST/SQL writes, replay, restart, summaries and traces |
| DeepSeek hold/withdrawal | 27/27 checks | Explicit hold survives edits; confirmation releases it; withdrawn date is cleared |
| Common questions | 84/84 mechanical checks, 20 replies reviewed | 16 scenarios; zero unintended writes; two minor presentation observations below |
| Credential audit | No known credential matches in 158 reachable history blobs at baseline | No sensitive tracked paths; new changes checked before publication |

The common-question checks assert HTTP success, real model routing, zero booking writes, unchanged existing records and selected draft expectations. Factual correctness was reviewed separately against the supplied CSV records; 84 checks do **not** mean 84 independent semantic questions. Mean response time was 5.63 seconds, with an observed range of 1.99–10.87 seconds in this run.

### 常見問題與人工核對 / Common questions and content review

| Question / sequence | Reviewed outcome |
|---|---|
| 我到醫院的流程是怎樣？ | Next appointment and conditional fasting; unspecified check-in procedures identified as general guidance. |
| Metro Care 星期日有開門嗎？星期六呢？ | Sunday closed; Saturday 09:00–13:00, matching C001. |
| Sunset Wellness Center 在哪裡？電話多少？ | Address and phone match C002. |
| Sarah 醫生會說中文嗎？ | English/Spanish listed; Chinese not listed. |
| T003 和 Elena 分別多少錢？一定合計 420 美元嗎？ | USD 200 service / USD 220 doctor fee distinguished; mandatory combined total not invented. |
| 一般健康檢查一定要空腹嗎？ | At least eight hours only if blood tests are scheduled. |
| 有專門的花生過敏檢查嗎？先不要預約。 | Dedicated service absent from catalog; GP discussion suggested without claiming allergy treatment or creating a booking. |
| 我下一次預約是甚麼時候？ | B1001, 2026-11-05 09:00 New York time, Sarah Jenkins. This expectation is date-dependent. |
| 取消已確認的 B1001。 | Unsupported operation explained; original record unchanged. |
| 把 B1001 改到另一個日期。 | Unsupported rescheduling explained; no replacement booking created. |
| 有 MRI 嗎？多少錢？ | Availability and price not invented; extra unrelated catalog examples were unnecessary. |
| 我的保險能全額報銷嗎？ | Dataset limitation stated; coverage not invented. |
| Skin rash → How much does that service cost? → Thanks. | Correct T003/D103 context and USD 200 service price. Courtesy reply unnecessarily cited T003. |
| Sarah checkup draft → 她會說甚麼語言？ → 取消未提交草稿 | Doctor/service preserved through Q&A, then draft cleared without changing bookings. |
| 有日期時間，醫生和服務未決定。 | Asked for missing fields; no doctor/service guessed and no write. |
| Metro Care 取消政策？ | At least 24 hours; late cancellation/no-show **may** incur USD 50, matching C001. |

**未阻塞提交的觀察 / Non-blocking observations:** courtesy replies can carry unnecessary citations, and unknown-service answers can be more verbose than needed. No incorrect booking execution or fabricated catalog fact was found in these 20 replies. These are one-run observations, not a reliability estimate.

## 4. 發現並修正的問題 / Defects corrected

1. **Local retrieval noise:** the README rash question matched an unrelated flu-shot record through the word “have”. Added “have / has / had” to stopwords and an integration regression covering both the rash question and a valid flu-shot query.
2. **Over-cautious LLM routing:** “先讓我確認醫生和服務” was sometimes interpreted as withholding booking execution, so a completed draft remained unsubmitted. Clarified choice confirmation versus an explicit execution hold in routing/answer prompts. The persisted hold gate was retained; explicit hold, edit, confirmation and withdrawal were retested.

An intermediate core run failed its “booking actually created” assertion because of the second issue. It was a missed write, not an unauthorized write. Failure evidence is retained alongside the later passing run.

## 5. 重現與證據 / Reproduction and evidence

Use [VALIDATION.md](VALIDATION.md) for dependency installation, offline tests and core live commands. Common questions use the same opt-in provider flags and isolated databases:

```powershell
.venv/Scripts/python.exe scripts/common_questions_acceptance.py --env-file .env --api-style responses --tool-choice auto --no-strict-tools
```

This invokes the paid provider configured in the selected file. Runtime reports remain ignored by Git. Review response text manually as well as the checks; all sample data is synthetic.

| Run ID | Outcome |
|---|---|
| `df58c8ce58d74d949bcfe1c031494fbc` | Baseline core: 82 passed |
| `e82b331f6b904aa788e5f696c6a58a2e` | Intermediate core: failed booking creation check; retained |
| `92bded55d1aa43cc810bb7cf83491e18` | Final core: 82 passed |
| `6efb4597a543441fa18e504e556492e2` | Final hold/withdrawal: 27 passed |
| `2f21de2bd198436095914bd60363ce94` | Common questions: 84 checks / 20 turns, with content review above |

Poe Sonnet's October 22 acceptance remains historical and was not rerun during this review. See [MODEL_COMPARISON.md](MODEL_COMPARISON.md). GitHub Actions only showed an older failed run when inspected; no green cloud-CI claim is made. Local checks and deployment-manifest validation do not establish production readiness.
