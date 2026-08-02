"""The governance engine. Turns ActionFacts into a Verdict + full DecisionTrace.

  facts -> anomaly -> risk -> retrieval -> rules -> conflict -> confidence -> verdict

The verdict is produced HERE, by code. The LLM only phrases the reason string;
it never sets `verdict`.
"""
from __future__ import annotations
import uuid
from typing import Callable, Optional
from schemas import ActionFacts, DecisionTrace, Verdict, Effect, PolicyHit
from risk import score_risk
from rules import PolicyEngine
from anomaly import BehaviourStore
from confidence import estimate_confidence

DENY_AT = 70.0
REVIEW_AT = 40.0
NEAR_THRESHOLD = 8.0
MIN_CONFIDENCE = 0.55

Retriever = Callable[[ActionFacts], list[PolicyHit]]


def _stub_retriever(facts: ActionFacts) -> list[PolicyHit]:
    return [
        PolicyHit(policy_id="EU-AI-ACT-ART14", similarity=0.88, framework="EU_AI_ACT"),
        PolicyHit(policy_id="GDPR-ART17", similarity=0.61, framework="GDPR"),
    ]


class GovernanceEngine:
    def __init__(self, policy_engine: Optional[PolicyEngine] = None,
                 behaviour: Optional[BehaviourStore] = None,
                 retriever: Optional[Retriever] = None):
        self.policies = policy_engine or PolicyEngine()
        self.behaviour = behaviour or BehaviourStore()
        if retriever is None:
            from retriever import QdrantRetriever
            retriever = QdrantRetriever()
        self.retrieve = retriever

    def evaluate(self, facts: ActionFacts, request_id: str = None) -> DecisionTrace:
        request_id = request_id or f"req_{uuid.uuid4().hex[:8]}"

        anomaly = self.behaviour.score(facts)
        risk = score_risk(facts, anomaly_value=anomaly.score)
        policies = self.retrieve(facts)
        fired = self.policies.evaluate(facts, risk.score)
        winning_effect, conflict, winner_id = self.policies.resolve(fired)
        confidence = estimate_confidence(facts, policies, fired)
        verdict, reason = self._decide(risk.score, winning_effect, confidence.value, winner_id)

        self.behaviour.observe(facts)

        return DecisionTrace(
            request_id=request_id, facts=facts, policies_retrieved=policies,
            rules_fired=fired, conflict=conflict, risk=risk, anomaly=anomaly,
            confidence=confidence, verdict=verdict, reason=reason)

    def _decide(self, risk: float, effect: Effect, confidence: float, winner_id):
        top = winner_id or "policy"
        if effect == Effect.deny:
            return Verdict.deny, f"Denied by policy rule {top} (deterministic, fail-closed)."
        if effect == Effect.require_review:
            return Verdict.review, f"Policy rule {top} requires documented human oversight."

        if risk >= DENY_AT:
            return Verdict.deny, f"Risk {risk:.0f} at or above deny threshold {DENY_AT:.0f}."

        near_edge = abs(risk - REVIEW_AT) <= NEAR_THRESHOLD or abs(risk - DENY_AT) <= NEAR_THRESHOLD
        # Low confidence only forces review when there is something at stake:
        # a low-risk request with no rules firing has nothing to be unsure about.
        if confidence < MIN_CONFIDENCE and risk >= REVIEW_AT:
            return Verdict.review, (f"Confidence {confidence:.2f} below {MIN_CONFIDENCE:.2f} "
                                    f"on an elevated-risk request; escalating.")
        if REVIEW_AT <= risk < DENY_AT or near_edge:
            return Verdict.review, f"Risk {risk:.0f} in the review band ({REVIEW_AT:.0f}-{DENY_AT:.0f})."

        return Verdict.approve, f"Risk {risk:.0f} below review threshold and no blocking policy."