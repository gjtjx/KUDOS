# 測試與驗收 / Validation — 2026-10-22

## 本次修正 / Regression fixed

新對話輸入「我到医院的流程」曾被當作一般檢索問題，零命中後先輸出無關過敏資訊與通用提示。現在使用明確的就診導覽意圖，回答出發、準備、報到及看診後步驟，附上實際未來預約與資料來源；缺少的院內規定明確標示需向診所確認。它不建立預約，亦不改動既有草稿。

The reported phrase previously fell through to empty retrieval and an unrelated allergy-prefixed fallback. It now selects visit orientation, adds current booking/catalog facts, identifies unknown on-site policies, and does not create bookings or discard drafts.

其他修正：問營業時間、費用、準備或取消政策時只呈現相關欄位；新對話清除未送出輸入；取消既有預約問題不誤分流為預約歷史；下一次預約依實際時區時間排序；拒絕無效模型工具與欄位格式。

Other fixes include concise field-specific answers, clearing unsent input on New chat, cancellation routing, timezone-aware upcoming order and rejecting malformed model tool output.

## 自動化結果 / Automated results

環境 / Environment: Windows, Python 3.13, Node 22.15, npm 10.9, Vite 6.4.5, Vitest 4.1.12.

| 檢查 / Check | 結果 / Result |
|---|---|
| 後端單元與整合 / Backend units and integration | 56 tests passed: 27 unit cases in test_units.py, 17 existing integration cases, 12 new API/data regressions. Subtests cover additional inputs. |
| 後端覆蓋 / Backend coverage | 428/430 executable lines (99.53%); 118/120 branches (98.33%); combined 99.27%. Scope: all backend/app modules. |
| 前端單元及元件 / Frontend unit and component | 17 tests passed: 4 API-client cases and 13 React interaction cases. |
| 前端覆蓋 / Frontend coverage | 100% lines/statements/functions; 93.24% branches (69/74). Scope: App.jsx and api.js; bootstrap main.jsx and CSS excluded. |
| 依賴重建 / Reproducible install | npm ci succeeded from the committed lockfile. |
| 正式建置 / Production build | npm run build succeeded. |
| 依賴檢查 / Dependency audit | npm installation audit: 0 known vulnerabilities, 133 packages audited. |

後端未覆蓋分支主要為可選 dotenv 缺少及未建置首頁的啟動路徑；前端少量替代顯示分支未覆蓋。沒有以排除核心邏輯的方式宣稱全系統 100%。

Uncovered backend paths include missing optional dotenv and startup without built assets; some frontend display fallbacks remain uncovered. No claim of 100% whole-system coverage is made.

完整功能與測試檔對照，以及可重跑指令，見 [MAINTENANCE.md](MAINTENANCE.md)。後端測試使用獨立暫存資料庫，前端元件測試使用 jsdom 與模擬 API；它們不是瀏覽器端到端測試。

See the maintenance manual for the feature matrix and commands. Backend tests use isolated SQLite databases. Frontend component tests use jsdom and mocked APIs, not browser end-to-end execution.

## 驗證範圍與限制 / Scope and limits

- 本次新增流程由 API 回歸及前端元件測試驗證；未把先前版本的瀏覽器驗收當成本次瀏覽器驗收。 / The new flow is verified by API regression and frontend component tests; earlier browser checks are not claimed as current browser acceptance.
- 前一版本已用隔離資料庫在瀏覽器驗證繁英多輪預約及列表由 2 筆變 3 筆。 / The previous bilingual version had browser acceptance for multi-turn booking and list updates from two to three entries.
- 真實 LLM 未配置憑證；模型輸出與供應商 HTTP 均以模擬回覆驗證合約，不代表自然語言品質或實際服務連線驗收。 / Live LLM remains unverified; mocked contracts do not prove language quality or provider connectivity.
- GitHub Actions 先前未啟動，原因為帳號帳單鎖定：[run 39775522266](https://github.com/gjtjx/KUDOS/actions/runs/39775522266)。CI 已加入測試與門檻，但不宣稱雲端通過。 / CI configuration includes the new gates; cloud success is not claimed while the account lock remains unresolved.
- Docker 執行、其他作業系統、多 worker、負載、DST 歧義時間及臨床正確性未驗收。 / Docker runtime, other platforms, multi-worker/load, DST ambiguity and clinical accuracy are not verified.
- 單元測試覆蓋的是目前已實作功能；可選醫療逐字稿摘要、Langfuse、Kubernetes 未實作，不在測試覆蓋內。 / Coverage applies to implemented features, not unimplemented optional summarization, external tracing or Kubernetes.
