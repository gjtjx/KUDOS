# 維護手冊 / Maintenance Manual

適用版本：2026-10-22。維護對象為固定病人 P001 的本機示範系統。原始需求逐項核對見 [REQUIREMENTS_REVIEW.md](REQUIREMENTS_REVIEW.md)，測試結果見 [VALIDATION.md](VALIDATION.md)。

Applies to the local single-patient P001 demo. See the requirements review for scope and the validation report for measured results.

## 1. 啟動、停止與設定 / Start, stop and configure

在專案根目錄執行 `setup.cmd` 安裝及建置，再執行 `start.cmd`。頁面為 http://127.0.0.1:8000 ，API 文件為 http://127.0.0.1:8000/docs 。伺服器視窗按 Ctrl+C 停止。使用單一 worker；不支援多程序共享對話鎖。

Run `setup.cmd`, then `start.cmd` from the project root. Stop with Ctrl+C in the server window. Use a single worker; conversation locks are process-local.

| 設定 / Setting | 用途與變更方式 / Purpose and change procedure |
|---|---|
| `AI_MODE=local` | 預設規則與模板模式，不呼叫外部模型。 / Default deterministic rules and templates; no remote model call. |
| `AI_MODE=llm` | 設定 `LLM_API_KEY`、`LLM_MODEL` 及 `LLM_BASE_URL` 後重新啟動。 / Set credentials/model/base URL and restart. |
| `DATABASE_PATH` | 預設 `runtime/clinic.db`；變更前備份並使用完整路徑。 / Defaults to runtime/clinic.db; back up before changing and prefer an absolute path. |
| `.env` | 從 `.env.example` 複製；禁止提交密鑰。程序環境變數優先於此檔。 / Copy the example; never commit secrets. Process environment takes precedence. |

啟動後查詢 `/api/health` 並核對畫面的 LOCAL／LLM 標籤。不要只憑 `.env` 判斷實際模式。LLM 模式會把模擬病人與對話資料送往所設定的服務商。

Check `/api/health` and the UI mode badge after restarting. LLM mode sends mock patient and conversation context to the configured provider.

## 2. 日常檢查 / Routine checks

1. 確認健康檢查、患者資料、服務目錄及預約列表可讀取。 / Verify health, profile, catalog and booking reads.
2. 點「新對話」輸入「我到医院的流程」，應出現分步繁英導覽；有未來預約時附上實際地址及服務準備說明。此問題不應新增預約。 / Start a new chat with the reported phrase; expect bilingual steps and grounded details without a booking write.
3. 查看預約數量與 ID，確認重新整理後一致。 / Check booking IDs and counts survive refresh.
4. 發版前在隔離測試資料庫執行下列完整測試。 / Run the full isolated suite before releasing.

不要用正式示範資料庫做大量新增或破壞性測試；所有自動化後端測試使用 `runtime/tests` 下的暫存資料庫。

Do not run destructive tests against the demo database. Automated backend tests use temporary databases under `runtime/tests`.

## 3. 測試操作與功能對照 / Tests and feature mapping

PowerShell，從專案根目錄執行。若未使用虛擬環境，以已安裝相同依賴的 `python` 代替下方路徑。

