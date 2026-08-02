from __future__ import annotations
from qdrant_client import QdrantClient
from fastembed import TextEmbedding
from ..config import settings

DENSE_MODEL = "BAAI/bge-small-en-v1.5"
DENSE_VECTOR_NAME = "fast-bge-small-en-v1.5"

_client = None
_embedder = None


def _c() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url,
                               api_key=settings.qdrant_api_key or None, timeout=60, prefer_grpc=False)
    return _client


def _embed(text: str) -> list[float]:
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(DENSE_MODEL)
    return list(_embedder.embed([text]))[0].tolist()


def search(query: str, k: int = 4, frameworks: list[str] | None = None) -> dict:
    """Pure dense search via query_points on the named dense vector.
    Framework filtering is done client-side. Avoids the .query() helper that
    panics (OutputTooSmall) on this Qdrant build."""
    try:
        fw_set = set(frameworks) if frameworks else None
        fetch = 50 if fw_set else k

        resp = _c().query_points(
            collection_name=settings.collection,
            query=_embed(query),
            using=DENSE_VECTOR_NAME,
            limit=fetch,
            with_payload=True,
        )

        results, lines = [], []
        for p in resp.points:
            pl = p.payload or {}
            if fw_set and pl.get("framework") not in fw_set:
                continue
            text = pl.get("text") or pl.get("document") or ""
            src = pl.get("source", pl.get("framework", "unknown"))
            results.append({
                "text": text,
                "source": src,
                "framework": pl.get("framework"),
                "ref": pl.get("ref"),
                "title": pl.get("title"),
                "score": getattr(p, "score", None),
            })
            lines.append(f"[{src}] {pl.get('ref', '')} {text}".strip())
            if len(results) >= k:
                break

        return {"results": results, "result": "\n---\n".join(lines)}
    except Exception as e:
        return {"results": [], "result": f"(KB unavailable: {e})", "error": str(e)}
