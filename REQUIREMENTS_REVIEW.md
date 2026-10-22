# ClinicPilot AI — 需求與功能核對 / Requirements Review

核對日期 / Reviewed: 2026-10-22  
依據 / Source: AI-interview-take-home-assignment.md  
最新進展 / Latest: 已接通 Poe Claude Sonnet 5.5，完成 78 項真實流程檢查及文字逐字稿摘要。模型比較邊界與數據見 LIVE_MODEL_REPORT.md。 / Live Claude and transcript extraction are implemented and tested; see the live report.

狀態含義 / Status: 「已驗證」指本機測試或瀏覽器流程；不代表已完成真實 LLM、臨床或正式部署驗收。 / “Verified” means local tests or browser validation, not live-provider, clinical or production approval.

## 1. 作業真正要展示的流程 / Required demonstration

病人提問 → 檢索診所、醫生及服務資料 → 提供合適服務與醫生建議 → 查詢現有預約 → 用多輪對話補齊醫生、服務、日期及時間 → Agent 呼叫 REST API 或 MCP → 預約寫入資料庫 → 畫面立即顯示新紀錄。

Patient question → grounded clinic/doctor/service retrieval → suitable service and doctor recommendation → existing bookings query → multi-turn slot collection → REST or MCP execution → database persistence → refreshed booking list.

評分重點為架構分層、意圖分流、AI 編排／工具呼叫及資料持久化；複雜視覺設計不是要求。 / Evaluation prioritizes architecture, intent routing, AI orchestration/tool calling and persistence over visual complexity.

## 2. 必做功能逐項核對 / Required features

