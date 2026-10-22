# 測試與驗收 / Validation

**最新提交複核 / Latest submission review: 2026-10-23.**
本頁最新結果對應授權引文、後端狀態回答與顯示正規化修正；[修復驗證](FIX_VALIDATION.md)記錄 118 項後端測試、112 項定向與 82 項完整流程結果；乾淨安裝與瀏覽器證據見 [SUBMISSION_CHECK](SUBMISSION_CHECK.md)。2026-10-22 的兩模型比較另保留為歷史結果。
Current results include the fixes found during the fresh-clone review; the earlier provider comparison remains dated separately.

## 1. 最新結果 / Latest recorded results

| 驗證 / Validation | 結果 / Result |
|---|---|
| 後端單元／整合 / Backend unit and integration | 118 passed |
| 前端單元／元件 / Frontend unit and component | 28 passed |
| 自動化測試合計 / Automated test total | 146 passed |
| 後端行／分支合併覆蓋率 / Backend combined coverage | 97.64% |
| 前端覆蓋率 / Frontend coverage | Lines/functions 100%; statements 99.23%; branches 93.83% |
| React 正式建置 / Production build | Passed |
| DeepSeek 真實核心流程 / Live core acceptance | 82/82 checks, 2026-10-23 |
| DeepSeek 修復回歸 / Fix regressions | 112/112 checks, 11 scenarios / 20 turns |
| 常見問題 / Common questions | 20 replies reviewed; 84/84 mechanical checks; two minor wording observations |
| Poe Sonnet 歷史流程 / Historical Sonnet acceptance | 82/82 checks, 2026-10-22; 本次未重跑 / not rerun |
| 部署設定離線驗證 / Offline deployment validation | 2 Compose files, 5 Kubernetes resources |
| Docker／Kubernetes 執行 / Container and cluster runtime | 未驗收 / Not verified |
| 雲端 CI / Cloud CI | 無本版成功證據 / No successful run claimed for this implementation |

環境 / Environment: Windows, Python 3.13, Node 22.15, Vite 6.4.5, Vitest 4.1.12.
本次為後端修復；前端未變動，28 項結果保留自先前驗證，本次未重跑。 / Frontend results are retained from the unchanged earlier build, not rerun in this backend fix.
覆蓋率反映程式執行路徑，不是自然語言理解或臨床正確率。 / Coverage is not language or clinical accuracy.

## 2. 測試分層與責任 / Test layers and coverage

| 層次 / Layer | 位置 / Location | 涵蓋範圍 / Coverage |
|---|---|---|
| 回答修復 / Answer regressions | [test_answer_regressions.py](backend/tests/test_answer_regressions.py) | Authorization provenance, held drafts, authoritative lookup, catalog scope, formatting and verbatim evidence |
| 核心單元 / Core units | [test_units.py](backend/tests/test_units.py) | 路由、欄位、回答、翻譯、檢索與驗證 / Routing, slots, answers, localization, retrieval |
| API／資料 / API and database | [test_app.py](backend/tests/test_app.py)、[test_regressions.py](backend/tests/test_regressions.py) | 真實 SQLite、種子、FTS、狀態、持久化、錯誤與重試 / Persistence and API regressions |
| 提交與邊界 / Submission controls | [test_extended.py](backend/tests/test_extended.py) | hold、撤回、更正、跨輪／重啟、併發重試／衝突 / Consent, state and idempotency boundaries |
| 模型／摘要 / Provider and summary | [test_llm_features.py](backend/tests/test_llm_features.py) | API 形狀、錯誤、路由修復、摘要引文、null、無副作用 / Mocked contracts and bounded repairs |
| 追蹤 / Tracing | [test_observability.py](backend/tests/test_observability.py) | 隔離、保留、隱私、錯誤與重啟 / Lifecycle, retention and failure handling |
| 部署設定 / Deployment configuration | [test_deployment.py](backend/tests/test_deployment.py) | Schema 與資源參照；不執行容器 / Offline validation only |
| 前端 / Frontend | [frontend/src/test](frontend/src/test) | 聊天、API、摘要、追蹤、刷新、輸入法及重試 / UI and API-client behavior |
| 真實核心流程 / Live core flow | [live_acceptance.py](scripts/live_acceptance.py) | 真實供應商、REST／SQL、持久化與追蹤 / End-to-end provider acceptance |
| 真實額外情境 / Live edge cases | [expanded_acceptance.py](scripts/expanded_acceptance.py) | 暫緩、撤回、歧義、引用與摘要 / Expanded behavioral cases |
| 常見問法 / Common questions | [common_questions_acceptance.py](scripts/common_questions_acceptance.py) | 16 scenarios / 20 turns; inspect response content as well as assertions |
| 擴大情境 / Diverse scenarios | [diverse_questions_acceptance.py](scripts/diverse_questions_acceptance.py) | 64 scenarios / 83 turns; [results and open findings](DIVERSE_QUESTIONS_REPORT.md) |

