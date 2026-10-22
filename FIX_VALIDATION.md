# 回歸修復驗證 / Regression fix validation

**後續狀態 / Follow-up:** The findings in this historical phase were subsequently addressed and retested; [REMAINING_FIXES_REPORT.md](REMAINING_FIXES_REPORT.md) records the 525-check complete rerun. Original failures and counts below are preserved.

Date: **2026-10-23 (Asia/Shanghai)**. Fixes follow the failed broad review at `03c67a5`. Original failures remain in [DIVERSE_QUESTIONS_REPORT.md](DIVERSE_QUESTIONS_REPORT.md); they have not been rewritten as passes.

## 修復 / Changes

| Problem | Change and verification |
|---|---|
| Complete English booking remains a draft | Routing now requests an exact user authorization quote and a separate current-turn hold quote. The host checks quote provenance; a complete unheld draft with grounded authorization can normalize an erroneous collect action to submit. Persisted hold still requires confirm. A hold without its requested evidence is rejected through bounded routing repair. |
| Lookup contradicts a previously created booking | The LLM still routes the query, but the reply is rendered directly from the live REST booking records. No free-text generation can deny a record that is present. The current view lists the next appointment and all booking history, rather than selecting a single last-created record. |
| MRI answer generalizes incomplete retrieval | Knowledge generation receives the complete small catalog alongside selected retrieval evidence. Instructions distinguish “MRI not listed” from absence of all prices and distinguish catalog absence from physical unavailability. The real retest correctly limited its unknown-price statement to MRI. |
| Draft response invents extra approval | Missing-field and held-draft prompts are rendered from backend state. Natural-language routing and extraction still use the real model; this is an explicit responsibility boundary, not a provider-error fallback. |
| Escaped newlines, HTML breaks, mixed scripts and invented name rendering | A display-only normalizer handles escaped newlines and HTML line breaks, converts generated Chinese with [OpenCC](https://pypi.org/project/opencc-python-reimplemented/), and removes a Chinese personal-name prefix attached to a canonical English doctor name. Prompts require original catalog names. Summary values use the same formatting, while original evidence quotations remain unchanged. |

Authorization quotes establish provenance, not perfect semantic understanding. Other safety gates, API validation and idempotency remain required. Catalog-wide context is suitable for these eleven records; larger catalogs need scoped candidate retrieval and explicit completeness metadata.

## 驗證 / Validation

| Check | Result |
|---|---|
| Backend unit/integration tests | **118 passed**, combined coverage **97.64%** |
| Targeted live DeepSeek regression | **112/112 checks**, 11 scenarios, 20 turns |
| Repeated English booking / lookup probes | **50/50 checks**, two additional isolated runs; no failures |
| Live DeepSeek full acceptance | **82/82 checks**, including summaries, replay, restart and trace checks |
| Frontend | Unchanged; prior 28-test result retained, not rerun for these backend changes |

Targeted run: `82795167c9fd420cb927c8b22753e1a2`.
Full run: `708b3214a3534800bbe33a7d4e760ce6`.
Repeated probes: `0f674378ab134801aa54825c91ceda1a`, `6b1b9826cead4fe584c892a6f7f88d3b` (25 checks each). They are reported separately from the 112-check targeted suite, not as additional distinct scenarios.

Targeted scenarios: c14, c23, c31, c38, c50, c51, c52, c61, c62, c63, c64. The English request created the intended James Wilson / joint-consultation booking at 14:30. The timezone case wrote the correct Los Angeles record and the next query included it without a denial. Explicit hold/edit/confirm cases passed without premature writes. MRI, preparation and credential-refusal text was manually reviewed for source scope, format and original doctor names.

The entire 64-scenario suite was subsequently rerun on `8e2e2d0`: **376/376 original checks passed**, 83 turns and all 8 expected writes. Response/state review still found open issues; see [FULL_REGRESSION_REPORT.md](FULL_REGRESSION_REPORT.md). The earlier 83-turn / 374-check outcome remains historical. Focused passes are not a universal language-quality guarantee. Cloud CI, Docker execution and Kubernetes runtime remain unverified.

## 重現 / Reproduce

Install the updated backend requirements first; the pinned OpenCC dependency is new. Run the commands in a fresh PowerShell window:

```powershell
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
.venv/Scripts/python.exe scripts/diverse_questions_acceptance.py --env-file .env --api-style responses --tool-choice auto --no-strict-tools --only c14_mandarin,c23_vaccine_prep,c31_mri,c38_secret,c50_interruption,c51_hold,c52_hold_edit,c61_ambiguous_ampm,c62_date_choices,c63_english_booking,c64_timezone
.venv/Scripts/python.exe scripts/live_acceptance.py --env-file .env --summary --api-style responses --tool-choice auto --no-strict-tools
```

Calls use the configured paid provider. Databases and raw reports remain isolated under ignored runtime directories. No credential files or raw runtime reports are published.
