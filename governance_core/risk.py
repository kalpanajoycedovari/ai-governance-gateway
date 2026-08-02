"""Transparent additive risk model. (Answers "why is it 85 not 72?")

    risk = 100 * sum_i ( weight_i * value_i ),  value_i in [0, 1]

Linear + independent factors, so each term (weight_i * value_i * 100) is exactly
that factor's Shapley value. The contribution table is the exact attribution.
"""
from __future__ import annotations
from schemas import (ActionFacts, ActionType, Scope, Sensitivity, ActorRole,
                     RiskBreakdown, FactorContribution)

WEIGHTS: dict[str, float] = {
    "action_severity": 0.30,
    "data_sensitivity": 0.25,
    "scope": 0.15,
    "irreversibility": 0.10,
    "privilege_gap": 0.10,
    "anomaly": 0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "weights must sum to 1.0"

_ACTION_SEVERITY: dict[ActionType, float] = {
    ActionType.read: 0.10, ActionType.list: 0.10, ActionType.share: 0.50,
    ActionType.write: 0.40, ActionType.update: 0.40, ActionType.transfer: 0.60,
    ActionType.execute: 0.60, ActionType.grant_access: 0.70, ActionType.deploy: 0.70,
    ActionType.delete: 0.90, ActionType.purge: 0.95,
}

_DATA_SENSITIVITY: dict[str, float] = {
    "none": 0.0, "public": 0.0, "internal": 0.3,
    "pii": 0.8, "financial": 0.8, "health": 0.9, "phi": 0.9,
    "credentials": 1.0, "secrets": 1.0,
}

_RESOURCE_SENSITIVITY: dict[Sensitivity, float] = {
    Sensitivity.public: 0.0, Sensitivity.internal: 0.3,
    Sensitivity.confidential: 0.7, Sensitivity.restricted: 1.0,
}

_SCOPE: dict[Scope, float] = {Scope.single: 0.2, Scope.bulk: 0.6, Scope.all: 1.0}

_ACTOR_LEVEL: dict[ActorRole, int] = {
    ActorRole.external_api: 1, ActorRole.intern: 1, ActorRole.developer: 2,
    ActorRole.hr: 2, ActorRole.finance_agent: 2, ActorRole.service_account: 3,
    ActorRole.admin: 4,
}
_MAX_LEVEL = 4


def _band(score: float) -> str:
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def score_risk(facts: ActionFacts, anomaly_value: float) -> RiskBreakdown:
    v_action = _ACTION_SEVERITY.get(facts.action_type, 0.5)

    cat_max = max((_DATA_SENSITIVITY.get(c.lower(), 0.3) for c in facts.data_categories),
                  default=0.0)
    v_data = max(cat_max, _RESOURCE_SENSITIVITY[facts.resource_sensitivity])

    v_scope = _SCOPE[facts.scope]
    v_irrev = 0.0 if facts.reversible else 1.0

    required_level = max(1, round(v_action * _MAX_LEVEL))
    actor_level = _ACTOR_LEVEL.get(facts.actor_role, 2)
    v_priv = max(0, required_level - actor_level) / _MAX_LEVEL

    v_anom = max(0.0, min(1.0, anomaly_value))

    values = {
        "action_severity": v_action,
        "data_sensitivity": v_data,
        "scope": v_scope,
        "irreversibility": v_irrev,
        "privilege_gap": v_priv,
        "anomaly": v_anom,
    }

    contributions = []
    total = 0.0
    for factor, weight in WEIGHTS.items():
        pts = weight * values[factor] * 100.0
        total += pts
        contributions.append(FactorContribution(
            factor=factor, raw_value=values[factor], weight=weight, points=pts))

    total = round(total, 1)
    return RiskBreakdown(score=total, band=_band(total), contributions=contributions)