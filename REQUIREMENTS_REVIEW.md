# 需求核對 / Requirements Review

最新修復與驗證 / Latest fixes and retest: [REMAINING_FIXES_REPORT.md](REMAINING_FIXES_REPORT.md). Earlier counts and provider comparisons below retain their original scope.

文件核對：2026-10-23；最近功能驗收：2026-10-23。
Documentation reviewed October 23, 2026; latest functional acceptance is dated October 23.

依據使用者提供的原始 `AI-interview-take-home-assignment.md`。本頁追蹤交付範圍；啟動方式見 [README](README.md)，數據與驗證邊界見 [VALIDATION](VALIDATION.md)。
This page maps the original assignment to the implementation, not to production or clinical certification.

## 1. 核心流程 / Required workflow

提問 → 檢索與推薦 → 查詢現有預約 → 多輪收集醫生、服務、日期及時間 → 呼叫 REST → 寫入資料庫 → 更新 React 列表。
Question → retrieval and recommendation → existing bookings → slot collection → REST execution → persistent record → refreshed UI.

## 2. 必做功能 / Required features

| 要求 / Requirement | 實作與驗證 / Implementation and evidence |
|---|---|
| 索引 clinics、doctors、treatments / Index knowledge datasets | ID 關聯查詢及 FTS5/BM25；檢索回歸與真實模型測例。 / Structured and lexical retrieval, tested locally and in live acceptance. |
| 依需求推薦服務及醫生 / Recommend services and doctors | 根據目錄與 P001 上下文回答；不把服務導覽當診斷。 / Catalog-grounded recommendations, not diagnosis. |
| 動態意圖與上下文理解 / Intent and context | `route_intent`、歷史訊息、持久化草稿；涵蓋指代與中途問答。 / Structured routing and persisted state with contextual acceptance cases. |
| 以 REST 或 MCP 查詢預約 / Tool-based booking queries | 選用 `GET /api/bookings`；ASGITransport 經正式 REST handler。 / Actual REST handlers selected from the permitted alternatives. |
| 收集缺失參數並執行預約 / Collect slots and execute | 四欄完整且允許提交後呼叫 `POST /api/bookings`，交易保存及重試去重。 / Authorized complete drafts produce persistent, idempotent writes. |
| 固定病人及個人化 / Fixed patient context | P001 的個資、過敏、病史與即時預約；拒絕其他病人 ID。 / Preloaded patient context and enforced scope. |
| 患者與醫生關係 / Patient-doctor relations | 病歷／預約 JOIN 與唯讀工具區分歷史、下次及草稿醫生；不推定未提供的主治指定。 / Scoped relationship queries and a persisted doctor/service bridge. |
| FastAPI 或 NestJS / Backend choice | FastAPI，自訂 Python Agent，模組分離。 / FastAPI with modular custom orchestration. |
| 六份 CSV 初始化關聯資料庫 / Relational seed | SQLite 六張業務表、外鍵及缺失 ID 初始化。 / Relational schema and insert-if-missing seed. |
| 請求驗證、SQL、錯誤處理 / Engineering standards | Pydantic、參數化 SQL、交易及明確錯誤回應。 / Validation, parameterized queries and transactional error handling. |
| React 聊天與即時／可刷新預約 / React workbench | 繁英介面、重試、新對話、自動與手動列表更新。 / Bilingual chat, retry controls and appointment refresh. |

本機單元／整合／元件測試、DeepSeek 本次真實複核及 Sonnet 10 月 22 日歷史對照提供驗證證據；有限測例通過不保證每種自然語言都能正確處理。
Local tests, the current DeepSeek review and historical Sonnet acceptance substantiate these features within the recorded cases.

## 3. 加分項與排除範圍 / Optional features and exclusions

| 項目 / Item | 現況 / Status |
|---|---|
| 文字逐字稿四欄摘要 / Transcript summary | LLM 端點與 UI 已實作，含引文、缺失 null 及有限修復；不含音訊辨識。 / Implemented text summary, not speech-to-text. |
| LLM 追蹤 / Observability | SQLite 父請求／子呼叫、耗時、Token、錯誤與快取；無外部 Langfuse 或費用估算。 / Persistent built-in tracing. |
| Docker／Kubernetes / Deployment files | 已提供並做離線設定檢查；未完成容器／叢集執行驗收。 / Manifests supplied; runtime unverified. |
| 排班衝突 / Scheduling conflicts | 原題明確不要求，假設時段可用。 / Explicitly excluded by the assignment. |
| 登入、多病人 / Authentication, multiple patients | 原題採固定病人簡化；目前未實作。 / Outside the simplified patient scope. |
| 同時支援 REST 與 MCP / Both protocols | 原題二選一；REST 已符合此項。 / REST satisfies the alternative. |
| 向量資料庫或指定 Agent 框架 / Vector store or mandated framework | 原題未強制；目前採 FTS5 與自訂編排。 / Not required; not implemented. |
| 已確認預約取消／改期 / Saved booking cancellation/rescheduling | 未列為必做；只提供取消草稿。 / Only pending drafts can be cancelled. |

## 4. 提交狀態 / Submission status

| 交付要求 / Deliverable | 狀態 / Status |
|---|---|
| 公開 GitHub 原始碼 / Public source repository | [gjtjx/KUDOS](https://github.com/gjtjx/KUDOS) |
| 本機設定指南 / Setup guide | [README](README.md) |
| 架構、意圖、工具與資料設計 / Technical design | [TECH_DOC](TECH_DOC.md) |
| 英文提交摘要 / English overview | [SUBMISSION_REPORT_EN](SUBMISSION_REPORT_EN.md) |
| 回信附倉庫連結 / Submission email | 已提供草稿；未代寄郵件。 / Draft provided; no email sent. |
| 24 小時期限 / 24-hour deadline | 原始郵件收件時間未知，須自行核對。 / Receipt timestamp unavailable. |
| 現場展示 / Live demonstration | 已有本機及 DeepSeek／Sonnet 驗收紀錄；現場前仍須確認服務及額度。 / Recorded acceptance does not guarantee future provider availability. |

最新乾淨副本驗收與修正見 [SUBMISSION_CHECK](SUBMISSION_CHECK.md)。 / See the fresh-clone readiness review for current evidence.

## 5. 提交／面試前檢查 / Pre-demo checks

1. 按 README 啟動，以 `/api/health` 核對實際模式與模型，再做一則提問驗證供應商可用。 / Check configuration and a real request.
2. 按 README 示範流程，用未來日期及隔離資料庫展示真實寫入、列表更新與持久化。 / Demonstrate persistence without altering retained demo data.
3. 真實模型回歸指令集中於 [MODEL_COMPARISON](MODEL_COMPARISON.md)；不要使用歷史報告的舊設定。 / Use current reproducibility instructions.
4. 如要展示容器或雲端 CI，須先取得實際成功證據；目前不宣稱已驗收。 / Runtime deployment and cloud CI remain separate checks.

必做功能已有對應實作與已記錄的驗收證據，可作作業提交；郵件寄送、期限核對及現場環境確認仍由提交者完成。這不是正式醫療上線許可。
The required implementation is supported by recorded evidence; email submission, deadline confirmation and demo readiness remain separate responsibilities.
