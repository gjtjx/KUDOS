# 部署指南 / Deployment Guide

**狀態：設定已提供並做離線驗證；尚未實際建置容器或驗收叢集。**
**Status: configuration checked offline; container and cluster runtime remain unverified.**

本指南以單 worker、單副本 SQLite 為前提。一般本機啟動見 [README](README.md)，備份及回退見 [MAINTENANCE](MAINTENANCE.md)。
Deployment files do not remove the application's single-process or authentication limitations.

## 1. 離線檢查 / Offline checks

安裝開發依賴後，在根目錄執行 / From the root with development dependencies installed:

```powershell
.\.venv\Scripts\python.exe scripts/validate_deployment.py
```

驗證兩份 Compose schema、五種 Kubernetes 資源、selector／volume／Secret 參照及安全設定。Kubernetes 驗證器指定 1.37 schema；不代表已在該版本叢集運行。Compose schema 的來源與授權見 [tools/schemas/README](tools/schemas/README.md)。
Schema validation is separate from image builds, storage behavior and cluster scheduling.

## 2. Docker Compose：本機模式 / Local-mode Compose

需要 Docker Engine/Desktop 與 Compose v2。以下使用 8001 埠，避免與 8000 的本機示範服務衝突。
Requires Docker and Compose v2; commands use a separate host port.

```powershell
$env:CLINIC_PORT="8001"
docker compose up --build -d --wait --wait-timeout 120
.\.venv\Scripts\python.exe scripts/smoke_deployment.py
```

Compose 明確設定 `AI_MODE=local`；主機 .env 的 LLM 設定不會自動啟用容器模型。預設 localhost 綁定、非 root UID/GID 10001、唯讀 root filesystem、單 worker；named volume 的 runtime 與 /tmp 可寫。
The base Compose file explicitly selects local mode and persistent storage.

隔離部署可另驗證寫入及重啟保存；`--write-booking` 會新增模擬預約。 / For a disposable test deployment, explicitly opt into a booking write:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_deployment.py --write-booking
docker compose restart
docker compose up -d --wait
.\.venv\Scripts\python.exe scripts/smoke_deployment.py --verify-report runtime/deployment-smoke.json
```

一般停止使用 `docker compose down` 會保留 volume；需要保留資料時不要加 `--volumes`。
Preserve the named volume during normal shutdown.

## 3. Docker Compose：真實模型 / Live-provider Compose

[compose.llm.yaml](compose.llm.yaml) 預設為 Poe Sonnet。先依 [README](README.md#model-configuration) 在本機準備完整 `.env.sonnet`，再建立 Secret 檔：
The overlay defaults to Poe Sonnet; prepare a matching local profile first.

```powershell
.\.venv\Scripts\python.exe scripts/prepare_secret.py --env-file .env.sonnet
docker compose -f compose.yaml -f compose.llm.yaml up --build -d --wait
```

DeepSeek 改用 `--env-file .env` 準備密鑰，並把 overlay 的非機密參數改成 README 的 DeepSeek 組合。**Secret helper 只準備密鑰，不會同步模型、URL 或 API style。**
For DeepSeek, update both the secret source and non-secret overlay settings. The helper does not switch provider configuration.

Secret 位於 `.secrets/llm_api_key`，不進 Git／image。Helper 不覆寫既有檔；輪替時停止服務、安全保留舊檔、建立新檔，再用相同兩個 `-f` 參數重建容器。不要把密鑰值放進 YAML 或命令。
Keep file-mounted credentials separate from configuration and use the same overlay selection for lifecycle operations.

啟動後檢查 `/api/health` 的 mode/model/api_style，再送一則提問驗證真實供應商。健康探針本身不呼叫模型。
Health checks show configuration, not provider reachability.

## 4. Kubernetes

需要可用叢集、kubectl、預設 StorageClass 及可取得的映像。以下 `clinicpilot:local` 必須先載入 kind，或改成叢集可拉取的 registry image。
Ensure the cluster can access the chosen image.

```powershell
docker build -t clinicpilot:local .
# For kind: kind load docker-image clinicpilot:local
kubectl apply -f k8s/clinicpilot.yaml
kubectl -n clinicpilot rollout status deployment/clinicpilot --timeout=180s
kubectl -n clinicpilot port-forward service/clinicpilot 8001:8000
```

資源包含 Namespace、ConfigMap、1Gi RWO PVC、單副本 Recreate Deployment、ClusterIP Service，沒有公開 Ingress。
The deployment intentionally remains single-replica with private access.

| 設定 / Setting | 用途 / Purpose |
|---|---|
| startup/readiness: `/api/ready` | SQLite 可讀性 / Database readiness |
| liveness: `/api/live` | 程序存活；不呼叫付費模型 / Process liveness |
| UID/GID、fsGroup 10001 | 非 root 儲存權限 / Non-root storage access |
| 唯讀 root、emptyDir /tmp | 限定可寫位置 / Restricted writable paths |
| Secret file mount | 密鑰不寫入 ConfigMap / Separate credentials |

啟用 Poe Sonnet 前，準備同一供應商的 Secret。若由 Compose 切換服務商，先處理既有 Secret 檔，不可混用。
Prepare matching credentials before enabling the LLM patch.

```powershell
.\.venv\Scripts\python.exe scripts/prepare_secret.py --env-file .env.sonnet
kubectl -n clinicpilot create secret generic clinicpilot-llm --from-file=LLM_API_KEY=.secrets/llm_api_key
kubectl -n clinicpilot patch configmap clinicpilot-config --type merge --patch-file k8s/llm-config.patch.yaml
kubectl -n clinicpilot rollout restart deployment/clinicpilot
kubectl -n clinicpilot rollout status deployment/clinicpilot
```

此 create 命令用於首次建立 Secret；已存在時按環境的 Secret 更新程序輪替，不重複 create。DeepSeek 需同步修改 patch 中非機密參數及密鑰來源。檔案掛載位置由 `LLM_API_KEY_FILE` 指向，更新後重新啟動。
The sample creates the Secret once; subsequent rotation requires updating it and restarting.

## 5. 維護與驗收 / Operations and acceptance

- 不直接增加 worker 或副本；先解決程序鎖、共享 Agent 狀態與資料庫架構。 / Horizontal scaling requires application changes.
- PVC Pending 查 StorageClass；ImagePullBackOff 查 registry；權限錯誤查 driver 對 fsGroup 的支援。 / Diagnose storage, image and ownership failures separately.
- 先用 SQLite backup API 產生一致快照，再透過 compose cp／kubectl cp 取出；還原前停服務並確認 10001 權限。 / Follow the maintenance backup procedure.
- 回退映像保留 volume/PVC；刪除 namespace/PVC 不是普通停止，可能刪除資料。 / Preserve persistent storage.
- 記錄實際 image、健康狀態、寫入、重啟及還原結果，才能宣稱 runtime 驗收。 / Capture runtime evidence before claiming deployment success.

CI 已有容器檢查步驟，但沒有本版成功的雲端執行證據；先前失敗原因與驗證界線見 [VALIDATION](VALIDATION.md)。
