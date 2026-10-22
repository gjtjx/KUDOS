"""Local, metadata-only observability. Never persist prompts, transcripts or credentials."""
import contextvars
import functools
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS request_traces(
 trace_id TEXT PRIMARY KEY, operation TEXT NOT NULL, mode TEXT NOT NULL,
 started_at TEXT NOT NULL, status TEXT NOT NULL, http_status INTEGER,
 duration_ms INTEGER, outcome TEXT, cache_hit INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS llm_spans(
 span_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL REFERENCES request_traces ON DELETE CASCADE,
 operation TEXT NOT NULL, model TEXT NOT NULL, api_style TEXT NOT NULL,
 started_at TEXT NOT NULL, duration_ms INTEGER NOT NULL, status TEXT NOT NULL,
 input_tokens INTEGER, output_tokens INTEGER, error_code TEXT);
CREATE INDEX IF NOT EXISTS trace_started ON request_traces(started_at DESC);
CREATE INDEX IF NOT EXISTS spans_trace ON llm_spans(trace_id);
"""
current_trace = contextvars.ContextVar("clinic_trace", default=None)

def timestamp():
    return datetime.now(timezone.utc).isoformat()

def token_count(value):
    return value if type(value) is int and 0 <= value <= 10**9 else None

def identifier(value, fallback):
    # Only internally selected identifiers; never accept arbitrary exception text.
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,120}", value) else fallback

def error_code(error):
    codes = {"configuration_missing", "invalid_request", "authentication_failed", "insufficient_credits",
             "access_denied", "model_or_endpoint_not_found", "rate_limited", "provider_unavailable",
             "incomplete_response", "invalid_tool_response", "empty_response"}
    code = getattr(error, "code", None)
    if code in codes:
        return code
    name = type(error).__name__
    return {"ReadTimeout": "timeout", "ConnectTimeout": "timeout", "ConnectError": "connection_error",
            "CancelledError": "cancelled"}.get(name, "invalid_or_failed_response")

class TraceStore:
    def __init__(self, db):
        self.db = db
        self.enabled = os.getenv("TRACE_ENABLED", "true").lower() == "true"
        self.maximum = int(os.getenv("TRACE_MAX_RECORDS", "1000"))
        if not 10 <= self.maximum <= 10000:
            raise ValueError("TRACE_MAX_RECORDS must be between 10 and 10000")
        def recover():
            with self.db.connect() as c:
                c.execute("UPDATE request_traces SET status='interrupted',http_status=503 WHERE status='running'")
        self.attempt(recover)

    def attempt(self, operation):
        try:
            return operation()
        except Exception:
            # Observability failure must not undo or misreport a successful booking.
            logging.warning("Trace storage unavailable; business request continues")
            return None

    def start(self, operation, mode):
        ident = uuid.uuid4().hex
        def insert():
            with self.db.connect() as c:
                c.execute("INSERT INTO request_traces(trace_id,operation,mode,started_at,status) VALUES(?,?,?,?,?)",
                          (ident, operation, mode, timestamp(), "running"))
        self.attempt(insert)
        return {"id": ident, "store": self, "started": time.monotonic(), "outcome": None, "cache_hit": False}

    def finish(self, context, status):
        def update():
            with self.db.connect() as c:
                c.execute("UPDATE request_traces SET status=?,http_status=?,duration_ms=?,outcome=?,cache_hit=? WHERE trace_id=?",
                          ("ok" if status < 400 else "error", status,
                           round((time.monotonic()-context["started"])*1000),
                           context["outcome"], int(context["cache_hit"]), context["id"]))
                c.execute("DELETE FROM request_traces WHERE status!='running' AND trace_id IN "
                          "(SELECT trace_id FROM request_traces WHERE status!='running' ORDER BY started_at DESC,trace_id DESC LIMIT -1 OFFSET ?)",
                          (self.maximum,))
        self.attempt(update)

    def generation(self, context, operation, model, style, started_at, duration, metadata=None, error=None):
        metadata = metadata or {}
        ident = uuid.uuid4().hex
        def insert():
            with self.db.connect() as c:
                c.execute("INSERT INTO llm_spans VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                          (ident, context["id"], operation, identifier(model, "unknown"),
                           identifier(style, "unknown"), started_at, duration,
                           "error" if error else "ok", token_count(metadata.get("input_tokens")),
                           token_count(metadata.get("output_tokens")), error_code(error) if error else None))
        self.attempt(insert)

    def overview(self, limit):
        traces = self.db.rows(
            "SELECT t.*,COUNT(s.span_id) AS llm_calls, SUM(s.input_tokens) AS input_tokens,"
            "SUM(s.output_tokens) AS output_tokens FROM request_traces t LEFT JOIN llm_spans s USING(trace_id) "
            "GROUP BY t.trace_id ORDER BY t.started_at DESC,t.trace_id DESC LIMIT ?", (limit,))
        for trace in traces:
            trace["cache_hit"] = bool(trace["cache_hit"])
            trace["spans"] = self.db.rows("SELECT * FROM llm_spans WHERE trace_id=? ORDER BY started_at,span_id", (trace["trace_id"],))
        summary = self.db.rows("SELECT COUNT(*) AS requests, SUM(CASE WHEN status IN ('error','interrupted') THEN 1 ELSE 0 END) AS errors, "
                               "SUM(cache_hit) AS cache_hits, AVG(duration_ms) AS mean_latency_ms FROM request_traces")[0]
        usage = self.db.rows("SELECT COUNT(*) AS llm_calls,SUM(input_tokens) AS input_tokens,SUM(output_tokens) AS output_tokens,"
                            "SUM(CASE WHEN input_tokens IS NULL OR output_tokens IS NULL THEN 1 ELSE 0 END) AS missing_usage_calls FROM llm_spans")[0]
        return {"enabled": self.enabled, "retention_limit": self.maximum, "summary": {**summary, **usage}, "traces": traces}

def mark_outcome(outcome, cached=False):
    context = current_trace.get()
    if context:
        context.update(outcome=outcome, cache_hit=cached)

def observe_generation(function):
    @functools.wraps(function)
    async def wrapped(messages, tools=None):
        context = current_trace.get()
        if not context:
            return await function(messages, tools)
        operation = tools[0].get("function", {}).get("name") if tools else "answer"
        operation = operation if operation in {"route_intent", "summarize_transcript", "answer"} else "tool_call"
        started_at, started = timestamp(), time.monotonic()
        model, style = os.getenv("LLM_MODEL", ""), os.getenv("LLM_API_STYLE", "chat_completions")
        try:
            result = await function(messages, tools)
        except BaseException as error:
            context["store"].generation(context, operation, model, style, started_at,
                                        round((time.monotonic()-started)*1000), error=error)
            raise
        context["store"].generation(context, operation, model, style, started_at,
                                    round((time.monotonic()-started)*1000), metadata=result[1])
        return result
    return wrapped
