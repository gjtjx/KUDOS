import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from .db import Database
from .models import ChatInput, BookingInput
from .knowledge import MATCHES
from .agent import Agent
from .llm import ProviderError, configuration
from .transcripts import TranscriptInput, summarize
from .localization import TRANSLATIONS, localized_booking
from .observability import TraceStore, current_trace, mark_outcome

ROOT = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass
TIMEZONES = {"C001": "America/New_York", "C002": "America/Los_Angeles"}
BOOKING_SQL = """SELECT b.*, d.full_name doctor_name,d.clinic_id,t.treatment_name,t.pre_treatment_instructions,c.clinic_name
FROM patient_bookings b JOIN doctors d USING(doctor_id) JOIN treatments t USING(treatment_id)
JOIN clinics c ON c.clinic_id=d.clinic_id """

def create_app(db_path=None, data_dir=None):
    app = FastAPI(title="ClinicPilot AI", version="1.0.0")
    db = Database(db_path or os.getenv("DATABASE_PATH", str(ROOT / "runtime" / "clinic.db")), data_dir or ROOT / "mock-data")
    app.state.db = db
    app.state.lock = asyncio.Lock()
    app.state.tracing = TraceStore(db)
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.middleware("http")
    async def trace_requests(request, call_next):
        operations = {"/api/chat": "chat", "/api/transcripts/summarize": "transcript_summary"}
        if request.method != "POST" or request.url.path not in operations or not app.state.tracing.enabled:
            return await call_next(request)
        context = app.state.tracing.start(operations[request.url.path], app.state.agent.mode)
        token = current_trace.set(context)
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Trace-ID"] = context["id"]
            return response
        finally:
            app.state.tracing.finish(context, status)
            current_trace.reset(token)

    @app.exception_handler(sqlite3.Error)
    async def database_error(request, error):
        logging.error("Database operation failed: %s", type(error).__name__)
        return JSONResponse(status_code=503, content={"detail": "資料庫暫時無法使用，未發出成功確認，請重試相同請求。 / Database unavailable; no success has been reported. Retry the same request."})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        fields = ", ".join(".".join(str(p) for p in e["loc"][1:]) for e in error.errors())
        return JSONResponse(status_code=422, content={"detail": "欄位格式不正確，請檢查 / Invalid fields; please check: " + fields})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": app.state.agent.mode, "patient_id": "P001",
                "model": os.getenv("LLM_MODEL") if app.state.agent.mode == "llm" else None,
                "api_style": os.getenv("LLM_API_STYLE", "chat_completions") if app.state.agent.mode == "llm" else None}

    @app.get("/api/live")
    def live():
        return {"status": "alive"}

    @app.get("/api/ready")
    def ready():
        db.rows("SELECT 1")
        return {"status": "ready"}

    @app.get("/api/observability")
    def observability(limit: int = Query(default=20, ge=1, le=100)):
        return app.state.tracing.overview(limit)

    @app.get("/api/profile")
    def profile():
        return {**db.profile(), "known_allergies_zh": "青黴素、花生"}

    @app.post("/api/transcripts/summarize")
    async def summarize_transcript(body: TranscriptInput):
        if not body.transcript.strip():
            raise HTTPException(422, "逐字稿不得為空 / Transcript must not be blank")
        if app.state.agent.mode != 'llm':
            raise HTTPException(503, "請先啟用真實模型 / Enable LLM mode to summarize transcripts")
        try:
            result = await summarize(body.transcript)
            mark_outcome("summarized")
            return result
        except ProviderError as error:
            raise HTTPException(502, "摘要服務失敗 / Summary provider failed: " + error.code) from error
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
            logging.warning("Transcript summary failed: %s", type(error).__name__)
            raise HTTPException(502, "逐字稿摘要未完成，請重試 / Transcript summary failed; please retry") from error

    @app.get("/api/catalog")
    def catalog():
        return {t: [{**row, "zh": TRANSLATIONS.get(row[{"clinics": "clinic_id", "doctors": "doctor_id", "treatments": "treatment_id"}[t]], {})}
                    for row in db.rows("SELECT * FROM " + t)] for t in ("clinics", "doctors", "treatments")}

    def booking_row(booking_id):
        result = db.rows(BOOKING_SQL + " WHERE b.booking_id=?", (booking_id,))[0]
        return localized_booking({**result, "timezone": TIMEZONES[result["clinic_id"]]})

    @app.get("/api/bookings")
    def bookings(patient_id: str = "P001"):
        if patient_id != "P001":
            raise HTTPException(403, "本示範僅供患者 P001 使用。 / This demo is scoped to patient P001")
        return [localized_booking({**b, "timezone": TIMEZONES[b["clinic_id"]]}) for b in db.rows(BOOKING_SQL + " WHERE b.patient_id=? ORDER BY b.booking_date,b.booking_time,b.booking_id", (patient_id,))]

    @app.post("/api/bookings")
    def book(body: BookingInput):
        data = body.model_dump(mode="json")
        payload = json.dumps({k:v for k,v in data.items() if k != "request_id"}, sort_keys=True)
        with db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            previous = c.execute("SELECT * FROM booking_keys WHERE id=?", (body.request_id,)).fetchone()
            if previous:
                if previous["payload"] != payload:
                    raise HTTPException(409, "此請求編號已用於不同預約內容。 / Request ID already used for different booking details")
                ident = previous["booking_id"]
            else:
                doctors = db.rows("SELECT * FROM doctors WHERE doctor_id=?", (body.doctor_id,))
                if not doctors or body.treatment_id not in MATCHES:
                    raise HTTPException(422, "醫生或服務編號不存在。 / Unknown doctor or treatment ID")
                if body.doctor_id not in MATCHES[body.treatment_id]:
                    raise HTTPException(422, "醫生與服務不符，請選擇對應專科的醫生。 / Doctor and treatment do not match. Select a doctor with the corresponding specialty.")
                if body.treatment_id == "T002":
                    raise HTTPException(422, "P001 為成人，本示範不提供兒童疫苗預約。 / P001 is an adult. Pediatric vaccination is not available in this single-patient demo.")
                zone = ZoneInfo(TIMEZONES[doctors[0]["clinic_id"]])
                when = datetime.combine(body.booking_date, body.booking_time).replace(tzinfo=zone)
                if when <= datetime.now(zone):
                    raise HTTPException(422, "請選擇診所當地時區的未來日期與時間。 / Choose a future date and time in the clinic's local timezone.")
                ident = "B" + uuid.uuid4().hex[:12].upper()
                c.execute("INSERT INTO patient_bookings VALUES(?,?,?,?,?,?,?,?)",
                          (ident,"P001",body.doctor_id,body.treatment_id,str(body.booking_date),body.booking_time.isoformat(),"Confirmed",body.notes))
                c.execute("INSERT INTO booking_keys VALUES(?,?,?)", (body.request_id,payload,ident))
        return booking_row(ident)

    @app.post("/api/chat")
    async def chat(body: ChatInput):
        started = time.monotonic()
        key = body.session_id + ":" + body.request_id
        payload = body.message
        async with app.state.lock:
            prior = db.rows("SELECT * FROM requests WHERE id=?", (key,))
            if prior:
                if prior[0]["payload"] != payload:
                    raise HTTPException(409, "此請求編號已用於另一則訊息。 / Request ID already used for another message")
                mark_outcome("cached", cached=True)
                return json.loads(prior[0]["response"])
            state = db.state(body.session_id)
            try:
                response = await app.state.agent.run(body.message, state, key)
            except ProviderError as error:
                logging.warning("Model provider failed: %s", error.code)
                raise HTTPException(502, "模型服務未能完成請求 / Model provider failed: " + error.code + ". 請檢查設定後重試 / Check configuration and retry.") from error
            except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as error:
                logging.warning("Agent failed: %s", type(error).__name__)
                raise HTTPException(502, "AI 服務未能完成請求，未發出預約確認，請重試。 / AI service could not complete the request. Please retry; no booking confirmation was issued.") from error
            response["session_id"] = body.session_id
            response["latency_ms"] = round((time.monotonic() - started) * 1000)
            db.save(body.session_id, state, key, payload, response)
            mark_outcome("booked" if response.get("booking") else "rejected" if any(t.get("status")=="rejected" for t in response.get("tool_trace",[])) else "draft" if response.get("draft") else "answered")
            return response

    app.state.agent = Agent(db, app)
    dist = ROOT / "frontend" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
        @app.get("/")
        def index():
            return FileResponse(dist / "index.html")
    return app
