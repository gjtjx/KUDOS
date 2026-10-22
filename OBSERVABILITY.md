# 模型追蹤 / Model Observability

內建 SQLite 追蹤，用於觀察延遲、用量與錯誤；未接入 Langfuse，也不外送遙測。
Built-in local tracing, with no external Langfuse integration or telemetry export.

## 1. 查看方式 / Viewing activity

開啟頁面下方「模型使用紀錄」，在對話或摘要後刷新，可展開請求的模型呼叫。API 為 `GET /api/observability?limit=20`，limit 允許 1–100。
The UI fetches activity on demand; the API lists retained request traces and generation spans.

啟用追蹤時，`POST /api/chat` 與 `POST /api/transcripts/summarize` 建立父請求並回傳 `X-Trace-ID`。route_intent、answer、summarize_transcript 的實際模型呼叫各有子 span。快取重試建立新請求紀錄，但不增加模型呼叫。
A cached replay remains an application request without becoming another provider call.

## 2. 保存內容 / Stored fields

| 資料 / Data | 欄位 / Fields |
|---|---|
| `request_traces` | trace ID、operation、mode、開始時間、HTTP/status、耗時、outcome、cache hit |
| `llm_spans` | span/trace ID、operation、model、API style、時間、狀態、input/output tokens、安全錯誤分類 |

供應商 response ID 可出現在即時工具回傳 metadata，但目前不另存於 `llm_spans` 欄位。不要把即時 tool_trace 與持久化追蹤表當成相同結構。
Provider response IDs may appear in live tool metadata; they are not a column in the persistent span table.

用量未提供時為 null，UI 顯示未知；不計算價格。模型傳輸成功不等於語義正確，後續摘要驗證的結果反映於父請求狀態。
Unknown usage is not measured zero, and a successful provider call is not a quality score.

## 3. 設定與生命週期 / Configuration and lifecycle

| 設定 / Setting | 預設與範圍 / Default and range |
|---|---|
| `TRACE_ENABLED` | true；false 停止新增，仍可讀既有紀錄 / Disables collection, not existing reads |
| `TRACE_MAX_RECORDS` | 1000；允許 10–10000 / Retained completed-request bound |

請求結束後刪除超額的最舊完成紀錄及其子 span；執行中暫不刪除，因此不是絕對硬上限。啟動時把遺留 running 標為 interrupted。只支援單 process/worker。
Retention is applied to completed requests, with startup recovery for interrupted work.

ContextVar 隔離請求追蹤上下文。追蹤寫入採 best effort：失敗不撤銷或誤報成功預約，但統計可能缺漏。
Tracing failures do not invalidate committed business operations.

## 4. 隱私與維護 / Privacy and operations

追蹤兩張表不存提示、回答、逐字稿、病人 ID 或密鑰；既有 sessions／requests 仍保存聊天內容。LLM 模式仍向供應商傳送必要上下文，不能因此宣稱整個應用不處理敏感資料。
Metadata-only tracing does not eliminate sensitive data elsewhere in the application.

沒有登入控制，維持 localhost 或受控 port-forward。備份整份 SQLite，步驟見 [MAINTENANCE](MAINTENANCE.md)；測試覆蓋見 [VALIDATION](VALIDATION.md)。
