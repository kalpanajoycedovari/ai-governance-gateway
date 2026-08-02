"""Deterministic compliance checks. No LLM here, by design.

Every result is reproducible and defensible in front of an auditor, because a
rule either passed or it did not. Judgement calls (bias, risk tier, narrative)
live in the agent layer, never here.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:(?:\+|00)\d{1,3}[\s-]?)?(?:\d[\s-]?){9,13}")
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")

REQUIRED_FIELDS = ["trace_id", "timestamp", "agent_name", "user_input", "agent_output"]


def _finding(check: str, article: str, status: str, detail: str) -> dict:
    return {"check": check, "article": article, "status": status, "detail": detail}


def check_log_completeness(trace: dict[str, Any]) -> dict:
    missing = [f for f in REQUIRED_FIELDS if not trace.get(f)]
    if missing:
        return _finding("log_completeness", "Art. 12", "fail",
                        f"Missing required fields: {', '.join(missing)}")
    return _finding("log_completeness", "Art. 12", "pass",
                    "All required record-keeping fields present")


def check_ai_disclosure(trace: dict[str, Any]) -> dict:
    if trace.get("ai_disclosed") is True:
        return _finding("ai_disclosure", "Art. 13", "pass",
                        "User was informed they interacted with an AI system")
    return _finding("ai_disclosure", "Art. 13", "fail",
                    "No record that AI interaction was disclosed to the user")


def check_human_oversight(trace: dict[str, Any], high_risk: bool) -> dict:
    reviewed = trace.get("human_reviewed") is True
    escalated = any(s.get("type") == "escalation" for s in trace.get("steps", []))
    if not high_risk:
        return _finding("human_oversight", "Art. 14", "not_applicable",
                        "Decision not classified high-risk")
    if reviewed or escalated:
        return _finding("human_oversight", "Art. 14", "pass",
                        "Human oversight step present for high-risk decision")
    return _finding("human_oversight", "Art. 14", "fail",
                    "High-risk decision had no human review or escalation")


def check_confidence(trace: dict[str, Any], minimum: float) -> dict:
    c = trace.get("confidence")
    if c is None:
        return _finding("confidence_threshold", "Art. 15", "fail",
                        "No confidence score recorded")
    if c >= minimum:
        return _finding("confidence_threshold", "Art. 15", "pass",
                        f"Confidence {c:.2f} meets minimum {minimum:.2f}")
    return _finding("confidence_threshold", "Art. 15", "fail",
                    f"Confidence {c:.2f} below minimum {minimum:.2f}")


def check_pii_leakage(trace: dict[str, Any]) -> dict:
    text = str(trace.get("agent_output", ""))
    hits = []
    if EMAIL_RE.search(text):
        hits.append("email")
    if CARD_RE.search(text):
        hits.append("card-like number")
    for m in PHONE_RE.finditer(text):
        if len(re.sub(r"\D", "", m.group())) >= 10:
            hits.append("phone")
            break
    if hits:
        return _finding("pii_leakage", "Art. 10", "fail",
                        f"Potential PII in output: {', '.join(sorted(set(hits)))}")
    return _finding("pii_leakage", "Art. 10", "pass",
                    "No obvious PII detected in output")


def check_retention(trace: dict[str, Any], max_days: int) -> dict:
    try:
        t = datetime.fromisoformat(str(trace.get("timestamp")).replace("Z", "+00:00"))
    except Exception:
        return _finding("retention", "Art. 12", "fail", "Timestamp unparseable")
    age = (datetime.now(timezone.utc) - t).days
    if age <= max_days:
        return _finding("retention", "Art. 12", "pass",
                        f"Record age {age}d within {max_days}d window")
    return _finding("retention", "Art. 12", "fail",
                    f"Record age {age}d exceeds {max_days}d retention window")


def run_all(trace: dict[str, Any], *, high_risk: bool, min_confidence: float,
            retention_days: int) -> list[dict]:
    return [
        check_log_completeness(trace),
        check_ai_disclosure(trace),
        check_human_oversight(trace, high_risk),
        check_confidence(trace, min_confidence),
        check_pii_leakage(trace),
        check_retention(trace, retention_days),
    ]