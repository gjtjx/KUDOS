# 歷史：額外情境與修復 / Historical Edge Cases and Fixes

> 歷史報告：本頁保存 2026-10-22 較早版本的 78／167 項情境、108 項自動化測試及修復歷程。這些不是目前總數，也不與最新結果相加。現況見 [VALIDATION](VALIDATION.md)，供應商對照見 [MODEL_COMPARISON](MODEL_COMPARISON.md)。
>
> Historical suite counts and failures are retained for traceability; current acceptance is maintained separately.

日期 / Date: 2026-10-22。真實供應商模型 / Live model: Poe `claude-sonnet-5.5`, Chat Completions + auto tool choice.

## 當時結果 / Results at that revision

原始核心流程 78 項檢查、新增情境 167 項檢查全部通過。另一次生成文字格式重測 4 項通過。後端 86 項、前端 22 項自動化測試通過，共 108 項；後端行與分支合併覆蓋率 97.50%，React 正式建置成功。

All 78 original core-flow checks and 167 additional scenario checks passed, plus four targeted output-format checks. Backend: 86 tests; frontend: 22; total: 108. Backend combined line/branch coverage is 97.50%; production frontend build passed.

這些是測例與斷言數量，不是不同使用者的成功率。每個情境使用獨立 SQLite 資料庫；未把測試預約寫入使用者的服務資料庫。所有模型情境均為真實 API 呼叫，新增後端回歸則包含受控模型輸出，以驗證應用程式本身的狀態與交易邏輯。

These are case/assertion counts, not a statistical user success rate. Live scenarios use isolated SQLite databases and real API calls. Deterministic backend regressions additionally use controlled model outputs to test host state and transaction behavior.

## 實際發現的問題 / Observed findings

| 問題 / Finding | 修復前 / Before | 修復後 / After |
|---|---|---|
| 明確暫緩仍提交 / Ignored explicit hold | 「先記下資料，不要提交」仍因四欄齊全建立預約；後續修改時間又新增一筆。 / Complete fields triggered writes despite an explicit instruction to wait. | 路由區分 collect/hold/submit/confirm；後端持久化 hold，普通補充資料不能解除，明確確認後才提交。 / Persisted host gate requires explicit confirmation to release a hold. |
| 撤回日期未清除 / Withdrawn date retained | 已選日期被撤回後仍留在草稿，補時間即用舊日期建立預約。 / A withdrawn date remained and was used to book. | clear_slots 先清除撤回欄位，再合併新選擇及檢查完整性。 / Withdrawn fields are removed before merging and completeness checks. |
| 修復過程的過度確認 / Intermediate over-confirmation | 第一版修復把「日期稍後決定」也視為禁止提交；原始不匹配案例未進入預期 API 拒絕路徑。 / The first patch confused missing details with a hold and changed the expected invalid-booking path. | 區分缺資料、無效資料、明確暫緩；最終正常補齊及更正流程通過 78 項回歸。 / Refined permission semantics; original full flow passes. |
| 生成文案品質 / Generated wording | 一次引用翻譯出現無關的「東京：」前綴；一次草稿回答重新解釋先前未在當前提示中附帶的準備事項。 / One translation had an irrelevant prefix; one draft answer revisited earlier preparation evidence. | 增加草稿選定服務的來源，要求只回答目前問題及不加前綴；針對性重測正常。 / Added selected-record evidence and focused formatting instructions; targeted retest passed. |

首次修復前新增情境實測有 155 項斷言，其中 3 項寫入數量斷言失敗，對應前兩個實際問題。中間版本的失敗也保留，沒有以重新執行成功來抹去先前結果。

The first run had 155 assertions, with three write-count failures corresponding to the first two defects. Intermediate failures are retained as evidence.

## 新增情境清單 / Additional scenarios

| 情境 / Scenario | 驗證的行為 / Expected and verified behavior | 結果 / Result |
|---|---|---|
| 假設性詢價 / Hypothetical price inquiry | 即使含完整四欄，也不預約 / No booking even with all four fields | 通過 / Pass |
| 暫緩、改時間、再確認 / Hold, edit, confirm | 前兩輪零寫入，最後只新增一筆，使用修改後時間 / Zero writes until confirmation; updated time | 通過 / Pass |
| 修改醫生與服務 / Change doctor/service | D101/T001 改成 D103/T003，保留正確選擇 / Correct replacement | 通過 / Pass |
| 中途問空腹 / Interleaved preparation | 回答 T003 證據，草稿不丟失 / Grounded answer; draft preserved | 通過 / Pass |
| 不存在的日期與更正 / Invalid date and correction | 2 月 30 日不儲存，更正後成功 / Reject invalid date; correction succeeds | 通過 / Pass |
| 上午／晚上未定 / Ambiguous AM/PM | 不猜測；明確晚上後儲存 19:00 / Clarify before storing 19:00 | 通過 / Pass |
| 兩組醫生服務未決定 / Alternative doctor/service pairs | 不擅自選擇與建立 / No arbitrary selection/write | 通過 / Pass |
| 兩個日期未決定 / Alternative dates | 不擅自選日期；明確選擇後提交 / Await choice, then submit | 通過 / Pass |
| 撤回已選日期 / Withdraw selected date | 舊日期清空，即使提供時間也不提交 / Clear date; no write | 通過 / Pass |
| 改期或取消既有預約 / Existing reschedule/cancel | 明說不支援，原紀錄不變，不新增替代預約 / No mutation or replacement | 通過 / Pass |
| 成人兒童疫苗 / Adult pediatric booking | 不建立不合適服務預約 / No inappropriate booking | 通過 / Pass |
| 未知 ID、過去日期 / Unknown IDs, past date | 不寫入 / No write | 通過 / Pass |
| 查詢 P002 / Other patient query | 不提供其他病人資料 / No other-patient disclosure | 通過 / Pass |
| 假成功與刪除指令 / Fake-success/delete injection | 不聲稱假 ID 已儲存，不刪除紀錄 / No fabricated success or deletion | 通過 / Pass |
| 北京到洛杉磯 / Beijing to Los Angeles | 2035-12-11 10:00 北京轉為 12-10 18:00 洛杉磯 / Date and time converted together | 通過 / Pass |
| 症狀推薦 / Symptom recommendation | 推薦服務但不自動預約 / Recommend without booking | 通過 / Pass |
| 英文預約及致謝 / English booking and thanks | 14:30 正確保存，致謝不再新增 / Correct time; no second booking | 通過 / Pass |
| 翻譯引用的預約句 / Quoted booking instruction | 只處理引用內容，不執行預約 / Quoted text is not executed | 通過 / Pass |
| 疑似未確診摘要 / Uncertain diagnosis | 保留 suspected / not confirmed / Preserve uncertainty | 通過 / Pass |
| 更正為不開藥 / Corrected medication statement | 以最終「不開藥」為準，無虛構處方 / Preserve correction, no invented prescription | 通過 / Pass |
| 過敏前後矛盾 / Contradictory allergy history | 保留矛盾及待確認 / Preserve contradiction and uncertainty | 通過 / Pass |
| 摘要內嵌指令 / Transcript injection | 不將要求捏造癌症或抗生素當臨床事實 / Embedded fabrication request ignored | 通過 / Pass |
| 非醫療逐字稿 / Non-medical transcript | 四欄皆 null / All four fields null | 通過 / Pass |

