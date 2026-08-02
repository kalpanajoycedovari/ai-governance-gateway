"""Load tagged regulatory sources into Qdrant as a HYBRID collection.

Hybrid = dense vectors (meaning) + BM25 sparse vectors (exact legal terms).
Each source file declares its jurisdiction on the first line as:
    <!-- source: EU AI Act -->
That tag is attached to every chunk and stripped from the text.

Run: python -m app.kb.ingest
"""
from __future__ import annotations

import re
from pathlib import Path

from qdrant_client import QdrantClient

from ..config import settings

DENSE_MODEL = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL = "Qdrant/bm25"
TAG_RE = re.compile(r"^\s*<!--\s*source:\s*(.+?)\s*-->\s*", re.IGNORECASE)


def _read_tagged(path: Path) -> tuple[str, str]:
    """Return (source_tag, body_without_tag). Falls back to filename."""
    raw = path.read_text(encoding="utf-8")
    m = TAG_RE.match(raw)
    if m:
        return m.group(1).strip(), raw[m.end():]
    return path.stem, raw


def _chunk(text: str, size: int = 600, overlap: int = 80) -> list[str]:
    words = text.split()
    step = max(size - overlap, 1)
    chunks = [" ".join(words[j:j + size]) for j in range(0, len(words), step)]
    return chunks or [text]


def ingest(docs_dir: str = "docs", policy_dir: str = "data/policy") -> None:
    client = QdrantClient(url=settings.qdrant_url,
                          api_key=settings.qdrant_api_key or None)
    client.set_model(DENSE_MODEL)
    client.set_sparse_model(SPARSE_MODEL)

    # Fresh hybrid collection.
    if client.collection_exists(settings.collection):
        client.delete_collection(settings.collection)
    client.create_collection(
        collection_name=settings.collection,
        vectors_config=client.get_fastembed_vector_params(),
        sparse_vectors_config=client.get_fastembed_sparse_vector_params(),
    )

    docs, ids, meta = [], [], []
    idx = 0
    sources = list(Path(docs_dir).glob("*.md")) + list(Path(policy_dir).glob("*.md"))
    for p in sources:
        tag, body = _read_tagged(p)
        for chunk in _chunk(body):
            docs.append(chunk)
            ids.append(idx)
            meta.append({"source": tag, "file": p.name})
            idx += 1

    client.add(collection_name=settings.collection, documents=docs, ids=ids, metadata=meta)
    print(f"Ingested {len(docs)} chunks into hybrid '{settings.collection}'")
    seen = sorted({m["source"] for m in meta})
    print(f"Sources: {seen}")


if __name__ == "__main__":
    ingest()