"""Deterministic rule engine + conflict resolution.

Forward-chains over the policy set, collects every rule whose conditions match,
and when matched rules disagree resolves the conflict by an explicit, logged
precedence: override > framework rank > lex specialis > most-restrictive.
"""
from __future__ import annotations
from pathlib import Path
import yaml
from schemas import ActionFacts, Effect, RuleMatch, ConflictResolution

_RESTRICTIVENESS = {Effect.deny: 3, Effect.require_review: 2, Effect.flag: 1, Effect.allow: 0}


class PolicyEngine:
    def __init__(self, policy_path=None):
        path = Path(policy_path or Path(__file__).with_name("policies.yaml"))
        data = yaml.safe_load(path.read_text())
        self.framework_rank: dict[str, int] = data.get("framework_rank", {})
        self.rules: list[dict] = [r for r in data["rules"] if r.get("enabled", True)]

    def _matches(self, rule: dict, facts: ActionFacts, risk: float):
        when = rule.get("when", {})
        matched: list[str] = []
        for key, expected in when.items():
            if key == "action_type":
                if facts.action_type.value not in expected:
                    return None
                matched.append(f"action_type={facts.action_type.value}")
            elif key == "data_categories_any":
                have = {c.lower() for c in facts.data_categories}
                hit = have.intersection(e.lower() for e in expected)
                if not hit:
                    return None
                matched.append(f"data={'/'.join(sorted(hit))}")
            elif key == "scope":
                if facts.scope.value not in expected:
                    return None
                matched.append(f"scope={facts.scope.value}")
            elif key == "environment":
                if facts.environment.value not in expected:
                    return None
                matched.append(f"env={facts.environment.value}")
            elif key == "resource_sensitivity":
                if facts.resource_sensitivity.value not in expected:
                    return None
                matched.append(f"sensitivity={facts.resource_sensitivity.value}")
            elif key == "actor_role":
                if facts.actor_role.value not in expected:
                    return None
                matched.append(f"role={facts.actor_role.value}")
            elif key == "reversible":
                if facts.reversible is not expected:
                    return None
                matched.append(f"reversible={facts.reversible}")
            elif key == "min_risk":
                if risk < float(expected):
                    return None
                matched.append(f"risk>={expected}")
            else:
                return None
        return matched

    def evaluate(self, facts: ActionFacts, risk: float) -> list[RuleMatch]:
        fired: list[RuleMatch] = []
        for rule in self.rules:
            matched = self._matches(rule, facts, risk)
            if matched is None:
                continue
            fired.append(RuleMatch(
                rule_id=rule["id"], description=rule["description"],
                effect=Effect(rule["effect"]), framework=rule["framework"],
                article=rule["article"], version=rule["version"],
                matched_on=matched, specificity=len(matched)))
        return fired

    def resolve(self, fired: list[RuleMatch]):
        if not fired:
            return Effect.allow, None, None

        def rank(rule_id: str) -> int:
            src = next(r for r in self.rules if r["id"] == rule_id)
            if src.get("org_override"):
                return -1
            return self.framework_rank.get(src["framework"], 99)

        def sort_key(rm: RuleMatch):
            src = next(r for r in self.rules if r["id"] == rm.rule_id)
            return (0 if src.get("org_override") else 1,
                    rank(rm.rule_id),
                    -rm.specificity,
                    -_RESTRICTIVENESS[rm.effect])

        ordered = sorted(fired, key=sort_key)
        winner = ordered[0]

        effects = {rm.effect for rm in fired}
        if len(effects) == 1:
            return winner.effect, None, winner.rule_id

        losers = [rm.rule_id for rm in fired if rm.rule_id != winner.rule_id]
        reason = self._precedence_reason(winner, ordered[1])
        conflict = ConflictResolution(
            conflicting_rules=[rm.rule_id for rm in fired],
            winner=winner.rule_id, winning_effect=winner.effect,
            losers=losers, precedence_reason=reason)
        return winner.effect, conflict, winner.rule_id

    def _precedence_reason(self, winner: RuleMatch, runner_up: RuleMatch) -> str:
        w = next(r for r in self.rules if r["id"] == winner.rule_id)
        if w.get("org_override"):
            return f"{winner.rule_id} is an organizational override and beats all frameworks"
        wr = self.framework_rank.get(winner.framework, 99)
        rr = self.framework_rank.get(runner_up.framework, 99)
        if wr != rr:
            return (f"{winner.rule_id} ({winner.framework}) outranks "
                    f"{runner_up.rule_id} ({runner_up.framework}) by framework precedence")
        if winner.specificity != runner_up.specificity:
            return (f"{winner.rule_id} matched more conditions "
                    f"({winner.specificity} vs {runner_up.specificity}), lex specialis")
        return (f"tie broken by most-restrictive-wins (fail closed): "
                f"{winner.effect.value} over {runner_up.effect.value}, no override present")