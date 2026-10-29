import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.db import Base, Ticket, engine, get_db
from app.logging_config import setup_logging
from app.schemas import TicketCreate, TicketOut, TicketUpdate

log = setup_logging()
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
APP_ENV = os.getenv("APP_ENV", "local")
STARTED = time.time()
METRICS = {"requests_total": 0, "errors_5xx_total": 0, "duration_ms_sum": 0.0}


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    log.info("startup", extra={"extra_fields": {"version": APP_VERSION, "env": APP_ENV}})
    yield
    log.info("shutdown")


app = FastAPI(title="Apex Operations API", version=APP_VERSION, lifespan=lifespan)


@app.middleware("http")
async def request_logger(request: Request, call_next):
    rid = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["x-request-id"] = rid
        return response
    except Exception:
        log.exception("unhandled_error", extra={"extra_fields": {"request_id": rid}})
        return JSONResponse({"detail": "Internal server error"}, status_code=500)
    finally:
        ms = round((time.perf_counter() - start) * 1000, 2)
        METRICS["requests_total"] += 1
        METRICS["duration_ms_sum"] += ms
        if status >= 500:
            METRICS["errors_5xx_total"] += 1
        if not request.url.path.startswith("/static"):
            log.info("request", extra={"extra_fields": {
                "request_id": rid, "method": request.method, "path": request.url.path,
                "status": status, "duration_ms": ms}})


# ---------- Health / Ready / Metrics ----------
@app.get("/health")
def health():
    """Liveness: process zinda hai?"""
    return {"status": "ok", "version": APP_VERSION, "env": APP_ENV,
            "uptime_seconds": int(time.time() - STARTED)}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    """Readiness: DB se baat kar sakta hai?"""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "up", "version": APP_VERSION}
    except Exception:
        log.exception("readiness_failed")
        return JSONResponse({"status": "not_ready", "database": "down"}, status_code=503)


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    m = METRICS
    return (
        "# TYPE apex_requests_total counter\n"
        f"apex_requests_total {m['requests_total']}\n"
        "# TYPE apex_errors_5xx_total counter\n"
        f"apex_errors_5xx_total {m['errors_5xx_total']}\n"
        "# TYPE apex_request_duration_ms_sum counter\n"
        f"apex_request_duration_ms_sum {m['duration_ms_sum']:.2f}\n"
        "# TYPE apex_uptime_seconds gauge\n"
        f"apex_uptime_seconds {int(time.time() - STARTED)}\n"
    )


# ---------- Tickets API ----------
@app.get("/api/tickets", response_model=List[TicketOut])
def list_tickets(db: Session = Depends(get_db)):
    return db.query(Ticket).order_by(Ticket.id.desc()).all()


@app.post("/api/tickets", response_model=TicketOut, status_code=201)
def create_ticket(body: TicketCreate, db: Session = Depends(get_db)):
    t = Ticket(**body.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    log.info("ticket_created", extra={"extra_fields": {"ticket_id": t.id, "priority": t.priority}})
    return t


@app.patch("/api/tickets/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id: int, body: TicketUpdate, db: Session = Depends(get_db)):
    t = db.get(Ticket, ticket_id)
    if not t:
        raise HTTPException(404, "Ticket not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t


@app.delete("/api/tickets/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    t = db.get(Ticket, ticket_id)
    if not t:
        raise HTTPException(404, "Ticket not found")
    db.delete(t)
    db.commit()


@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    by_status = dict(db.query(Ticket.status, func.count()).group_by(Ticket.status).all())
    by_priority = dict(db.query(Ticket.priority, func.count()).group_by(Ticket.priority).all())
    return {"total": sum(by_status.values()), "by_status": by_status, "by_priority": by_priority}


# Failure-investigation demo: is endpoint se jaan-boojh ke 500 aata hai (APP_ENV != production)
@app.get("/api/debug/crash")
def crash():
    if APP_ENV == "production":
        raise HTTPException(404)
    raise RuntimeError("Simulated failure for incident drill")


# ---------- Frontend ----------
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse("app/static/index.html")
