"""One-off: embed each policy rule and upsert into local Qdrant.

Run once (and re-run whenever policies.yaml changes). Uses fastembed
BAAI/bge-small-en-v1.5 (384-dim), local and deterministic, no network in the
decision path. The text we embed is the rule's description plus its framework
and article, so a request matches on meaning, not just keywords.
"""
from __future__ import annotations
from pathlib import Path
import yaml
from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

COLLECTION = "governance_policies"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
DIM = 384


def embed_text(rule: dict) -> str:
    return (f"{rule['framework']} {rule['article']}: {rule['description']}")


def main():
    path = Path(__file__).with_name("policies.yaml")
    data = yaml.safe_load(path.read_text())
    rules = data["rules"]  # index ALL rules, even disabled ones, for retrieval context

    print(f"loading embedding model {EMBED_MODEL} (first run downloads it)...")
    embedder = TextEmbedding(model_name=EMBED_MODEL)

    texts = [embed_text(r) for r in rules]
    vectors = list(embedder.embed(texts))

    client = QdrantClient(url="http://localhost:6333")
    client.recreate_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=DIM, distance=Distance.COSINE),
    )

    points = []
    for i, (rule, vec) in enumerate(zip(rules, vectors)):
        points.append(PointStruct(
            id=i,
            vector=vec.tolist(),
            payload={
                "policy_id": rule["id"],
                "framework": rule["framework"],
                "article": rule["article"],
                "version": rule["version"],
                "description": rule["description"],
            },
        ))

    client.upsert(collection_name=COLLECTION, points=points)
    count = client.count(collection_name=COLLECTION).count
    print(f"indexed {count} policies into '{COLLECTION}'")


if __name__ == "__main__":
    main()