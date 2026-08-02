"""Postgres helpers for storing audit results and reading the agent registry."""
from __future__ import annotations

import json
from typing import Any

import psycopg

from .config import settings


def store_audit(result: dict[str, Any]) -> None:
    """Insert one audit result into the audits table."""
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            """
            INSERT INTO audits
              (trace_id, agent_name, risk_level, annex_iii_category,
               uk_regime, auto_pass, bias_status, findings, report)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                result.get("trace_id"),
                result.get("agent_name"),
                result.get("risk_level"),
                result.get("annex_iii_category"),
                result.get("uk_regime"),
                result.get("auto_pass"),
                (result.get("bias") or {}).get("status"),
                json.dumps(result.get("deterministic") or []),
                result.get("report"),
            ),
        )


def get_registry() -> list[dict[str, Any]]:
    """Return one row per agent with rolled-up compliance status."""
    with psycopg.connect(settings.database_url) as conn:
        rows = conn.execute(
            """
            SELECT
              agent_name,
              COUNT(*)                                  AS total_audits,
              SUM(CASE WHEN auto_pass THEN 1 ELSE 0 END) AS passed,
              SUM(CASE WHEN NOT auto_pass THEN 1 ELSE 0 END) AS failed,
              MAX(audited_at)                           AS last_audited
            FROM audits
            GROUP BY agent_name
            ORDER BY failed DESC, agent_name
            """
        ).fetchall()

    registry = []
    for r in rows:
        agent, total, passed, failed, last = r
        rate = round((passed / total) * 100) if total else 0
        registry.append({
            "agent_name": agent,
            "total_audits": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": rate,
            "needs_attention": failed > 0,
            "last_audited": last.isoformat() if last else None,
        })
    return registry