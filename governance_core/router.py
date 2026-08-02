"""FastAPI router: the governance gateway surface. Mount on your :8010 app.

/govern/decide      advisory: score + trace, runs nothing
/govern/decide/raw  advisory, LLM extracts facts from plain text
/govern/execute     enforcement: APPROVE runs the tool, DENY blocks,
                    HUMAN_REVIEW parks the request and returns a review_token
/govern/resume      the human decision returns here: approve runs the parked
                    tool, deny blocks. Reviewer identity + rationale recorded.
                    A human CANNOT override a hard policy DENY.
/govern/pending     parked reviews awaiting a human
/govern/reviews     resolved-review audit log
"""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from schemas import ActionFacts, DecisionTrace, Verdict
from engine import GovernanceEngine

router = APIRouter(prefix="/govern", tags=["governance"])
engine = GovernanceEngine()

# In-memory for v1. Swap for Postgres in prod so parked reviews survive a
# restart; the n8n Wait node persists its own copy of the execution too.
_PENDING: dict[str, dict] = {}
_REVIEW_LOG: list[dict] = []


class RawRequest(BaseModel):
    request_text: str


class ExecuteRequest(BaseModel):
    facts: ActionFacts
    tool: str
    tool_payload: dict = {}


class ExecuteResult(BaseModel):
    trace: DecisionTrace
    executed: bool
    detail: str
    review_token: str | None = None


class ResumeRequest(BaseModel):
    review_token: str
    decision: str            # "approve" or "deny"
    reviewer_email: str
    rationale: str


def _forward_to_tool(tool: str, payload: dict) -> str:
    """Placeholder for the real downstream call. Only reached on APPROVE."""
    return f"executed {tool} with {len(payload)} args"


@router.post("/decide", response_model=DecisionTrace)
def decide(facts: ActionFacts) -> DecisionTrace:
    return engine.evaluate(facts)


@router.post("/decide/raw", response_model=DecisionTrace)
def decide_raw(raw: RawRequest, x_agent_id: str = Header(...),
               x_agent_role: str = Header("developer")) -> DecisionTrace:
    try:
        from extractor import extract_facts
        facts = extract_facts(raw.request_text, actor_id=x_agent_id,
                              actor_role=x_agent_role)
    except Exception as e:
        raise HTTPException(status_code=422,
                            detail=f"fact_extraction_failed: {e}; route to human review")
    return engine.evaluate(facts)


@router.post("/execute", response_model=ExecuteResult)
def execute(req: ExecuteRequest) -> ExecuteResult:
    trace = engine.evaluate(req.facts)

    if trace.verdict == Verdict.approve:
        return ExecuteResult(trace=trace, executed=True,
                             detail=_forward_to_tool(req.tool, req.tool_payload))

    if trace.verdict == Verdict.deny:
        return ExecuteResult(trace=trace, executed=False,
                             detail=f"blocked: {trace.reason}")

    # HUMAN_REVIEW -> park so the n8n wait/resume branch can return a decision.
    _PENDING[trace.request_id] = {
        "facts": req.facts, "tool": req.tool, "payload": req.tool_payload,
        "reason": trace.reason, "parked_at": datetime.now(timezone.utc).isoformat(),
    }
    return ExecuteResult(trace=trace, executed=False,
                         detail="pending_human_review; parked on review branch",
                         review_token=trace.request_id)


@router.get("/pending")
def pending():
    return [{"review_token": k, "actor_id": v["facts"].actor_id,
             "tool": v["tool"], "reason": v["reason"], "parked_at": v["parked_at"]}
            for k, v in _PENDING.items()]


@router.post("/resume", response_model=ExecuteResult)
def resume(req: ResumeRequest) -> ExecuteResult:
    parked = _PENDING.pop(req.review_token, None)
    if parked is None:
        raise HTTPException(status_code=404,
                            detail="review_token not found or already resolved")

    decision = req.decision.strip().lower()
    if decision not in {"approve", "deny"}:
        _PENDING[req.review_token] = parked  # nothing decided, put it back
        raise HTTPException(status_code=422, detail="decision must be 'approve' or 'deny'")

    # Re-evaluate so the record reflects current policy.
    trace = engine.evaluate(parked["facts"], request_id=req.review_token)

    resolved = {
        "review_token": req.review_token, "decision": decision,
        "reviewer_email": req.reviewer_email, "rationale": req.rationale,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "engine_verdict": trace.verdict.value,
    }
    _REVIEW_LOG.append(resolved)

    # A human cannot override a hard policy DENY. Fail closed.
    if trace.verdict == Verdict.deny:
        return ExecuteResult(trace=trace, executed=False,
                             detail=f"policy hard-denies regardless of review ({trace.reason})")

    if decision == "approve":
        return ExecuteResult(trace=trace, executed=True,
                             detail=f"approved by {req.reviewer_email}: "
                                    f"{_forward_to_tool(parked['tool'], parked['payload'])}")

    return ExecuteResult(trace=trace, executed=False,
                         detail=f"denied by {req.reviewer_email}: {req.rationale}")


@router.get("/reviews")
def reviews():
    return _REVIEW_LOG