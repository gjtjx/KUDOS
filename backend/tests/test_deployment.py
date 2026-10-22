import importlib.util
import tempfile
import unittest
import os
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

class DeploymentTests(unittest.TestCase):
    def test_provider_profile_does_not_mix_other_files_or_old_credentials(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'LLM_API_KEY_FILE':'old-secret', 'POE_API_KEY':'old-poe'}, clear=False):
            root=Path(directory)
            source=root/'chosen.env'
            source.write_text('LLM_API_KEY=new-test-key\nLLM_MODEL=new-model\nLLM_BASE_URL=https://provider.test\nLLM_API_STYLE=responses\n',encoding='utf-8')
            (root/'.env.local').write_text('LLM_MODEL=wrong-provider\n',encoding='utf-8')
            module('acceptance_config').load_provider(SimpleNamespace(env_file=source,api_style=None,tool_choice='auto',no_strict_tools=True))
            self.assertEqual(os.environ['LLM_MODEL'],'new-model')
            self.assertEqual(os.environ['LLM_API_STYLE'],'responses')
            self.assertEqual(os.environ['LLM_TOOL_CHOICE'],'auto')
            self.assertEqual(os.environ['LLM_STRICT_TOOLS'],'false')
            self.assertNotIn('LLM_API_KEY_FILE',os.environ)
            self.assertNotIn('POE_API_KEY',os.environ)

    def test_offline_compose_and_kubernetes_schema_and_references(self):
        report=module("validate_deployment").verify()
        self.assertEqual(report["kubernetes_resources"],5)
        self.assertFalse(report["runtime_tested"])

    def test_secret_preparation_copies_only_key_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/".env"; target=root/".secrets/llm_api_key"
            source.write_text("LLM_API_KEY=local-test-secret\nAI_MODE=llm\n",encoding="utf-8")
            prepare=module("prepare_secret").prepare
            prepare(source,target)
            self.assertEqual(target.read_text(),"local-test-secret")
            with self.assertRaises(FileExistsError): prepare(source,target)

    def test_secret_preparation_rejects_missing_key_without_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/".env"; target=root/"key"
            source.write_text("AI_MODE=llm\n",encoding="utf-8")
            with self.assertRaises(ValueError): module("prepare_secret").prepare(source,target)
            self.assertFalse(target.exists())
