"""Hybrid retrieval for the policy knowledge base.

Two independent arms over the same corpus:
  - dense  : semantic nearest-neighbour search in Qdrant (bge-small-en-v1.5)
  - sparse : BM25 keyword scoring, built in-process from the Qdrant payloads

Results are combined with Reciprocal Rank Fusion. Dense search finds passages
that mean the same thing in different words; BM25 finds exact legal references
like "Article 5(1)(c)" that embeddings routinely blur. Regulation text needs
both, which is the whole argument for hybrid here.
"""

from __future__ import annotations

import hashlib
import re
import threading
from typing import Any, Dict, List, Optional

from rank_bm25 import BM25Okapi

from ..config import settings
from . import retrieve

# Standard RRF constant. Damps the influence of any single arm's top hit.
RRF_K = 60

# Depth pulled from each arm before fusion.
ARM_DEPTH = 25

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "in", "is", "it", "its", "of", "on", "or", "that", "the", "to", "was",
    "were", "will", "with", "this", "these", "those", "shall", "may",
}

_lock = threading.Lock()
_corpus: Optional[List[Dict[str, Any]]] = None
_bm25: Optional[BM25Okapi] = None
_index_error: Optional[str] = None


def _tokenize(text: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+(?:\([a-z0-9]+\))?", (text or "").lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 1]


def _key(payload: Dict[str, Any]) -> str:
    text = payload.get("text") or payload.get("document") or ""
    return hashlib.md5(text.encode("utf-8", "ignore")).hexdigest()


def _load_corpus() -> List[Dict[str, Any]]:
    """Read every chunk out of Qdrant once, so BM25 has something to index."""
    client = retrieve._c()
    docs: List[Dict[str, Any]] = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=settings.collection,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for p in points:
            pl = p.payload or {}
            text = pl.get("text") or pl.get("document") or ""
            if not text.strip():
                continue
            docs.append(
                {
                    "key": _key(pl),
                    "text": text,
                    "source": pl.get("source", pl.get("framework", "unknown")),
                    "framework": pl.get("framework"),
                    "ref": pl.get("ref"),
                    "title": pl.get("title"),
                }
            )
        if offset is None:
            break
    return docs


def _ensure_index() -> None:
    global _corpus, _bm25, _index_error
    if _bm25 is not None or _index_error is not None:
        return
    with _lock:
        if _bm25 is not None or _index_error is not None:
            return
        try:
            _corpus = _load_corpus()
            if not _corpus:
                _index_error = "corpus empty: nothing to index"
                return
            _bm25 = BM25Okapi([_tokenize(d["text"]) for d in _corpus])
        except Exception as exc:
            _index_error = repr(exc)


def index_status() -> Dict[str, Any]:
    _ensure_index()
    return {
        "bm25_ready": _bm25 is not None,
        "documents_indexed": len(_corpus) if _corpus else 0,
        "collection": settings.collection,
        "error": _index_error,
    }


def _sparse_arm(query: str, frameworks: Optional[List[str]]) -> List[Dict[str, Any]]:
    _ensure_index()
    if _bm25 is None or not _corpus:
        return []
    scores = _bm25.get_scores(_tokenize(query))
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    fw_set = set(frameworks) if frameworks else None
    out: List[Dict[str, Any]] = []
    for i in ranked:
        if scores[i] <= 0:
            break
        doc = _corpus[i]
        if fw_set and doc.get("framework") not in fw_set:
            continue
        out.append({**doc, "bm25_score": float(scores[i])})
        if len(out) >= ARM_DEPTH:
            break
    return out


def _dense_arm(query: str, frameworks: Optional[List[str]]) -> List[Dict[str, Any]]:
    resp = retrieve.search(query, k=ARM_DEPTH, frameworks=frameworks)
    out = []
    for r in resp.get("results", []):
        out.append({**r, "key": _key({"text": r.get("text", "")})})
    return out


def search(
    query: str,
    k: int = 4,
    frameworks: Optional[List[str]] = None,
    mode: str = "hybrid",
) -> Dict[str, Any]:
    """Retrieve policy passages. mode: hybrid | dense | sparse."""

    if mode == "dense":
        return {**retrieve.search(query, k, frameworks), "retrieval_mode": "dense"}

    dense = _dense_arm(query, frameworks) if mode in ("hybrid", "dense") else []
    sparse = _sparse_arm(query, frameworks) if mode in ("hybrid", "sparse") else []

    if not dense and not sparse:
        return {
            "results": [],
            "result": "(KB unavailable: both retrieval arms returned nothing)",
            "retrieval_mode": mode,
            "error": _index_error,
        }

    # Reciprocal Rank Fusion: a passage ranked well by either arm surfaces,
    # and one ranked well by both surfaces higher still.
    fused: Dict[str, Dict[str, Any]] = {}
    for arm_name, arm in (("dense", dense), ("sparse", sparse)):
        for rank, doc in enumerate(arm):
            key = doc["key"]
            entry = fused.setdefault(
                key, {**doc, "rrf_score": 0.0, "matched_by": []}
            )
            entry["rrf_score"] += 1.0 / (RRF_K + rank + 1)
            entry["matched_by"].append(arm_name)

    ordered = sorted(fused.values(), key=lambda d: d["rrf_score"], reverse=True)[:k]

    lines = [
        "[{}] {} {}".format(d.get("source"), d.get("ref") or "", d.get("text", "")).strip()
        for d in ordered
    ]
    return {
        "results": ordered,
        "result": "\n---\n".join(lines),
        "retrieval_mode": mode,
        "arms": {"dense": len(dense), "sparse": len(sparse)},
    }