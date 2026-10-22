# 模型追蹤 / Model observability

開啟頁面下方「模型使用紀錄」，在對話或摘要後更新。/ Open Model activity and refresh after a chat or summary.

每個 chat/summary 請求建立獨立 X-Trace-ID，子紀錄對應 route_intent、answer、summarize_transcript。記錄模型、介面、HTTP 結果、耗時、Token、安全錯誤分類與快取命中。重試命中快取不增加模型呼叫。/ Parent requests and generation spans record timing, reported usage and outcomes. Cached retries add no model calls.

資料存於 SQLite request_traces / llm_spans，重啟保留。這兩張表不保存提示、回答、逐字稿、病人 ID 或憑證；原有 sessions/requests 仍保存聊天內容。/ Trace tables are metadata-only; existing conversation tables still contain conversation content.

GET /api/observability?limit=20，limit 範圍 1–100。TRACE_ENABLED 預設 true；false 停止新增，既有資料仍可讀。TRACE_MAX_RECORDS 預設 1000，可設 10–10000；請求結束後刪除超額的最舊完成紀錄及其子紀錄。執行中紀錄暫不刪除。/ Bounded retention applies to completed requests.

重啟將遺留 running 標為 interrupted。只支援單 process/worker。追蹤儲存失敗不影響成功預約，但統計可能缺漏。未回報 Token 為 null，畫面顯示 —；不估算費用。模型呼叫成功代表傳輸與回傳通過檢查，不代表語義正確；摘要引文的後續驗證結果反映於請求狀態。/ Provider success is not a semantic quality score.

這是內建本機追蹤，沒有接入 Langfuse 或外送遙測。沒有登入控制，維持 localhost 或 port-forward 存取。備份整份 SQLite，見 MAINTENANCE.md。/ Built-in local tracing, no external Langfuse export.

測試見 test_observability.py、TracePanel.test.jsx，涵蓋隔離、隱私、保留上限、重啟、停用、缺失用量、錯誤與 UI 重試。/ Tests cover lifecycle, privacy, failures and presentation.