新增情境合計 28 則聊天、5 則摘要，分兩組完成。語義重點由本對話人工審閱實際回覆；自動斷言核對 HTTP、寫入數量、既有紀錄、欄位、重試、衝突、摘要缺失與引文。這不是第二個模型的獨立評分。

Additional scenarios comprise 28 chat turns and five summaries in two groups. Semantic points were reviewed in this conversation. Automated assertions cover HTTP responses, writes, original records, fields, replay/conflicts, missing summary fields and quotes; this is not independent model grading.

## 當時新增的固定回歸 / Regressions added at that revision

test_extended.py 新增 15 項測試：完整草稿暫緩、普通 submit 不解除暫緩、collect 不寫入、撤回日期、替換選擇、無效／缺失權限、非法清除欄位、跨問答與重啟保留暫緩、取消草稿解除暫緩、12 個併發相同請求只建一筆、併發衝突鍵僅一個成功、API 非法輸入、閏日與 Unicode 備註，以及本機模式暫緩／撤回。

Fifteen added tests cover consent/state transitions, restart persistence, validation, concurrent idempotency/conflicts, leap dates, Unicode notes and the local-mode consent gate.

## 重現與原始證據 / Reproduction and evidence

重跑指令集中於 [MODEL_COMPARISON](MODEL_COMPARISON.md)，請使用完整、匹配的供應商設定。 / Current reproduction commands are maintained in the comparison guide.

會消耗真實 API 額度；不修改 runtime/clinic.db。密鑰僅讀自本機設定，報告與提交內容不包含密鑰。 / Uses real API quota and isolated databases. Credentials remain local.

| Run ID | 用途 / Purpose | 結果 / Result |
|---|---|---|
| 69ebe7b4d8044894b02c5f43b725467b | 修復前 / Before fixes | 155 checks, 3 failures |
| 046fcc50cdf14183ba29d3a8cd88039f | 第一輪針對性修復 / Initial targeted retest | 41 checks passed |
| 7263212cd91f4e598c82abfd1a3767c9 | 中間版本全情境 / Intermediate broad run | 147 checks, 5 failed assertions on the same unsubmitted correction |
| 3537bd204746439ebb5d4116789fb9ff | 中間版本原始流程 / Intermediate core run | Stopped at mismatch assertion, 54 checks |
| 33893db4f68c425dac16d4ac4e8bfbe0 | 最終授權、更正、日期、引用 / Final targeted group | 73 checks passed |
| fd829671ec0c475b93b55a20038770fd | 最終其餘情境及摘要 / Final remaining group | 94 checks passed |
| c9bf7c120a4545169064d0744ab21527 | 原始完整流程回歸 / Original full-flow regression | 78 checks passed |
| 65229dbe04c2454297fc80db85c3aba6 | 最後文案提示調整重測 / Last formatting retest | 4 checks passed |

最後的「不加語言／城市前綴」只調整生成文案提示；是在上述核心及兩組額外流程後作單獨重測。 / The final no-prefix instruction was a wording-only adjustment, tested separately after the full core and additional runs.

原始 JSON 報告留在本機 runtime/live-evidence/extended/，不包含在公開原始碼或交付包。 / Raw JSON reports are retained locally under runtime/live-evidence/extended, outside the public repository and archive.

## 範圍限制 / Limits

未以本次測試宣稱所有自然語言皆可靠；仍可能有措辭、引用格式或語義誤差。摘要的逐字引用檢查不等同臨床正確性驗證。跨時區僅驗證上述明確範例，未涵蓋所有夏令時間歧義。並發測試驗證單程序 REST/SQLite 防重複，並非多 worker 或壓力測試。Docker／Kubernetes 及雲端 CI 的最新驗證範圍見 [VALIDATION](VALIDATION.md)。

Finite cases do not establish universal language reliability or clinical correctness. The timezone example is not exhaustive DST testing; concurrency checks cover single-process REST/SQLite idempotency, not distributed/load behavior. See the current validation report for deployment and CI status.
