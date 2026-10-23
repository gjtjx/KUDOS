# 維護手冊 / Maintenance Manual

適用於固定 P001、單 worker 的本機示範。啟動與模型參數以 [README](README.md#model-configuration) 為準；測試命令與功能對照集中於 [VALIDATION](VALIDATION.md)。
This manual covers operations and recovery, without duplicating setup or test specifications.

## 1. 設定與啟停 / Configuration and lifecycle

在根目錄執行 `setup.cmd` 安裝／建置，`start.cmd` 啟動，Ctrl+C 停止。只使用一個 worker；對話鎖不能跨程序共享。
Use the Windows launchers and a single worker. For other startup methods, follow README.

| 設定 / Setting | 行為 / Behavior |
|---|---|
| `AI_MODE` | 預設 local；llm 需要完整供應商設定。 / Explicit demo or live-provider mode. |
| `.env` | 唯一自動載入的設定檔，程序環境變數優先。 / Loaded automatically; process environment takes precedence. |
| `.env.local`、`1.env` | 不自動載入；只有明確指定的工具才讀取。 / Not automatically loaded. |
| `DATABASE_PATH` | 預設 runtime/clinic.db；變更前備份，優先使用完整路徑。 / Back up before switching databases. |
| `LLM_API_KEY_FILE` | 若設定，檔案內密鑰優先於 key 環境變數。 / A mounted key file overrides key variables. |
| `TRACE_ENABLED`、`TRACE_MAX_RECORDS` | 見 [OBSERVABILITY](OBSERVABILITY.md)。 / Trace collection and retention. |

修改設定後重啟，以 `/api/health` 核對 mode/model/api_style。健康端點不呼叫供應商；一則成功真實提問才能驗證當時連線可用。不要輸出整份環境變數或設定檔。
Restart after changes. Inspect non-secret health metadata rather than dumping configuration.

## 2. 日常檢查 / Routine checks

1. 確認 `/api/live`、`/api/ready`、個人資料、目錄與預約列表可讀。 / Check process, database and read endpoints.
2. 新對話詢問「我到醫院的流程」，確認有依據的回答且沒有新增預約。 / Test visit guidance without writes.
3. 核對列表 ID 與筆數；重載或重啟後資料應保留。 / Check persistence.
4. 在模型使用紀錄查看錯誤分類及用量；追蹤故障可能造成統計缺漏。 / Inspect traces without treating them as complete audit guarantees.

新對話更換 session、清除畫面和未送出輸入，不刪既有預約；舊 session 仍在 DB。頁面重載保留 session，但不恢復聊天氣泡。
New chat and page reload have different UI/state behavior.

## 3. 備份與還原 / Backup and restore

預約、session、重試鍵與追蹤在同一 SQLite 檔，應一起備份。使用 SQLite backup API 取得一致快照；不要直接複製寫入中的 DB。若設定 `DATABASE_PATH`，將下例 source 改成相同完整路徑。
Use a consistent snapshot, including business state and idempotency records.

在專案根目錄執行 / Run from the project root:

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
with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src:
    with sqlite3.connect(target) as dst:
        src.backup(dst)
        assert dst.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
print(target.resolve())
'@ | .\.venv\Scripts\python.exe -
```

還原順序 / Restore sequence:

1. 停止服務，保留目前 DB 的備份。 / Stop and preserve the current database.
2. 對候選備份執行 `PRAGMA integrity_check`，確認為 `ok`。 / Validate the backup.
3. 將備份複製到新路徑，讓 `DATABASE_PATH` 指向該副本。 / Restore to a new path.
4. 啟動並核對 P001、預約 ID／筆數及對話狀態，驗收前保留舊檔。 / Verify before retiring old data.

不要提交 DB、備份、原始對話報告或密鑰。容器儲存與檔案權限另見 [DEPLOYMENT](DEPLOYMENT.md)。
Database snapshots and raw reports are local operational data, not submission artifacts.

## 4. 更新資料與行為 / Updating data and behavior

- CSV 是缺失 ID 初始化；修改同 ID 欄位後重啟不會覆蓋資料庫。先備份，再做明確可回退的資料遷移。 / Existing records require an explicit migration.
- 示範重置可指向新的空 DB，保留舊檔；不應為更新目錄刪除預約。 / Reset a separate demo database.
- FTS 索引啟動時由 DB 目錄重建；更新後檢查來源 ID 與相關問題。 / Verify retrieval after catalog updates.
- 新增醫生／服務須維護 `doctor_treatments`、別名、翻譯與測試；`MATCHES` 僅為空關聯表的初始化預設值。新診所須提供時區。 / Maintain the database bridge; MATCHES seeds an empty bridge only.
- 路由或回答出錯時，先把實際原句轉成回歸測例，再修改 `agent.py`、`knowledge.py` 或 `answers.py`。 / Reproduce defects before changing behavior.

就診導覽不能虛構櫃台、保險、付款、動線或提前到院規定。保留資料中的條件，例如 T001 僅在已安排抽血時要求空腹。
Service guidance must preserve missing information and conditional instructions.

患者醫生問題先核對 `GET /api/patient-doctors`、病歷 JOIN 與即時預約狀態；不可把下一次預約或全科專長當成主治指定。既有資料庫在首次使用新版時新增關聯表，保留預約、病歷與會話；升級前按本手冊備份。 / Verify relationship facts before prompts. The additive bridge initialization preserves existing records; back up before updating. To change compatibility, update the bridge in a transaction and recheck both retrieval and booking rejection. An emptied bridge is reseeded on restart.

## 5. 排錯 / Troubleshooting

| 現象 / Symptom | 處理 / Action |
|---|---|
| 模型或模式不符 / Wrong mode/model | 查健康端點；核對程序環境是否覆寫 .env，確認啟動目錄及重啟。 / Check process overrides and launch directory. |
| 無關回答或錯意圖 / Wrong answer/intent | 保存原句、mode、intent、來源 ID，在隔離 DB 重現。LLM 查 route_intent／檢索；local 查規則／模板。 / Debug the active mode's actual path. |
| 畫面舊版 / Stale UI | 重建 frontend、重啟並刷新。 / Rebuild and reload. |
| Windows 測試依賴安裝出現路徑不存在 / Long-path installation failure | 在短路徑重新 clone 並重建 .venv；Kubernetes schema 套件可能超過 Windows 路徑限制。 / Recreate the checkout and environment at a short path. |
| 埠被佔用 / Port conflict | 確認自己的舊服務或改埠，勿任意終止不明程序。 / Resolve only the intended server instance. |
| 422 | 檢查欄位、醫生服務相容性、成人限制及診所當地未來時間。 / Check validation and business rules. |
| 409 | 同 ID 配不同內容；重試保留原內容，新操作用新 ID。 / Preserve retry identity. |
| 502 | 查安全錯誤分類、供應商狀態及完整相容設定；勿當成必然同一根因。 / Inspect provider/configuration failures. |
| 503／database locked | 檢查路徑權限、磁碟、單 worker 與長期鎖；恢復後重試原請求。摘要在 local 模式亦會回 503。 / Check database availability or enable LLM mode for summaries. |
| 已成功但列表未更新 / Saved but stale list | 手動刷新並核對 ID，不再建立同筆預約。 / Refresh rather than resubmit. |
| 預約後聊天保存失敗 / Post-booking chat-save failure | 以原 session/request/message 重試，穩定預約鍵防重複。 / Recover using the original identifiers. |
| 沒有「下一次」預約 / No next appointment | 只有未來且 Confirmed 的紀錄符合條件。 / Check status and clinic-local time. |
| 摘要引文失敗 / Invalid evidence | 查看錯誤；最多一次修復仍不合格即失敗，不繞過驗證。 / Do not weaken evidence checks to force success. |

供應商 400／401／402／404 等會轉成應用安全錯誤（通常 502），不代表瀏覽器直接收到相同供應商 HTTP 狀態。分類與已重現問題見 [MODEL_COMPARISON](MODEL_COMPARISON.md)。
Provider status and application HTTP status are distinct.

## 6. 發版、回退與真實回歸 / Release, rollback and live regression

1. 備份 DB，記錄 commit、依賴與非機密設定名稱。 / Preserve state and record the version.
2. 程式變更執行 [VALIDATION](VALIDATION.md) 的測試及建置；文件變更檢查內容、連結、命令與敏感資訊。 / Match verification to the change.
3. 更新程式及 frontend/dist 時保留 .env、runtime 與備份；重啟後做日常檢查。 / Preserve configuration and data.
4. 失敗先回退程式／資產；資料還原只在確有需要時進行，先保留新增紀錄。 / Avoid unnecessary data rollback.

真實回歸使用 [MODEL_COMPARISON](MODEL_COMPARISON.md) 的完整供應商設定與隔離測試指令，會消耗 API 額度。保留失敗報告，檢查 intent、來源、工具及 DB，不只重跑到成功。
Live regressions require matching credentials and preserved failure evidence.

目前驗收範圍見 VALIDATION；雲端 CI 的先前帳號限制與容器 runtime 未驗收，不能用本機測試結果替代。

## 雙語生成校驗 / Bilingual generation validation

已重現的根因：互相衝突的文字／JSON 提示，加上把「不代表她不能說其他語言」當作能力否定的校驗誤報。檢查內部 JSON 契約與否定作用範圍，重跑 `test_bilingual_negation.py`；不要關閉校驗或無限重試。
The corrected incident involved conflicting output instructions and negation scope. Reproduce with the bounded regression tests rather than disabling validation or retrying indefinitely.

`invalid_bilingual_answer` means the provider failed the internal paragraph/language checks after one repair. Verify the configured provider/model, preserve the failed isolated report and reproduce with the scenario ID. Do not bypass validation or paste credentials into logs. The public reply remains text; no frontend migration is needed. See [REMAINING_FIXES_REPORT.md](REMAINING_FIXES_REPORT.md).
