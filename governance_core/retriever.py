"""Live policy retrieval from local Qdrant. Replaces the stub in engine.py.

Embeds the incoming request with the SAME model used at ingest time
(bge-small-en-v1.5) and returns the top-k policies by cosine similarity as
PolicyHit objects. The embedder is loaded once and reused.
"""
from __future__ import annotations
from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from schemas import ActionFacts, PolicyHit

COLLECTION = "governance_policies"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
TOP_K = 4


class QdrantRetriever:
    """Callable: ActionFacts -> list[PolicyHit]. Drop-in for the engine."""

    def __init__(self, url: str = "http://localhost:6333", top_k: int = TOP_K):
        self._embedder = TextEmbedding(model_name=EMBED_MODEL)
        self._client = QdrantClient(url=url)
        self._top_k = top_k

    def _query_text(self, facts: ActionFacts) -> str:
        # Describe the request in the same vocabulary the policies were indexed in.
        cats = ", ".join(facts.data_categories) or "no specific data"
        return (f"{facts.action_type.value} {facts.resource} "
                f"involving {cats}, scope {facts.scope.value}, "
                f"environment {facts.environment.value}, "
                f"reversible {facts.reversible}")

    def __call__(self, facts: ActionFacts) -> list[PolicyHit]:
        vector = next(iter(self._embedder.embed([self._query_text(facts)]))).tolist()
        hits = self._client.query_points(
            collection_name=COLLECTION,
            query=vector,
            limit=self._top_k,
            with_payload=True,
        ).points
        return [
            PolicyHit(
                policy_id=h.payload["policy_id"],
                similarity=round(float(h.score), 3),
                framework=h.payload["framework"],
            )
            for h in hits
        ]


if __name__ == "__main__":
    from engine import GovernanceEngine
    from schemas import (ActionType, Scope, Sensitivity, Environment, ActorRole)

    retriever = QdrantRetriever()
    engine = GovernanceEngine(retriever=retriever)

    facts = ActionFacts(
        action_type=ActionType.delete, resource="customer_records",
        resource_sensitivity=Sensitivity.restricted, data_categories=["pii"],
        scope=Scope.all, reversible=False, environment=Environment.prod,
        actor_id="agent_db_07", actor_role=ActorRole.developer)

    print(engine.evaluate(facts).explain())