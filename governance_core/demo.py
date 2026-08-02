"""Runnable showcase.  python demo.py

Each scenario is one interview gotcha, answered with a printed DecisionTrace.
"""
from engine import GovernanceEngine
from schemas import ActionFacts, ActionType, Scope, Sensitivity, Environment, ActorRole

SEP = "=" * 74


def run(title, facts, engine, warm_agent=False):
    if warm_agent:
        for _ in range(8):
            engine.behaviour.observe(ActionFacts(
                action_type=ActionType.read, resource="dashboard",
                actor_id=facts.actor_id, actor_role=facts.actor_role))
    print(SEP)
    print(title)
    print(SEP)
    print(engine.evaluate(facts).explain())
    print()


def main():
    engine = GovernanceEngine()

    run("SCENARIO 1  bulk irreversible PII delete on prod, developer agent",
        ActionFacts(action_type=ActionType.delete, resource="customer_records",
            resource_sensitivity=Sensitivity.restricted, data_categories=["pii"],
            scope=Scope.all, reversible=False, environment=Environment.prod,
            actor_id="agent_db_07", actor_role=ActorRole.developer,
            extraction_confidence=0.94), engine)

    run("SCENARIO 2  delete a record that is both PII and financial (GDPR vs retention)",
        ActionFacts(action_type=ActionType.delete, resource="closed_account_12831",
            resource_sensitivity=Sensitivity.confidential,
            data_categories=["pii", "financial"], scope=Scope.single, reversible=False,
            environment=Environment.prod, actor_id="agent_finance_02",
            actor_role=ActorRole.finance_agent, extraction_confidence=0.9), engine)

    run("SCENARIO 3  quiet read-only agent suddenly deploys to prod (anomaly)",
        ActionFacts(action_type=ActionType.deploy, resource="payments_service",
            resource_sensitivity=Sensitivity.confidential, data_categories=["internal"],
            scope=Scope.single, reversible=True, environment=Environment.prod,
            actor_id="agent_reporter_9", actor_role=ActorRole.developer,
            extraction_confidence=0.85), engine, warm_agent=True)

    run("SCENARIO 4  intern reads a public dashboard (should auto-approve)",
        ActionFacts(action_type=ActionType.read, resource="public_status_page",
            resource_sensitivity=Sensitivity.public, data_categories=["public"],
            scope=Scope.single, reversible=True, environment=Environment.prod,
            actor_id="agent_intern_1", actor_role=ActorRole.intern,
            extraction_confidence=0.97), engine)


if __name__ == "__main__":
    main()