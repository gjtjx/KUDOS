# DeepSeek Flash 與 Sonnet 5.5 / Final comparison

2026-10-22：同一程式、資料、14 輪對話及兩種逐字稿摘要，兩個模型均完整通過 82 項檢查。/ Both models passed all 82 checks on the same application and fixtures.

| 指標 / Metric | DeepSeek Flash | Poe Sonnet 5.5 |
|---|---:|---:|
| 完整驗收 / Checks | 82/82 | 82/82 |
| 模型呼叫 / Calls | 27 | 27 |
| 平均請求耗時（含快取重試） / Mean request latency including cached retry | 5.49 s | 14.78 s |
| Input tokens | 82,390 | 140,426 |
| Output tokens | 10,081 | 11,229 |
| 請求失敗 / Failed requests | 0 | 0 |
| 快取重試 / Cached retry | 1 | 1 |

本次 DeepSeek 較快；不同供應商、API、分詞器與預設推理行為，不能把 Token 直接換算成成本或當通用品質排名。僅單輪小樣本，不代表所有問法都穩定。/ This run was faster with DeepSeek; different tokenizers, APIs and provider defaults prevent general cost/quality conclusions.

## 修正與驗證 / Fixes and evidence

1. 啟動只讀完整 .env，移除舊 .env.local 的隱性覆蓋；對照腳本只載入指定檔並清除殘留 LLM 設定。/ Provider profiles no longer mix.
2. DeepSeek thinking mode 不接受 forced tool choice，曾回 400 並轉為應用 502。Poe/DeepSeek 的缺省工具設定現為 auto、strict=false，使用者明確設定仍優先；主機仍驗證工具輸出。/ Compatible defaults prevent the reproduced protocol error.
3. 路由明確區分整體報到流程與特定服務準備事項；後者取 knowledge，保留草稿。原句「去之前皮膚需要做甚麼準備？」在兩個模型的最終驗收均正確。/ Both models pass the previously misrouted preparation question.
4. 不合法路由結構最多重新生成一次，發生在任何預約副作用之前；持續無效回安全的 invalid_router_output。憑證或供應商失敗不走這個重試。/ Bounded pre-action repair with fail-closed validation.
5. 先前零星 Agent ValueError 未保存足夠細節，無法證明每一次都由同一欄位造成；不宣稱單輪成功可消除所有模型錯誤。新增測試覆蓋 null/錯誤形狀、兩次失敗、憑證不重試及草稿不變。/ Historical generic errors cannot all be assigned a proven single cause.

## 完整驗收範圍 / Acceptance scope

就診流程、服務推薦、指代追問、現有預約、自然語言選醫生/服務/日期/時間、中途問答、REST 寫入、SQL 核對、重試不重複、不匹配拒絕/更正、取消草稿、重啟保存、摘要引文與缺失 null、追蹤呼叫數與 Token 核對。/ Routing, grounded answers, booking state and persistence, summary evidence, and tracing accounting.

最終證據 ID：DeepSeek ec12269891244d4e8f11c7dbea5d7111；Sonnet 7eb2c0c675554f0db2d746b4d455b4b1。原始報告和 DB 只存本機 runtime，不發布。較早失敗與中斷報告保留，不算通過。/ Raw evidence remains local; earlier failed runs are retained.

```powershell
python scripts/live_acceptance.py --env-file .env --model deepseek-flash --tool-choice auto --no-strict-tools --summary
python scripts/live_acceptance.py --env-file 1.env --model claude-sonnet-5.5 --api-style chat_completions --tool-choice auto --no-strict-tools --summary
```

1.env 原本仍含舊 Opus/Responses 設定，故上例明確覆寫。測試使用隔離 DB 並消耗 API 額度。/ Explicit overrides select Sonnet despite old settings in the alternate file.

[DeepSeek Responses 文件](https://api-docs.deepseek.com/guides/responses_api/)；部署限制見 DEPLOYMENT.md，追蹤見 OBSERVABILITY.md。Docker/Kubernetes 目前僅離線驗證，尚無容器/cluster 實際運行結果。
