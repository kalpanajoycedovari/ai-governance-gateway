from __future__ import annotations
from fastapi import FastAPI
from pydantic import BaseModel
from .config import settings
from .deterministic import checks
from .kb import retrieve
from .kb import hybrid
from contextlib import asynccontextmanager

from .datahub_mcp import client as datahub_mcp_client
from .mcp_routes import router as mcp_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Open one long-lived DataHub MCP stdio session for the process.
    await datahub_mcp_client.start()
    try:
        yield
    finally:
        await datahub_mcp_client.stop()


app = FastAPI(title="Agent Governance Layer - core", lifespan=lifespan)
app.include_router(mcp_router)
class Trace(BaseModel):
    trace_id: str
    timestamp: str
    agent_name: str
    user_input: str
    agent_output: str
    steps: list[dict] = []
    confidence: float | None = None
    human_reviewed: bool = False
    ai_disclosed: bool = False
class CheckRequest(BaseModel):
    trace: Trace
    high_risk: bool = False
class SearchRequest(BaseModel):
    query: str
    k: int = 4
    frameworks: list[str] | None = None
    mode: str = "hybrid"
@app.get("/health")
def health():
    return {"status": "ok"}
@app.post("/checks")
def run_checks(req: CheckRequest):
    findings = checks.run_all(
        req.trace.model_dump(),
        high_risk=req.high_risk,
        min_confidence=settings.min_confidence,
        retention_days=settings.retention_days,
    )
    return {
        "findings": findings,
        "auto_pass_deterministic": all(f["status"] != "fail" for f in findings),
    }
@app.post("/kb/search")
def kb_search(req: SearchRequest):
    return hybrid.search(req.query, req.k, req.frameworks, req.mode)


@app.get("/kb/index")
def kb_index():
    return hybrid.index_status()
from typing import Any
from . import db
class AuditRecord(BaseModel):
    trace_id: str | None = None
    agent_name: str | None = None
    risk_level: str | None = None
    annex_iii_category: str | None = None
    uk_regime: str | None = None
    auto_pass: bool | None = None
    bias: dict[str, Any] | None = None
    deterministic: list[dict] | None = None
    report: str | None = None
@app.post("/audit")
def store_audit(record: AuditRecord):
    db.store_audit(record.model_dump())
    return {"stored": True, "agent_name": record.agent_name}
@app.get("/registry")
def registry():
    return {"agents": db.get_registry()}
from fastapi.responses import FileResponse
import os
_STATIC = os.path.join(os.path.dirname(__file__), "..", "static")
@app.get("/")
def dashboard():
    return FileResponse(os.path.join(_STATIC, "registry.html"))
from .kb import sources as kb_sources
@app.post("/ingest")
def ingest_kb():
    result = kb_sources.ingest_from_sources()
    return result
# ---- Governance gateway endpoints (report + audit log) ----
from .governance_gateway_api import router as gateway_router
app.include_router(gateway_router)
