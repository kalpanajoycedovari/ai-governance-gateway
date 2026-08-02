"""Structured contracts for the governance gateway.

ActionFacts   -> the ONLY thing the LLM produces. It extracts facts, never decides.
DecisionTrace -> one ordered object every request emits; the explainability spine.
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    read = "read"; list = "list"; write = "write"; update = "update"
    share = "share"; transfer = "transfer"; execute = "execute"
    deploy = "deploy"; grant_access = "grant_access"; delete = "delete"; purge = "purge"


class Scope(str, Enum):
    single = "single"; bulk = "bulk"; all = "all"


class Sensitivity(str, Enum):
    public = "public"; internal = "internal"; confidential = "confidential"; restricted = "restricted"


class Environment(str, Enum):
    dev = "dev"; staging = "staging"; prod = "prod"


class ActorRole(str, Enum):
    intern = "intern"; developer = "developer"; hr = "hr"; finance_agent = "finance_agent"
    external_api = "external_api"; service_account = "service_account"; admin = "admin"


class Effect(str, Enum):
    allow = "allow"; flag = "flag"; require_review = "require_review"; deny = "deny"


class Verdict(str, Enum):
    approve = "APPROVE"; review = "HUMAN_REVIEW"; deny = "DENY"


class ActionFacts(BaseModel):
    """Facts extracted from the raw request by the LLM. No verdict field here."""
    action_type: ActionType
    resource: str = Field(description="Human name of the thing being acted on")
    resource_sensitivity: Sensitivity = Sensitivity.internal
    data_categories: list[str] = Field(default_factory=list)
    scope: Scope = Scope.single
    reversible: bool = True
    environment: Environment = Environment.prod
    actor_id: str
    actor_role: ActorRole = ActorRole.developer
    jurisdiction: Optional[str] = None
    raw_request: Optional[str] = None
    extraction_confidence: float = Field(default=0.9, ge=0.0, le=1.0)


class PolicyHit(BaseModel):
    policy_id: str; similarity: float; framework: str


class RuleMatch(BaseModel):
    rule_id: str; description: str; effect: Effect
    framework: str; article: str; version: str
    matched_on: list[str]; specificity: int


class ConflictResolution(BaseModel):
    conflicting_rules: list[str]; winner: str; winning_effect: Effect
    losers: list[str]; precedence_reason: str


class FactorContribution(BaseModel):
    factor: str; raw_value: float; weight: float; points: float


class RiskBreakdown(BaseModel):
    score: float = Field(ge=0.0, le=100.0)
    band: str
    contributions: list[FactorContribution]

    def as_table(self) -> str:
        rows = [f"  {'factor':<18}{'value':>7}{'weight':>8}{'points':>8}"]
        for c in sorted(self.contributions, key=lambda x: -x.points):
            rows.append(f"  {c.factor:<18}{c.raw_value:>7.2f}{c.weight:>8.2f}{c.points:>8.1f}")
        rows.append(f"  {'TOTAL':<18}{'':>7}{'':>8}{self.score:>8.1f}")
        return chr(10).join(rows)


class AnomalyReport(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    sigma: float; baseline_samples: int; note: str


class ConfidenceReport(BaseModel):
    value: float = Field(ge=0.0, le=1.0)
    components: dict[str, float]; method: str = "geometric_mean"


class DecisionTrace(BaseModel):
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    facts: ActionFacts
    policies_retrieved: list[PolicyHit] = Field(default_factory=list)
    rules_fired: list[RuleMatch] = Field(default_factory=list)
    conflict: Optional[ConflictResolution] = None
    risk: RiskBreakdown
    anomaly: AnomalyReport
    confidence: ConfidenceReport
    verdict: Verdict
    reason: str
    decided_by: str = "deterministic_engine"

    def explain(self) -> str:
        NL = chr(10)
        L = []
        L.append(f"REQUEST {self.request_id}   ->   VERDICT: {self.verdict.value}")
        L.append(f"  decided_by: {self.decided_by}")
        f = self.facts
        L.append("1. FACTS (extracted by LLM, no decision made here)")
        L.append(f"   {f.actor_role.value} '{f.actor_id}' wants to {f.action_type.value} "
                 f"'{f.resource}' [{','.join(f.data_categories) or 'no-data'}] "
                 f"scope={f.scope.value} env={f.environment.value} reversible={f.reversible}")
        L.append("2. POLICIES RETRIEVED")
        for p in self.policies_retrieved:
            L.append(f"   {p.policy_id} ({p.framework})  sim={p.similarity:.2f}")
        L.append("3. RULES FIRED (deterministic match on facts)")
        for r in self.rules_fired:
            L.append(f"   {r.rule_id}: {r.effect.value.upper()}  [{r.framework} {r.article} v{r.version}]")
            L.append(f"      matched on: {', '.join(r.matched_on)}")
        if self.conflict:
            c = self.conflict
            L.append("4. CONFLICT RESOLVED")
            L.append(f"   conflicting: {', '.join(c.conflicting_rules)}")
            L.append(f"   winner: {c.winner} ({c.winning_effect.value})")
            L.append(f"   losers: {', '.join(c.losers) or 'none'}")
            L.append(f"   why: {c.precedence_reason}")
        L.append("5. RISK (additive model, points == exact SHAP attribution)")
        L.append(self.risk.as_table())
        L.append(f"   band: {self.risk.band}")
        L.append("6. ANOMALY")
        L.append(f"   score={self.anomaly.score:.2f}  sigma={self.anomaly.sigma:.2f}  "
                 f"(n={self.anomaly.baseline_samples})  {self.anomaly.note}")
        L.append("7. CONFIDENCE")
        comp = "  ".join(f"{k}={v:.2f}" for k, v in self.confidence.components.items())
        L.append(f"   value={self.confidence.value:.2f}  ({comp})")
        L.append(f"VERDICT: {self.verdict.value}")
        L.append(f"REASON:  {self.reason}")
        return NL.join(L)