| ID | 原始要求 / Requirement | 現況與限制 / Current implementation and limits | 驗收方式 / Acceptance |
|---|---|---|---|
| AI-01 | 索引 clinics、doctors、treatments 三份 CSV / Index three knowledge datasets | 已實作 SQLite FTS5、BM25 排序、雙語詞彙擴展；屬詞彙檢索，並非向量檢索。原題沒有強制向量資料庫。 / Implemented lexical retrieval, not embeddings; a vector store is not mandated. | 問診所營業時間、取消政策、皮膚科及關節服務；檢查來源檔名與 ID。 / Ask catalog questions and inspect citations. |
| AI-02 | 依需求或症狀推薦服務與醫生 / Recommend suitable services and doctors | 本機模板及真實 Claude 路徑已測試；Claude 改寫問題後採 ID 關聯查詢或 FTS 檢索。 / Both paths tested; Claude rewrites contextual queries for structured/FTS retrieval. | 花生過敏問題應指出目錄沒有專門過敏服務，提供全科諮詢選項，不虛構項目。 / Allergy question must not invent a dedicated service. |
| AI-03 | 動態判斷問答、既有預約、新預約意圖 / Route Q&A, booking queries and new bookings | 本機中英文規則可運作；LLM 使用 route_intent 函式結構輸出。LLM 合約有模擬測試，並有真實 Poe 工具呼叫驗收。 / Mocked contracts and live Poe tool calls are both verified. | 相同對話內切換問答及預約，確認草稿不遺失。 / Interleave questions and booking turns. |
| AI-04 | 經 REST 或 MCP 查詢當前病人的現有預約 / Query existing bookings through tools | 已驗證 GET /api/bookings；資料庫由原 CSV 初始化，後續查詢反映新增紀錄。 / Verified REST tool reads live seeded database records. | 問「我的下一次預約是甚麼時候？」並核對資料。 / Ask for next appointment. |
| AI-05 | 多輪辨識及追問缺失參數 / Collect missing parameters | 已驗證醫生、服務、日期、時間四欄位，支援分次填寫及更正。 / Four-slot collection and correction verified. | 先說要預約，再給醫生與服務，最後提供日期時間。 / Fill slots over several turns. |
| AI-06 | 參數齊全後實際呼叫 API／工具，寫入資料庫 / Execute and persist booking | 已驗證 POST /api/bookings；不只產生文字確認。HTTPX ASGI transport 經正式 FastAPI 路由、驗證及交易。 / Verified execution through actual REST handlers and DB transaction. | 核對對話預約 ID、GET 結果及重啟後紀錄。 / Compare booking ID, GET response and restart state. |
| AI-07 | 固定單一病人，注入個資、過敏／病史及預約 / Fixed patient context | P001 的資料、過敏、就診歷史及即時預約已載入；不需登入或輸入 ID。 / P001 context loaded without authentication. | 核對 Penicillin、Peanuts；其他 patient_id 應遭拒絕。 / Verify allergy context and patient scope. |
| BE-01 | FastAPI 或 NestJS 後端 / Permitted backend | 已採 FastAPI，AI 核心使用 Python 自訂 Agent。 / Implemented with Python/FastAPI. | 啟動服務並開啟 /docs。 / Start server and inspect API docs. |
| BE-02 | 六份 CSV 初始化關聯式資料庫 / Seed all six CSVs | 已採 SQLite，含 patient_bookings、外鍵、重複啟動不重複匯入。 / Six-table relational seed with foreign keys and idempotency. | 比較初始資料及重複啟動後筆數。 / Verify counts across startup. |
| BE-03 | POST /api/chat 接收訊息及可選 patient_id / Chat endpoint | 已實作；額外使用 session_id、request_id 管理狀態與重試。 / Implemented with explicit session and request identifiers. | API 與前端發送訊息均可回應。 / Exercise API and UI. |
| BE-04 | POST /api/bookings 與 GET /api/bookings / Booking endpoints | 已實作並測試；讀寫同一資料庫。 / Implemented and tested against the same DB. | 新增後立即 GET，紀錄應出現。 / Create then list. |
| BE-05 | 模組分離、請求驗證、SQL／ORM、錯誤處理 / Engineering standards | 分離 API、Agent、資料庫、檢索、翻譯；使用 Pydantic、參數化 SQL、交易及錯誤回應。ORM 並非強制。 / Modular architecture, validation, parameterized SQL and errors; ORM optional. | 驗證無效日期、未知 ID、不匹配服務及寫入失敗。 / Test validation and failure paths. |
| UI-01 | React 互動聊天介面 / React chat workbench | 已實作，繁體中文與英文對照，支援傳送、等待、錯誤、同請求重試及新對話。 / Implemented bilingual chat and retry controls. | 從頁面跑完整流程。 / Run full flow in browser. |
| UI-02 | 即時或手動更新預約列表 / Live or refreshable booking list | 對話成功後自動讀取，亦可手動重新整理；顯示服務、醫生、日期、時區及 ID。 / Automatic and manual refresh implemented. | 確認預約後列表新增紀錄。 / Check newly saved record. |

## 3. 加分項與非必需功能 / Bonus and non-required features

| 項目 / Item | 是否必須 / Required? | 現況 / Status |
|---|---|---|
| 對話逐字稿醫療摘要 / Transcript summarizer | 加分 / Bonus | 已實作 POST /api/transcripts/summarize 及頁面入口；四欄位、原文證據、缺失為 null。 / Implemented endpoint and UI with evidence-backed four-field output. |
| Langfuse／LLM 追蹤 / LLM observability | 加分 / Bonus | 已有每次 LLM 的模型、response ID、耗時、輸入/輸出 token；無成本計算或 Langfuse。 / Per-call model/ID/latency/tokens; no cost calculation or external tracing. |
| Docker／Kubernetes / Containers | 加分 / Bonus | 有 Dockerfile 與 compose.yaml；未實際驗證容器啟動，無 Kubernetes。 / Docker files supplied, runtime unverified; no Kubernetes. |
| 排班衝突、超額預約 / Schedule conflict detection | 明確不要求 / Explicitly not required | 依題目假設時段可用，未實作衝突檢查。 / Timeslots assumed available. |
| 登入與多病人切換 / Authentication and multiple patients | 簡化假設排除 / Excluded by demo assumption | 固定 P001，沒有登入。 / Fixed P001 without login. |
| MCP 與 REST 同時實作 / Implement both protocols | 不要求 / Not required | 題目為二選一，本作業採 REST；無須另加 MCP 才算符合此條。 / REST selected; MCP is not additionally required. |
| LangChain 等特定框架 / Specific agent framework | 不要求 / Not required | 題目允許自訂 Agent，無須強行加入框架。 / Custom orchestration is allowed. |
| 取消／改期既有預約 / Cancel or reschedule appointments | 未列為必做 / Not specified | 只可取消尚未提交的草稿；已確認預約需聯絡診所。 / Draft cancellation only. |
| 複雜美術效果 / Complex visual design | 明確非評分重點 / Not evaluated | 以清楚、可演示的畫面為主。 / Functional interface prioritized. |

