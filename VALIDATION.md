# 測試與驗收 / Validation — 2026-10-22

## 已完成 / Completed

- 真實 Poe Claude Sonnet 5.5：14 則對話及 2 則逐字稿摘要，78 項檢查通過。另有逐字稿指令注入測例，診斷與用藥保持 null。 / Live Claude: 14 chat turns, two summaries, 78 passing checks, plus a transcript-injection case.
- 後端 86 項單元／整合測試通過；前端 22 項單元／元件測試通過，共 108 項。 / 86 backend and 22 frontend tests passed, 108 total.
- 後端覆蓋率 97.50%（行與分支合併，backend/app 全部模組）；前端核心元件與 API 最近覆蓋率為行、敘述、函式 100%，分支 92.30%，本輪前端未變更。 / Backend combined coverage 97.50%; latest frontend core coverage is 100% lines/statements/functions and 92.30% branches; frontend code is unchanged.
- 額外真實情境 167 項檢查通過，修復後原始完整流程 78 項亦通過；最後文案調整另有 4 項針對性檢查。發現與修正詳見 [EXTENDED_TEST_REPORT.md](EXTENDED_TEST_REPORT.md)。 / 167 additional live checks and the 78-check core rerun passed, plus four final formatting checks; see the extended report.
- React 正式建置成功。 / Production build passed.

環境 / Environment: Windows, Python 3.13, Node 22.15, Vite 6.4.5, Vitest 4.1.12.

## 真實流程 / Live flow

就診流程 → 過敏服務推薦 → 指代追問診金 → 皮膚科推薦 → 現有預約 → 新預約草稿 → 從前文選擇醫生與服務 → 中途詢問準備事項 → 中文日期時間 → REST 儲存 → GET 列表與 SQL 核對 → 同請求重試 → 不匹配醫生服務拒絕與更正 → 取消草稿 → 重啟持久化 → 逐字稿摘要。

The complete live flow covers contextual retrieval, all routing intents, slot collection, interleaving, natural date/time, REST execution, SQL persistence, retry deduplication, correction, draft cancellation, restart and summary extraction.

證據記錄包含實際模型名稱、provider response ID、每次模型 token 與耗時；沒有用模擬回覆代替真實測試。供應商相容性問題與量測見 [LIVE_MODEL_REPORT.md](LIVE_MODEL_REPORT.md)。 / Evidence includes real provider metadata; see the live report for compatibility and measured results.

## 瀏覽器驗收 / Browser acceptance

使用隔離資料庫和 8017 埠，並未把測試預約加入使用者 8000 服務的資料庫。

Used an isolated database on port 8017, separate from the user's port-8000 database.

1. 頁面顯示 LLM 與 claude-sonnet-5.5，初始預約 2 筆。 / Model badge and two seeded bookings displayed.
2. 點就診流程問題，得到有來源的繁英流程。 / Visit question returned grounded bilingual guidance.
3. 輸入「我想預約莎拉醫生的一般健康檢查」，模型選 D101/T001 並追問日期時間。 / Natural-language selection collected missing date/time.
4. 輸入「2035年12月5日上午十點」，預約 B894824B4B332 儲存，列表從 2 筆變 3 筆。 / Booking persisted and the visible list increased to three.
5. 逐字稿首次生成發現引文不完全匹配，後端回錯誤並阻止成功顯示。加入最多一次修復後，頁面重測成功，呈現四欄繁英摘要、原文引句及 JSON 入口。 / The initial summary failed exact evidence validation; after adding one bounded repair, browser retest displayed the four fields, quotes and JSON.
6. 移除內部 request ID 上下文後，新草稿追問更精簡，未再顯示內部編號。 / Targeted browser retest confirmed concise draft prompts without internal IDs.

完整 78 項實測之後，另作上述引文修復與草稿文案修正，並重新通過後端全套測試及針對性瀏覽器重測。沒有因模型非決定性而把一次成功視為所有問法都可靠。

After the 78-check run, the evidence-repair and draft-prompt adjustments received full backend regression and targeted browser retests. A successful run does not imply universal language reliability.

## 測試位置與重跑 / Reproduction

- backend/tests/test_units.py：驗證、路由、回答、翻譯、檢索單元測試。 / Core units.
- backend/tests/test_app.py、test_regressions.py：真實 SQLite/API 與持久化、檢索範圍。 / Database/API regressions.
- backend/tests/test_llm_features.py：API 相容性、錯誤、摘要 schema/evidence、一次修復與無副作用。 / Provider and summary contracts.
- frontend/src/test：聊天、API、摘要元件及失敗恢復。 / React/API component tests.
- scripts/live_acceptance.py：需憑證的真實模型全流程，輸出至 runtime/live-acceptance。 / Opt-in paid live suite.

完整命令、備份還原與功能對照見 [MAINTENANCE.md](MAINTENANCE.md)。 / See the maintenance manual for commands and feature mapping.

## 尚未驗證 / Not verified

GPT-6 Astra High 指 Codex 對話模型，未作獨立 API 對跑，無其延遲、用量或分數。比較文件中的 Codex 欄位是審核意見，不是第二組模型實測。

The Codex-selected GPT model was not run as an independent API benchmark. Review comments are not benchmark results.

GitHub Actions 先前因帳號帳單鎖定未啟動：[run 39775522266](https://github.com/gjtjx/KUDOS/actions/runs/39775522266)。本機測試通過不代表雲端 CI 通過。Docker runtime、其他作業系統、多 worker、負載、DST 歧義時間及臨床正確性仍未驗收。未實作錄音轉文字、Langfuse 或 Kubernetes。

Cloud CI remains blocked by the previously reported account lock. Docker, cross-platform, distributed/load, DST and clinical validation remain outside acceptance. Audio transcription, Langfuse and Kubernetes are not implemented.
