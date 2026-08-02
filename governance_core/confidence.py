"""Confidence estimation. (Gives the Human Review branch a principled trigger.)

Not the LLM's self-reported number. Geometric mean of three independent signals,
so any single weak link drags the whole thing down:

  retrieval_margin   how clearly the top policy beat the runner-up in Qdrant
  rule_determinism   did rules fire on exact matches, or is nothing firing?
  extraction_agree   the LLM's own extraction confidence, one input only

Low confidence (or a risk score near a threshold) is the honest reason a request
routes to a human rather than auto-deciding.
"""
from __future__ import annotations
from schemas import ConfidenceReport, RuleMatch, PolicyHit, ActionFacts


def _geomean(values: list[float]) -> float:
    vals = [max(1e-6, v) for v in values]
    prod = 1.0
    for v in vals:
        prod *= v
    return prod ** (1.0 / len(vals))


def estimate_confidence(facts: ActionFacts, policies: list[PolicyHit],
                        rules_fired: list[RuleMatch]) -> ConfidenceReport:
    if len(policies) >= 2:
        s = sorted((p.similarity for p in policies), reverse=True)
        retrieval_margin = max(0.35, min(1.0, 0.5 + (s[0] - s[1]) * 6.0))
    elif len(policies) == 1:
        retrieval_margin = 0.7
    else:
        retrieval_margin = 0.3

    if rules_fired:
        rule_determinism = min(1.0, 0.6 + 0.1 * len(rules_fired))
    else:
        rule_determinism = 0.5

    extraction_agree = facts.extraction_confidence

    components = {
        "retrieval_margin": round(retrieval_margin, 3),
        "rule_determinism": round(rule_determinism, 3),
        "extraction_agree": round(extraction_agree, 3),
    }
    value = round(_geomean(list(components.values())), 3)
    return ConfidenceReport(value=value, components=components)