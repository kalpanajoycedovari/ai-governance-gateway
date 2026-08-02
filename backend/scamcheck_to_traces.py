"""Convert real ScamCheck agent decisions into governance trace format.

Reads the ScamCheck worker /history endpoint, maps each stored scan to the
trace schema the Governance Agent audits, and writes traces to a JSONL file.

Run (with the scamcheck worker running on 8787):
    python scamcheck_to_traces.py
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone

SCAMCHECK_HISTORY = "http://localhost:8787/history"
OUT_PATH = "data/scamcheck_traces.jsonl"


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def to_trace(scan: dict) -> dict:
    score = scan.get("score", 50)
    verdict = scan.get("verdict", "")
    analysis = scan.get("aiAnalysis", "")
    checked = scan.get("checkedAt", 0)
    return {
        "trace_id": "scamscan-" + str(checked),
        "timestamp": iso(checked),
        "agent_name": "scamscan",
        "user_input": scan.get("url", ""),
        "agent_output": f"Trust score {score}/100. {verdict} {analysis}".strip(),
        "steps": [],
        "confidence": round(score / 100, 2),
        # ScamCheck does not disclose it is AI or route to a human, so these are
        # honestly false. The governance layer should flag that.
        "human_reviewed": False,
        "ai_disclosed": False,
    }


def main() -> None:
    with urllib.request.urlopen(SCAMCHECK_HISTORY, timeout=10) as r:
        data = json.loads(r.read().decode("utf-8"))
    scans = data.get("pastScans", [])
    traces = [to_trace(s) for s in scans]
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t) + "\n")
    print(f"Wrote {len(traces)} traces to {OUT_PATH}")
    for t in traces:
        print(f"  {t['trace_id']}  {t['user_input']}  conf={t['confidence']}")


if __name__ == "__main__":
    main()