Run from the project root. If no virtual environment is used, substitute a Python installation with the same dependencies.

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
$env:PYTHONPATH = "backend"
$env:AI_MODE = "local"
.\.venv\Scripts\python.exe -m coverage run -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe -m coverage report
.\.venv\Scripts\python.exe -m coverage html
Set-Location frontend
npm.cmd ci
npm.cmd run test:coverage
npm.cmd run build
Set-Location ..
```

後端報告位於 `runtime/coverage-backend/index.html`；前端報告位於 `frontend/coverage/index.html`。門檻：後端行與分支合併至少 95%；前端行、敘述、函式至少 90%，分支至少 80%。覆蓋率不能代表自然語言或臨床正確率。

Backend and frontend HTML reports are at the paths above. Gates: 95% combined backend coverage; frontend 90% lines/statements/functions and 80% branches. Coverage is not a measure of language understanding or clinical accuracy.

| 功能 / Feature | 單元測試 / Unit tests | 整合或元件測試 / Integration or component tests |
|---|---|---|
| 簡繁英意圖、名稱/ID、日期時間 / Routing and slot parsing | `test_units.RoutingTests` | `test_app` 多輪、插入問答、更正 / multi-turn, interleaving, correction |
| 就診流程導覽 / Visit guide | `AnswerTests` 語言變體、無預約、時間排序 / variants, empty bookings, ordering | `test_regressions` 原句、繁體、草稿中提問、新 session / original phrase, Traditional Chinese, active draft, new session |
| RAG 與推薦 / Retrieval and recommendations | `RetrievalTests`, `AnswerTests` | `test_app` 與 `test_regressions` 真實 FTS 檢索 / real FTS |
| 雙語顯示與輸入 / Bilingual display/input | `LocalizationTests` | `test_app` 繁英預約確認 / bilingual confirmation |
| 欄位驗證 / Input validation | `ModelTests` | `test_app` 錯誤日期、ID、專科、成人限制 / invalid values and business rules |
| LLM 合約、網路失敗 / Model contract and errors | `RoutingTests` 模擬 HTTP、無效工具與欄位 / mocked HTTP and invalid output | `test_app` 模擬工具呼叫與 502 / mocked orchestration |
| 六表匯入、外鍵、交易、索引 / Seed, FKs, transactions, index | `test_regressions` 直接資料層測試 / direct data-layer tests | `test_app` 重啟持久化 / restart persistence |
| 查詢與建立預約 REST / Booking REST tools | 路由及資料驗證單元測試 / routing and validation units | `test_app` 真實 FastAPI、SQLite、工具紀錄 / real REST handlers and database |
| 重試與防重複 / Retries and deduplication | API 客戶端錯誤處理 / frontend API error tests | `test_app` key 衝突、寫入後保存失敗；`App.test.jsx` 重試保留 ID / conflict, post-commit failure, retained request ID |
| 健康、患者、目錄、首頁 / Health, profile, catalog, homepage | 翻譯與資料模組測試 / localization and data units | `test_app`, `test_regressions` API 與患者隔離 / endpoint and patient scope tests |
| 聊天、快捷問題、Enter、輸入法、等待 / Composer and interaction | `api.test.js` | `App.test.jsx` 傳送、空白拒絕、IME、等待鎖 / send, blank prevention, IME, pending controls |
| 新對話、草稿、來源與紀錄 / New chat, draft, evidence | session 與回答單元測試 / state and answer units | `App.test.jsx` 清空未送出文字、更換 session、證據呈現 / reset unsent text/session and evidence |
| 預約列表、刷新失敗及恢復 / Booking refresh and recovery | API 客戶端單元測試 / API client units | `App.test.jsx` 自動與手動刷新、失敗恢復 / auto/manual refresh and recovery |

前端 .npmrc 使用 legacy-peer-deps 避開 npm 10 的可選瀏覽器 peer 解析錯誤，所需測試 peer 已直接鎖定於 package.json。 / The frontend .npmrc avoids an npm 10 optional browser-peer resolution crash; required test peers are explicitly pinned.

CI 設定已加入上述測試與覆蓋率門檻。先前 GitHub Actions 因帳號帳單鎖定未啟動；需由倉庫擁有人處理帳號問題。這與本機測試是否通過是兩回事。

CI contains the same checks. The previous GitHub Actions run was blocked by an account billing lock; the repository owner must resolve it. Local results do not imply a successful CI run.

## 4. 資料備份與還原 / Backup and restore

備份預約、對話及防重複紀錄必須一起保留；它們都在同一 SQLite 檔。使用 SQLite backup API 取得一致快照，不直接複製正在寫入的資料庫。若設定了 `DATABASE_PATH`，把 `source` 改成相同完整路徑。

Keep bookings, sessions and idempotency records together in one SQLite snapshot. Use the backup API for a consistent snapshot rather than copying a database during writes. Match `source` to your configured database path.

```powershell
@'
import sqlite3
from pathlib import Path
from datetime import datetime
source = Path("runtime/clinic.db").resolve()
if not source.is_file():
    raise SystemExit("Source database does not exist")
