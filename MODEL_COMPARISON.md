# 模型相容性與對照 / Provider Compatibility and Comparison

**量測日期 / Measured: 2026-10-22.** 同一程式、資料與流程，DeepSeek 和 Poe Sonnet 最終均通過 82 項檢查。操作設定以 [README 模型設定](README.md#model-configuration) 為準。
These are recorded acceptance results, not a current provider availability guarantee.

## 1. 比較方法 / Method

每組包含 14 輪對話、2 則摘要及 1 次快取重試，共 17 個應用請求。涵蓋就診導覽、推薦、指代、現有預約、多輪收集、中途問答、寫入／更正、草稿取消、重啟、摘要與追蹤。
Each run uses the same fixtures and checks actual REST/SQL persistence, not just generated responses.

| 指標 / Metric | DeepSeek Flash | Poe Sonnet 5.5 |
|---|---:|---:|
| 檢查 / Checks | 82/82 | 82/82 |
| 模型呼叫 / Model calls | 27 | 27 |
| 平均應用請求耗時，含快取重試 / Mean request latency including cached retry | 5.49 s | 14.78 s |
| Input tokens | 82,390 | 140,426 |
| Output tokens | 10,081 | 11,229 |
| 請求失敗 / Failed requests | 0 | 0 |
| 快取命中 / Cache hits | 1 | 1 |

這輪 DeepSeek 較快，但 API、供應商、分詞器及預設推理行為不同；不能推導通用品質或成本排名。未獨立測試 Codex 對話中的 GPT-6 Astra High。
The sample is small, token totals are not a direct cost comparison, and no independent Astra API benchmark exists.

## 2. 已驗證的相容性 / Observed compatibility

| 路徑 / Route | 觀察 / Observation |
|---|---|
| DeepSeek `deepseek-flash` | Responses + auto + strict=false 通過；實測 thinking 設定拒絕 forced tool choice。 / Compatible profile passed; forced selection was rejected. |
| Poe `claude-sonnet-5.5` | Chat Completions + auto + strict=false 通過；該路徑拒絕 Responses 和 forced tool choice。 / Use the tested Chat Completions profile. |
| Poe `claude-opus-5.5` | 早期回傳 model not found；不是可用模型驗收。 / Earlier model-not-found result, not a supported profile. |

應用預設對 Poe／DeepSeek 使用 auto、strict=false；明確設定優先。測試腳本有自己的設定載入器，因此下方命令仍明確指定相容參數。主機驗證不因 provider strict=false 而停用。
Application defaults and test-harness defaults differ; use the explicit test options below.

## 3. 已重現問題與修復 / Reproduced issues and fixes

| 問題 / Issue | 修復與證據 / Fix and evidence |
|---|---|
| .env 與舊 .env.local 混用導致錯供應商／401 | 啟動只自動讀 .env；測試先清除殘留 LLM/POE 設定再讀指定檔。 / Provider profiles no longer mix implicitly. |
| DeepSeek forced tool choice 回 400，應用呈現 502 | 相容參數及供應商預設；最終流程通過。 / Compatible selection settings. |
| 特定服務準備事項誤判 visit_flow | 路由明確區分整體就診流程與服務準備；兩模型均通過原句。 / Treatment preparation remains knowledge and preserves the draft. |
| 無效路由結構 | 預約前最多一次修復；持續錯誤失敗，憑證／供應商錯誤不重試。 / Bounded pre-action repair and regression tests. |

部分早期 generic ValueError 沒有足夠細節，不能證明每次都是同一原因。Poe 曾有協定／連線失敗；一次完整通過不代表未來不會再出錯。
Historical unclassified failures remain unresolved as to exact cause; successful acceptance is not a universal reliability guarantee.

## 4. 重跑核心與額外測試 / Reproduction

先在專案根目錄準備獨立供應商檔：`.env` 放完整 DeepSeek 設定；`.env.sonnet` 放 README 中的完整 Poe/Sonnet 設定及其密鑰。兩者都不提交。既有 `1.env` 若保留舊 Opus 設定，不應直接當作 Sonnet profile。
Prepare two complete local profiles. The alternate filename is an example, not a file included in the repository.

使用已安裝開發依賴的虛擬環境；以下會消耗 API 額度。 / Use the project environment with development dependencies installed; these commands make paid requests.

```powershell
.\.venv\Scripts\python.exe scripts/live_acceptance.py --env-file .env --model deepseek-flash --api-style responses --tool-choice auto --no-strict-tools --summary
.\.venv\Scripts\python.exe scripts/live_acceptance.py --env-file .env.sonnet --model claude-sonnet-5.5 --api-style chat_completions --tool-choice auto --no-strict-tools --summary
```

額外邊界案例使用指定檔中的模型名稱；此腳本沒有 `--model` 參數。 / The expanded harness uses the model from its profile and has no model override.

```powershell
.\.venv\Scripts\python.exe scripts/expanded_acceptance.py --env-file .env.sonnet --api-style chat_completions --tool-choice auto --no-strict-tools --summary
```

可加 `--only hold,withdraw_slot` 選取情境；保留 `--summary` 仍會執行摘要。要測 DeepSeek，改為其完整設定檔與 `--api-style responses`。
The scenario filter applies to chat cases; summary execution is controlled separately.

## 5. 證據與保留 / Evidence and retention

| 供應商 / Provider | 最終 run ID / Accepted run |
|---|---|
| DeepSeek | `ec12269891244d4e8f11c7dbea5d7111` |
| Poe Sonnet | `7eb2c0c675554f0db2d746b4d455b4b1` |

核心輸出位於 `runtime/live-acceptance/<run-id>/`，額外案例位於 `runtime/expanded-acceptance/<run-id>/`；使用隔離 DB。原始對話、報告及 DB 保留本機，不發布。較早失敗與中斷報告不算通過。
Reports and databases remain local; failed and interrupted runs are retained separately.

早期相容性與瀏覽器發現見 [LIVE_MODEL_REPORT](LIVE_MODEL_REPORT.md)，授權／撤回修復歷史見 [EXTENDED_TEST_REPORT](EXTENDED_TEST_REPORT.md)，目前整體測試成績見 [VALIDATION](VALIDATION.md)。
