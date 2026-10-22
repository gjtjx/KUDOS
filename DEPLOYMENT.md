# Docker 與 Kubernetes / Deployment

設定已完成並通過離線 schema／參照檢查。本機沒有 Docker engine、kubectl 或 cluster，尚未實際建置映像或啟動 Pod。CI 已加入容器重啟持久化驗證，但帳號帳單鎖定尚待解除。/ Manifests validated; container/cluster runtime and cloud CI remain unverified.

## Docker Compose

需要 Docker Engine/Desktop 與 Compose v2。從根目錄執行，預設 local 無需密鑰。/ Run from the project root:

```powershell
$env:CLINIC_PORT="8001"
docker compose up --build -d --wait --wait-timeout 120
python scripts/smoke_deployment.py --write-booking
docker compose restart
docker compose up -d --wait
python scripts/smoke_deployment.py --verify-report runtime/deployment-smoke.json
```

--write-booking 會新增模擬預約，只用於隔離測試部署；省略可做唯讀檢查。/ Omit the write flag for read-only checks.

真實 Poe/Sonnet：/ Live Poe/Sonnet:
```powershell
python scripts/prepare_secret.py --env-file 1.env
docker compose -f compose.yaml -f compose.llm.yaml up --build -d --wait
```

DeepSeek：將 compose.llm.yaml 的非機密參數改為 URL https://api.deepseek.com、model deepseek-flash、style responses、choice auto、strict false，並用 --env-file .env 準備相應密鑰。不能混用兩家密鑰。/ Change provider parameters and use the matching key.

Secret 檔 .secrets/llm_api_key 不進 Git/image；helper 不覆寫既有檔。輪替時停止服務，把舊檔移至受保護位置，建立新檔並重建容器。限制本機目錄權限。/ Stop, preserve the old secret securely, prepare its replacement, recreate and verify.

容器以 UID/GID 10001 執行、唯讀根目錄、單 worker；runtime named volume 與 /tmp 可寫。docker compose down 保留資料；不要對需要保留的資料使用 down --volumes。/ Preserve the named volume during normal shutdown.

## Kubernetes

需要 cluster、kubectl、預設 StorageClass 和可取得的映像。kind 可載入本機映像，其他 cluster 請推送自己的 registry 並更新 Deployment image。/ Load into kind or use an accessible registry.

```powershell
docker build -t clinicpilot:local .
# For kind: kind load docker-image clinicpilot:local
kubectl apply -f k8s/clinicpilot.yaml
kubectl -n clinicpilot rollout status deployment/clinicpilot --timeout=180s
kubectl -n clinicpilot port-forward service/clinicpilot 8001:8000
```

包含 Namespace、ConfigMap、1Gi RWO PVC、單副本 Recreate Deployment、ClusterIP Service。無公開 Ingress。readiness/startup /api/ready 檢查 SQLite，liveness /api/live 檢查程序；均不呼叫付費模型。/ Five resources with private access and independent process/database probes.

啟用 Poe/Sonnet：/ Enable Poe/Sonnet:
```powershell
python scripts/prepare_secret.py --env-file 1.env
kubectl -n clinicpilot create secret generic clinicpilot-llm --from-file=LLM_API_KEY=.secrets/llm_api_key
kubectl -n clinicpilot patch configmap clinicpilot-config --type merge --patch-file k8s/llm-config.patch.yaml
kubectl -n clinicpilot rollout restart deployment/clinicpilot
kubectl -n clinicpilot rollout status deployment/clinicpilot
```

DeepSeek 修改 patch 的非機密參數並使用其密鑰。Secret 掛成檔，LLM_API_KEY_FILE 指向 /run/secrets/llm_api_key；輪替後重啟。不要將值寫入 YAML、命令或映像。/ File-mounted credentials, restart after rotation.

## 維護 / Operations

- SQLite 必須維持單副本、單 worker；不要直接擴容。/ Do not scale horizontally.
- PVC Pending 檢查 StorageClass；ImagePullBackOff 檢查 registry；權限錯誤檢查 storage driver 的 fsGroup 10001。/ Inspect storage, image access and ownership.
- 依 MAINTENANCE.md 用 SQLite backup API 在 runtime 產生一致快照，再透過 docker compose cp / kubectl cp 取出。還原前停止服務、保留目前資料，還原後確認 10001 權限。/ Back up consistently and stop before restore.
- 回退上一版映像並保留 volume/PVC；新增追蹤表不改寫原業務表。刪除 namespace/PVC 可能刪除資料，不能當成普通停止。/ Preserve storage on rollback.
- python scripts/validate_deployment.py 驗證 Compose 官方 schema、Kubernetes 1.37 schema、selector/volume/Secret 關聯；不等同實際部署。/ Offline validation is not runtime acceptance.

參考：[Docker secrets](https://docs.docker.com/compose/how-tos/use-secrets/)、[Kubernetes probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)。