folder = Path("runtime/backups")
folder.mkdir(parents=True, exist_ok=True)
target = folder / ("clinic-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".db")
with sqlite3.connect(source.as_uri()+"?mode=ro", uri=True) as src:
    with sqlite3.connect(target) as dst:
        src.backup(dst)
        assert dst.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
print(target.resolve())
'@ | .\.venv\Scripts\python.exe -
```

還原步驟：停止服務 → 保留目前資料庫的備份 → 對候選備份執行 `PRAGMA integrity_check`，確認為 `ok` → 將備份複製成新的完整路徑 → 將 `DATABASE_PATH` 指向該副本 → 啟動並核對預約 ID、筆數與患者。保留舊檔直到驗收通過。備份及對話可能包含敏感資料，不加入 GitHub 或交付壓縮檔。

Restore: stop the server, preserve the current database, integrity-check the backup, copy it to a new path, point `DATABASE_PATH` to that copy, restart and verify IDs/counts/patient scope. Retain the old file until acceptance. Never publish databases or backups.

## 5. 更新資料與回答 / Update data and responses

- 原始 CSV 以 ID 存在與否決定插入，重啟不會覆蓋已存在的紀錄。修改 CSV 後直接重啟，並不會更新舊資料庫的同 ID 欄位。 / Startup inserts missing IDs; editing CSV does not overwrite existing database rows.
- 更新既有資料需先備份，再使用明確、可回退的資料遷移；示範重置可指向新的空資料庫，保留舊檔。禁止為更新目錄直接刪除預約資料。 / Back up and migrate existing rows explicitly, or use a new demo database while retaining the old one.
- FTS 索引啟動時由資料庫的 clinics/doctors/treatments 重建。更新資料後重新啟動並測試相關問題及來源 ID。 / The index rebuilds from database catalog tables at startup; verify affected questions and IDs.
- 翻譯及簡繁詞彙在 `localization.py`；查詢擴展在 `knowledge.py`；意圖與欄位抽取在 `agent.py`；精簡回答與流程導覽在 `answers.py`。先加使用者原句的失敗測試，再修改。 / Add a failing regression for the actual utterance before changing normalization, retrieval, routing or answer rendering.
- 新增醫生或服務時，同時維護 `MATCHES` 專科映射、ID/別名、翻譯與測試；新增診所時維護時區映射。 / Update specialty mappings, aliases, translations and tests; new clinics also need a timezone.

就診流程回覆是一般導覽。原始資料沒有櫃台報到、保險、付款、院內動線或固定提前到院時間，不能把推測寫成診所規定。預約地址、時間及準備說明須取自實際資料；例如 T001 空腹要求僅限已安排抽血時。

The visit guide is general orientation. Do not invent clinic check-in, insurance, payment, internal directions or required arrival lead time. Preserve conditions in preparation instructions, including fasting only if blood tests are scheduled.

## 6. 故障排查 / Troubleshooting

| 現象 / Symptom | 處理 / Action |
|---|---|
| 回答無關、堆出資料 / Irrelevant or noisy answer | 記錄原句、實際模式、intent 與來源 ID；用新 session 在隔離資料庫重現。依序檢查 `is_visit_flow`、route、retrieve、local_answer。不要把過敏資訊無條件加入所有回答。 / Capture phrase/mode/intent/source IDs and reproduce in isolation; inspect routing, retrieval and rendering. |
| 畫面仍是舊版本 / Stale page | 重新建置前端、重啟服務，瀏覽器重新整理。檢查啟動目錄是否正確。 / Rebuild frontend, restart, refresh, and verify the launched directory. |
| 8000 埠已佔用 / Port occupied | 確認原服務是否仍在運行，停止自己的舊服務或改用另一埠；不要任意終止不明程序。 / Check the existing server; stop your own instance or use another port. |
| 422 | 檢查四個預約欄位、未來日期、診所當地時間、醫生服務映射、P001 成人限制。 / Check slots, future local time, mappings and patient constraints. |
| 409 | 同 request_id 被用於不同內容；原請求重試維持內容，新操作換新 ID。 / Preserve the original payload on retry; use a new ID for new content. |
| 502 | 查實際 LLM 模式、憑證、模型工具能力、網路與供應商狀態；日誌只記錯誤類型。 / Check mode, credentials, tool support and connectivity; logs contain failure categories only. |
| 503 / database locked | 檢查路徑權限、磁碟空間、單 worker 及是否有其他程式長時間鎖住檔案。修復後重試相同請求。 / Check permissions, space and locks; retry the same request after recovery. |
| 已確認但列表未更新 / Confirmation but stale list | 按重新整理；對照預約 ID。不要再建立相同預約。 / Refresh and compare IDs rather than submitting another booking. |
| 預約後回覆保存失敗 / Chat-save failure after booking | 用原 session/request ID 重試；防重複鍵會返回原預約。 / Retry the same identifiers; idempotency recovers the original booking. |
| 沒有下一次預約 / No next appointment | 只有未來且 Confirmed 的紀錄入選；用診所時區換算後排序。 / Only future Confirmed records qualify, ordered by actual instant. |
| 本機模式不懂自由表達 / Local mode misses wording | 有限規則不是完整語言模型。補充名稱/ID/ISO 日期，或配置 LLM 並完成真實服務驗收。 / Clarify fields or configure and validate a live model. |

新對話會更換 session 並清空畫面與未送出輸入，不刪除已儲存預約；舊 session 仍留在資料庫。頁面重載保留 session，但不恢復聊天氣泡；如要明確重新開始，按「新對話」。

New chat rotates the session and clears the UI/unsent input without deleting saved bookings. Old sessions remain stored. Reload retains the session but does not restore chat bubbles; use New chat to start afresh.

## 7. 發版與回退 / Release and rollback

1. 備份資料庫，記錄目前 commit、環境變數名稱及依賴版本；不把密鑰寫入紀錄。 / Back up and record commit/configuration names and dependency versions without secrets.
2. 安裝鎖定依賴，執行完整測試、覆蓋率、前端建置；檢查 `npm audit`，依相容性選擇修補版本，不盲目強制升級。 / Install locked dependencies, run tests/coverage/build and review dependency advisories.
3. 停止舊服務，更新程式與前端 dist，保留 `.env`、runtime 及備份，再啟動。 / Stop, update code/assets, preserve environment/data/backups, then restart.
4. 執行第 2 節檢查。如失敗，部署上一版原始碼並重建；只有資料格式確實變更且需要還原時才使用備份，先保存失敗版本新增的資料。 / Smoke-test; roll back code/assets if needed. Restore data only when schema changes require it, preserving new records first.

本版本沒有資料表遷移。真實 LLM、Docker 執行、跨平台、負載及 DST 歧義時間仍需獨立驗收；單元測試不能取代這些檢查。

This release has no schema migration. Live LLM, Docker runtime, other platforms, load and DST ambiguity still need separate acceptance.