單元／整合測試中的受控模型輸出驗證應用邏輯；真實模型測試另外驗證供應商與實際語言行為，兩者不可互相替代。
Mocked contracts and live-provider evidence answer different questions.

## 3. 重跑本機測試 / Run local tests

從專案根目錄，在新的 PowerShell 視窗執行；完成後關閉該視窗，避免測試環境變數影響下一次啟動。
Run in a fresh PowerShell window from the project root, then close it to discard test-only environment overrides.

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
$env:PYTHONPATH="backend"
$env:AI_MODE="local"
.\.venv\Scripts\python.exe -m coverage run -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe -m coverage report
.\.venv\Scripts\python.exe -m coverage html
cd frontend
npm.cmd ci
npm.cmd run test:coverage
npm.cmd run build
cd ..
```

後端測試使用 `runtime/tests` 下獨立資料庫，不寫入 `runtime/clinic.db`。HTML 報告位於 `runtime/coverage-backend/index.html` 及 `frontend/coverage/index.html`。
Backend tests isolate database state; the paths above contain coverage reports.

門檻為後端合併覆蓋率 95%；前端行／敘述／函式 90%、分支 80%。前端 `.npmrc` 的 `legacy-peer-deps` 配合已鎖定測試依賴，需保留於安裝與容器建置流程。
Coverage gates are enforced by the existing test configuration; preserve the committed npm configuration.

## 4. 真實流程與重現 / Live acceptance and reproduction

本次 DeepSeek 核心複核包含 14 輪對話、2 則摘要及 1 次快取重試；核對問答、指代、意圖、缺欄位、中途問答、建立與更正、草稿取消、REST／SQL 紀錄、重啟與追蹤用量。
The live suite checks conversational behavior and actual persisted results rather than generated success text alone.

本次 run ID 與發現見 [SUBMISSION_CHECK](SUBMISSION_CHECK.md)；供應商設定、完整命令及先前比較維護於 [MODEL_COMPARISON](MODEL_COMPARISON.md)。執行會消耗 API 額度，報告及隔離 DB 留在本機 runtime；不發布原始對話或憑證。
Use the comparison report as the reproducibility reference. Retain failed runs and investigate them rather than rerunning until success.

## 5. 歷史證據 / Historical evidence

- [LIVE_MODEL_REPORT](LIVE_MODEL_REPORT.md)：早期 Claude 78 項核心驗收、瀏覽器引文失敗與修復。 / Earlier Claude acceptance and browser findings.
- [EXTENDED_TEST_REPORT](EXTENDED_TEST_REPORT.md)：暫緩／撤回等真實問題、167 項額外檢查及中間失敗紀錄。 / Additional scenarios and regression history.

歷史數量不與最新 82 項相加，也不是目前測試總數。當時瀏覽器測試使用隔離 8017 埠，完成繁英回答、多輪新增、列表更新及摘要；不能當成所有模型、環境或問法的瀏覽器驗收。
Historical counts describe different revisions and suites, not extra current coverage or a user success rate.

## 6. 尚未驗證 / Unverified boundaries

- 廣泛自然語言品質、臨床正確性、完整提示注入防護。 / Comprehensive language, clinical and security quality.
- Docker／Kubernetes runtime、其他作業系統、多 worker、負載及完整 DST 歧義。 / Container runtime, cross-platform, distributed/load and DST behavior.
- GPT-6 Astra High 沒有獨立 API 對跑，沒有其延遲、Token 或得分。 / The Codex-selected model was not independently benchmarked.
- [先前 GitHub Actions run](https://github.com/gjtjx/KUDOS/actions/runs/39775522266) 因帳號帳單限制未執行；本次重新查詢仍只有該失敗 run，沒有最新提交成功紀錄；未查帳單狀態。 / An earlier run was blocked; the run listing still contains only that failed run; billing eligibility was not inspected.

部署驗收程序見 [DEPLOYMENT](DEPLOYMENT.md)，失敗排查見 [MAINTENANCE](MAINTENANCE.md)。
