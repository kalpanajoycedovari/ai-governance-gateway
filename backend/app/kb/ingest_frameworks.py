"""Load the framework-tagged governance corpus into Qdrant as a HYBRID collection.

Same embedding + collection config as ingest.py (BAAI/bge-small-en-v1.5 dense +
Qdrant/bm25 sparse), but the sources come from governance_corpus.py: one
obligation per chunk, with framework / ref / title carried into the payload so
/kb/search can filter by framework and the report can cite article numbers.

Run:  python -m app.kb.ingest_frameworks

NOTE: like ingest.py, this REBUILDS the collection from scratch. It replaces the
old Company Policy / UK / EU AI Act chunks with the 25 corpus chunks. If you want
the company policy kept, add it into governance_corpus.py and re-run.
"""
from __future__ import annotations
from collections import Counter
from qdrant_client import QdrantClient
from ..config import settings
from .governance_corpus import CORPUS

DENSE_MODEL = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL = "Qdrant/bm25"


def ingest() -> None:
    client = QdrantClient(url=settings.qdrant_url,
                          api_key=settings.qdrant_api_key or None)
    client.set_model(DENSE_MODEL)
    client.set_sparse_model(SPARSE_MODEL)

    # Fresh hybrid collection (same config as ingest.py).
    if client.collection_exists(settings.collection):
        client.delete_collection(settings.collection)
    client.create_collection(
        collection_name=settings.collection,
        vectors_config=client.get_fastembed_vector_params(),
        sparse_vectors_config=client.get_fastembed_sparse_vector_params(),
    )

    docs, ids, meta = [], [], []
    for i, c in enumerate(CORPUS):
        # Embed title + text: dense captures meaning, BM25 catches the legal terms.
        docs.append(f"{c['title']}. {c['text']}")
        ids.append(i)
        meta.append({
            "source": c["framework"],     # kept as 'source' for backward compatibility
            "framework": c["framework"],  # explicit key for framework filtering
            "ref": c["ref"],
            "title": c["title"],
            "text": c["text"],
        })

    client.add(collection_name=settings.collection,
               documents=docs, ids=ids, metadata=meta)

    print(f"Ingested {len(docs)} chunks into hybrid '{settings.collection}'")
    for fw, n in sorted(Counter(m["framework"] for m in meta).items()):
        print(f"  {fw}: {n}")


if __name__ == "__main__":
    ingest()
