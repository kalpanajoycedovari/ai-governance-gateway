"""Behavioural anomaly detection. (The "5 approvals then DELETE database" case.)

Each agent gets a rolling baseline. A request far from that agent's own recent
behaviour raises the 'anomaly' factor, which feeds the risk score. v1 is a
transparent z-score on action severity; upgrade path is a Postgres-backed store
plus an Isolation Forest once there is enough history.
"""
from __future__ import annotations
from collections import defaultdict, deque
from statistics import mean, pstdev
from schemas import ActionFacts, AnomalyReport
from risk import _ACTION_SEVERITY

_WINDOW = 50
_SIGMA_SATURATION = 4.0
_MIN_SAMPLES = 5


class BehaviourStore:
    def __init__(self) -> None:
        self._severity: dict[str, deque] = defaultdict(lambda: deque(maxlen=_WINDOW))

    def score(self, facts: ActionFacts) -> AnomalyReport:
        history = self._severity[facts.actor_id]
        sev = _ACTION_SEVERITY.get(facts.action_type, 0.5)
        n = len(history)

        if n < _MIN_SAMPLES:
            return AnomalyReport(score=0.0, sigma=0.0, baseline_samples=n,
                note=f"cold start: need {_MIN_SAMPLES} samples to baseline this agent")

        mu = mean(history)
        sd = pstdev(history)
        if sd == 0:
            sigma = 0.0 if sev == mu else _SIGMA_SATURATION
        else:
            sigma = (sev - mu) / sd

        score = max(0.0, min(1.0, sigma / _SIGMA_SATURATION))
        note = ("within normal range for this agent" if score < 0.5
                else "behaviour spike vs this agent's own baseline")
        return AnomalyReport(score=score, sigma=sigma, baseline_samples=n, note=note)

    def observe(self, facts: ActionFacts) -> None:
        self._severity[facts.actor_id].append(_ACTION_SEVERITY.get(facts.action_type, 0.5))