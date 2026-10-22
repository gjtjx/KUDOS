"""Offline schema and cross-resource validation; not a container/cluster runtime test."""
import json
from pathlib import Path
import yaml
from jsonschema import Draft202012Validator
from kubernetes_validate import validate

ROOT = Path(__file__).resolve().parents[1]

def verify(root=ROOT):
    schema = json.loads((root / "tools/schemas/compose-spec.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    base = yaml.safe_load((root / "compose.yaml").read_text(encoding="utf-8"))
    overlay = yaml.safe_load((root / "compose.llm.yaml").read_text(encoding="utf-8"))
    validator.validate(base)
    validator.validate(overlay)
    service = base["services"]["clinicpilot"]
    assert service["read_only"] is True
    assert "clinic-data:/app/runtime" in service["volumes"]
    assert service["ports"][0].startswith("127.0.0.1:")
    live = overlay["services"]["clinicpilot"]
    assert live["environment"]["LLM_API_KEY_FILE"] == "/run/secrets/llm_api_key"
    assert "LLM_API_KEY" not in live["environment"]
    assert live["secrets"] == ["llm_api_key"]
    assert overlay["secrets"]["llm_api_key"]["file"] == "./.secrets/llm_api_key"

    docs = list(yaml.safe_load_all((root / "k8s/clinicpilot.yaml").read_text(encoding="utf-8")))
    for doc in docs:
        validate(doc, desired_version="1.37.0", strict=True)
    resources = {doc["kind"]: doc for doc in docs}
    assert set(resources) == {"Namespace", "ConfigMap", "PersistentVolumeClaim", "Deployment", "Service"}
    namespace = resources["Namespace"]["metadata"]["name"]
    assert all(d["metadata"].get("namespace") == namespace for d in docs if d["kind"] != "Namespace")
    deployment = resources["Deployment"]["spec"]
    assert deployment["replicas"] == 1 and deployment["strategy"]["type"] == "Recreate"
    pod = deployment["template"]["spec"]
    container = pod["containers"][0]
    labels = deployment["template"]["metadata"]["labels"]
    assert deployment["selector"]["matchLabels"] == labels == resources["Service"]["spec"]["selector"]
    assert resources["Service"]["spec"]["type"] == "ClusterIP"
    assert container["envFrom"][0]["configMapRef"]["name"] == resources["ConfigMap"]["metadata"]["name"]
    volumes = {v["name"]: v for v in pod["volumes"]}
    assert volumes["data"]["persistentVolumeClaim"]["claimName"] == resources["PersistentVolumeClaim"]["metadata"]["name"]
    assert {v["name"] for v in container["volumeMounts"]} <= set(volumes)
    assert pod["securityContext"]["runAsUser"] == 10001
    assert container["securityContext"]["readOnlyRootFilesystem"]
    assert not container["securityContext"]["allowPrivilegeEscalation"]
    assert not pod["automountServiceAccountToken"]
    assert container["readinessProbe"]["httpGet"]["path"] == "/api/ready"
    assert container["livenessProbe"]["httpGet"]["path"] == "/api/live"
    assert container["startupProbe"]["httpGet"]["path"] == "/api/ready"
    patch = yaml.safe_load((root / "k8s/llm-config.patch.yaml").read_text(encoding="utf-8"))
    assert patch["data"]["AI_MODE"] == "llm"
    assert patch["data"]["LLM_API_KEY_FILE"] == "/run/secrets/llm_api_key"
    assert "LLM_API_KEY" not in patch["data"]
    assert volumes["llm-key"]["secret"]["items"] == [{"key": "LLM_API_KEY", "path": "llm_api_key"}]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "frontend/.npmrc" in dockerfile and "USER 10001:10001" in dockerfile
    assert "HEALTHCHECK" in dockerfile and "/api/ready" in dockerfile
    assert "--workers" in dockerfile and '"1"' in dockerfile
    for ignore in (".gitignore", ".dockerignore"):
        lines = (root / ignore).read_text(encoding="utf-8").splitlines()
        assert ".env" in lines and ".env.local" in lines and "*.env" in lines and ".env.*" in lines
        assert any(line.rstrip("/") == ".secrets" for line in lines)
    return {"compose_files": 2, "kubernetes_resources": len(docs), "schema_version": "1.37.0",
            "runtime_tested": False, "result": "passed"}

if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
