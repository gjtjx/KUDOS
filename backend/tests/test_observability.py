import asyncio
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
import httpx
from fastapi.testclient import TestClient
from app.main import create_app
from app.llm import configuration, ProviderError
from app.observability import TraceStore, current_trace, observe_generation, token_count, identifier, error_code

ROOT = Path(__file__).resolve().parents[2]

def response(message, usage=None, status=200):
    return httpx.Response(status, json={"id": "provider-response", "model": "test-model",
        "choices": [{"message": message}], "usage": usage or {}}, request=httpx.Request("POST", "https://example.test/v1/chat/completions"))

def routed():
    return {"tool_calls": [{"function": {"name": "route_intent", "arguments": json.dumps({"intent": "knowledge", "search_query": "C001 hours"})}}]}

class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        folder = ROOT / "runtime/tests"
        folder.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=folder)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "test.db"
        self.env = patch.dict(os.environ, {"AI_MODE": "llm", "TRACE_ENABLED": "true", "TRACE_MAX_RECORDS": "10",
            "LLM_API_KEY": "private-test-key", "LLM_API_KEY_FILE": "", "LLM_BASE_URL": "https://example.test/v1",
            "LLM_MODEL": "test-model", "LLM_API_STYLE": "chat_completions", "LLM_TOOL_CHOICE": "auto"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.app = create_app(self.path, ROOT / "mock-data")
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def chat(self, message="private-prompt-canary", request="one"):
        return self.client.post("/api/chat", json={"session_id": "private-session", "request_id": request, "message": message})

    def overview(self):
        return self.client.get("/api/observability").json()

    def replies(self):
        return [response(routed(), {"prompt_tokens": 20, "completion_tokens": 5}),
                response({"content": json.dumps({'paragraphs':[{'zh':'診所資訊','en':'private-answer-canary'}]})}, {"prompt_tokens": 30, "completion_tokens": 7})]

    def test_real_transport_spans_and_metadata_only_storage(self):
        with patch("app.llm.httpx.AsyncClient.post", AsyncMock(side_effect=self.replies())):
            result = self.chat()
        self.assertEqual(result.status_code, 200)
        view = self.overview()
        trace = view["traces"][0]
        self.assertEqual(trace["trace_id"], result.headers["X-Trace-ID"])
        self.assertEqual(trace["outcome"], "answered")
        self.assertEqual([s["operation"] for s in trace["spans"]], ["route_intent", "answer"])
        self.assertEqual((trace["input_tokens"], trace["output_tokens"]), (50, 12))
        self.assertEqual(view["summary"]["llm_calls"], 2)
        for canary in ("private-test-key", "private-prompt-canary", "private-answer-canary", "private-session"):
            self.assertNotIn(canary, json.dumps(view))

    def test_cached_request_has_new_parent_without_duplicate_spans(self):
        with patch("app.llm.httpx.AsyncClient.post", AsyncMock(side_effect=self.replies())) as provider:
            first = self.chat()
            replay = self.chat()
        self.assertEqual(provider.await_count, 2)
        self.assertEqual(first.json(), replay.json())
        self.assertNotEqual(first.headers["X-Trace-ID"], replay.headers["X-Trace-ID"])
        view = self.overview()
        self.assertEqual(view["summary"]["cache_hits"], 1)
        self.assertEqual(view["summary"]["llm_calls"], 2)
        cached = next(t for t in view["traces"] if t["cache_hit"])
        self.assertEqual(cached["spans"], [])

    def test_provider_http_error_is_traced_without_error_body(self):
        with patch("app.llm.httpx.AsyncClient.post", AsyncMock(return_value=response({"content": "private-error-key"}, status=401))):
            result = self.chat()
        self.assertEqual(result.status_code, 502)
        view = self.overview()
        self.assertEqual(view["summary"]["errors"], 1)
        span = view["traces"][0]["spans"][0]
        self.assertEqual(span["error_code"], "authentication_failed")
        self.assertNotIn("private-error-key", json.dumps(view))

    def test_timeout_and_missing_usage_are_not_fake_zero(self):
        with patch("app.llm.httpx.AsyncClient.post", AsyncMock(side_effect=httpx.ReadTimeout("private-test-key"))):
            self.assertEqual(self.chat().status_code, 502)
        span = self.overview()["traces"][0]["spans"][0]
        self.assertEqual(span["error_code"], "timeout")
        self.assertIsNone(span["input_tokens"])
        self.assertEqual(self.overview()["summary"]["missing_usage_calls"], 1)

    def test_validation_failure_has_parent_but_no_model_calls(self):
        self.assertEqual(self.chat(" ").status_code, 422)
        trace = self.overview()["traces"][0]
        self.assertEqual(trace["http_status"], 422)
        self.assertEqual(trace["spans"], [])

    def test_summary_tracing_never_stores_transcript(self):
        fields = ("chief_complaint", "diagnosis", "medication", "doctor_instructions")
        args = {**dict.fromkeys(fields), "evidence": {f: [] for f in fields}}
        msg = {"tool_calls": [{"function": {"name": "summarize_transcript", "arguments": json.dumps(args)}}]}
        with patch("app.llm.httpx.AsyncClient.post", AsyncMock(return_value=response(msg))):
            result = self.client.post("/api/transcripts/summarize", json={"transcript": "private-transcript-canary"})
        self.assertEqual(result.status_code, 200)
        view = self.overview()
        self.assertEqual(view["traces"][0]["operation"], "transcript_summary")
        self.assertEqual(view["traces"][0]["outcome"], "summarized")
        self.assertNotIn("private-transcript-canary", json.dumps(view))

    def test_disabled_tracing_has_no_new_records(self):
        self.app.state.tracing.enabled = False
        with patch("app.llm.httpx.AsyncClient.post", AsyncMock(side_effect=self.replies())):
            result = self.chat()
        self.assertNotIn("X-Trace-ID", result.headers)
        self.assertEqual(self.overview()["traces"], [])
        self.assertFalse(self.overview()["enabled"])

    def test_retention_cascades_and_recovers_interrupted_requests(self):
        store = self.app.state.tracing
        for _ in range(12):
            context = store.start("chat", "llm")
            store.generation(context, "answer", "test-model", "chat_completions", "2035-01-01", 1, {"input_tokens": 0, "output_tokens": 0})
            store.finish(context, 200)
        self.assertEqual(len(self.app.state.db.rows("SELECT * FROM request_traces")), 10)
        self.assertEqual(len(self.app.state.db.rows("SELECT * FROM llm_spans")), 10)
        context = store.start("chat", "llm")
        recovered = TraceStore(self.app.state.db)
        self.assertEqual(recovered.overview(20)["traces"][0]["status"], "interrupted")
        self.assertEqual(recovered.overview(20)["summary"]["errors"], 1)

    def test_trace_storage_failure_does_not_raise(self):
        store = self.app.state.tracing
        with patch.object(store.db, "connect", side_effect=sqlite3.OperationalError("private path")):
            context = store.start("chat", "llm")
            store.generation(context, "answer", "test-model", "chat_completions", "2035-01-01", 1)
            store.finish(context, 200)

    def test_trace_limit_validation_and_empty_state(self):
        self.assertEqual(self.overview()["summary"]["requests"], 0)
        for limit in ("0", "101", "wrong"):
            self.assertEqual(self.client.get("/api/observability?limit="+limit).status_code, 422)
        with patch.dict(os.environ, {"TRACE_MAX_RECORDS": "1"}), self.assertRaises(ValueError):
            TraceStore(self.app.state.db)

    def test_readiness_failure_does_not_fail_liveness(self):
        self.assertEqual(self.client.get("/api/ready").status_code, 200)
        with patch.object(self.app.state.db, "rows", side_effect=sqlite3.OperationalError("private path")):
            self.assertEqual(self.client.get("/api/ready").status_code, 503)
            self.assertEqual(self.client.get("/api/live").status_code, 200)

    def test_mounted_secret_takes_precedence_without_exposing_path(self):
        secret = Path(self.temp.name) / "api-key"
        secret.write_text("mounted-test-key\n", encoding="utf-8")
        with patch.dict(os.environ, {"LLM_API_KEY_FILE": str(secret)}):
            self.assertEqual(configuration()["key"], "mounted-test-key")
        with patch.dict(os.environ, {"LLM_API_KEY_FILE": str(secret)+"missing"}):
            with self.assertRaisesRegex(ValueError, "^Cannot read LLM_API_KEY_FILE$"):
                configuration()

    def test_unexpected_request_failure_cleans_up_context(self):
        with patch.object(self.app.state.db, "state", side_effect=RuntimeError("private detail")):
            with self.assertRaises(RuntimeError):
                self.chat()
        self.assertEqual(self.overview()["traces"][0]["http_status"], 500)
        self.assertIsNone(current_trace.get())

class ContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_calls_keep_request_context_separate(self):
        captured = []
        class Store:
            def generation(self, context, operation, model, style, start, duration, metadata=None, error=None):
                captured.append((context["id"], operation, metadata, error))
        @observe_generation
        async def provider(messages, tools=None):
            await asyncio.sleep(0)
            return {"content": "ok"}, {"input_tokens": messages[0], "output_tokens": 1}
        async def task(ident):
            token = current_trace.set({"id": ident, "store": Store()})
            try:
                await provider([ident])
            finally:
                current_trace.reset(token)
        await asyncio.gather(task(1), task(2))
        self.assertEqual({(c[0],c[2]["input_tokens"]) for c in captured}, {(1,1),(2,2)})
        self.assertIsNone(current_trace.get())

    async def test_unknown_tool_names_and_cancelled_calls(self):
        captured=[]
        class Store:
            def generation(self,*args,**kwargs): captured.append((args,kwargs))
        @observe_generation
        async def provider(messages, tools=None):
            raise asyncio.CancelledError()
        token=current_trace.set({"id":"x","store":Store()})
        try:
            with self.assertRaises(asyncio.CancelledError):
                await provider([], [{"function":{"name":"private-user-input"}}])
        finally: current_trace.reset(token)
        self.assertEqual(captured[0][0][1], "tool_call")
        self.assertEqual(error_code(captured[0][1]["error"]), "cancelled")

    def test_sanitizers_never_infer_usage_or_log_exception_text(self):
        for value in (None, True, -1, "100", 10**10):
            self.assertIsNone(token_count(value))
        self.assertEqual(token_count(0),0)
        self.assertEqual(identifier("bad secret with spaces","unknown"),"unknown")
        self.assertEqual(error_code(RuntimeError("private-key")),"invalid_or_failed_response")
        self.assertEqual(error_code(httpx.ConnectError("private-key")),"connection_error")