## 4. 提交要求 / Submission requirements

| 要求 / Requirement | 現況 / Status |
|---|---|
| 收到作業後 24 小時內提交 / Submit within 24 hours of receipt | 原始郵件收件時間未提供，無法判定截止時間；需自行依郵件核對。 / Receipt timestamp unknown; confirm from assignment email. |
| 公開 GitHub 原始碼 / Public repository | 已提交至 https://github.com/gjtjx/KUDOS 。 / Published. |
| TECH_DOC.md 技術設計 / Technical design | 已提供架構、意圖、工具流程、資料模型及取捨。 / Provided. |
| README.md 本機設定 / Local setup guide | 已提供環境變數、資料初始化、前後端啟動與測試。 / Provided. |
| 回信附倉庫網址 / Reply with repository link | 未發送郵件；本次工作沒有代寄郵件。 / No email sent. |
| 面試現場演示 / Interview live demo | 本機及真實 Claude 模式已測試；見 LIVE_MODEL_REPORT.md 與 VALIDATION.md。 / Local and live Claude tested; see reports. |

## 5. 面試前仍需確認 / Remaining checks

1. 使用本機已設定的 .env/.env.local 啟動，確認畫面顯示 claude-sonnet-5.5。API 額度與模型可用性可能改變。 / Verify live configuration and provider quota before the demo.
2. 依 LIVE_MODEL_REPORT.md 重跑需要的真實測例，人工檢查繁英語義、引用及摘要；不把小型驗收當成全面模型品質評估。 / Review live language and evidence; small acceptance suites are not comprehensive evaluations.
3. GitHub Actions 先前受帳號帳單鎖定影響，須處理帳號後重跑。 / Resolve the existing account lock before CI reruns.
4. Docker、跨平台、負載及臨床正確性仍未驗收。 / Docker, other platforms, load and clinical correctness remain unverified.

## 6. 本次語言調整 / Language update

介面、按鈕、空白／錯誤提示、固定回覆、預約狀態、服務名稱及診前說明均採繁體／English 對照。原始 CSV、正式姓名、地址、ID 與資料庫原文保持不變，以附加顯示翻譯呈現。簡體、繁體及英文輸入仍可使用。LLM 的繁英輸出已在指定真實測例中驗證；更廣泛品質仍需人工評估。

UI labels, controls, empty/error states, fixed replies, booking statuses, service names and preparation instructions are paired in Traditional Chinese and English. Original CSV records, proper names, addresses and identifiers are preserved. Simplified Chinese, Traditional Chinese and English inputs remain supported. Live bilingual output has been checked for the recorded cases, with broader quality evaluation still required.

目前功能的單元、整合及前端元件測試對照，見 MAINTENANCE.md；實測數量與覆蓋率見 VALIDATION.md。新增就診流程為本次改善，不把資料缺少的院內規定宣稱為原始需求已提供。 / See MAINTENANCE.md for feature-to-test mapping and VALIDATION.md for measured results. Visit orientation is an added improvement; missing on-site policies are not treated as supplied facts.
