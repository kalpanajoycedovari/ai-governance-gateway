"""Embedded regulatory corpus for cloud ingestion.

The deployed container has no source files, so the knowledge base text lives
here as Python strings. Each entry is (source_tag, body). ingest_from_sources()
builds the same hybrid (dense + BM25) collection the file-based ingest produces.

This is a working summary for retrieval, not legal advice.
"""
from __future__ import annotations

from qdrant_client import QdrantClient

from ..config import settings

DENSE_MODEL = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL = "Qdrant/bm25"

EU_OBLIGATIONS = """# EU AI Act obligations mapped to system checks (summary for the KB)
## Article 9 - Risk management
Providers must run a continuous risk management process across the system lifecycle. The risk classifier agent assigns each decision a tier.
## Article 10 - Data and data governance
Training and operational data must be relevant and free of prejudice that leads to discrimination. The bias agent reviews outputs; the PII check guards personal data in stored outputs.
## Article 12 - Record-keeping
High-risk systems must automatically log events over their lifetime. The log-completeness and retention checks enforce complete, timestamped, retained records.
## Article 13 - Transparency
Users must be informed they are interacting with an AI system. The disclosure check enforces this.
## Article 14 - Human oversight
High-risk systems must allow effective human oversight. The oversight check requires a review or escalation step for high-risk decisions.
## Article 15 - Accuracy and robustness
Systems must meet an appropriate level of accuracy. The confidence-threshold check flags low-confidence autonomous decisions.
Note: this is a working summary for retrieval, not legal advice."""

EU_ANNEX_III = """# EU AI Act Annex III - High-Risk AI System Categories (Article 6(2))
An AI system is high-risk if it falls into one of the eight Annex III areas below and is not caught by the Article 6(3) exception. Article 6(3) is a narrow carve-out: a listed system is not high-risk if it does not pose a significant risk of harm to health, safety or fundamental rights. Systems that profile natural persons always remain high-risk.
## 1. Biometrics
Remote biometric identification; biometric categorisation by sensitive attributes; emotion recognition. Excludes simple verification such as unlocking a device.
## 2. Critical infrastructure
AI as a safety component in critical digital infrastructure, road traffic, or supply of water, gas, heating and electricity.
## 3. Education and vocational training
Admissions or assignment; evaluating learning outcomes; assessing level of education; detecting prohibited behaviour during tests.
## 4. Employment, workers management and access to self-employment
Recruitment, screening, filtering, ranking or evaluating candidates; decisions on promotion, termination, task allocation, or performance monitoring.
## 5. Access to essential private and public services
Evaluating eligibility for public assistance benefits; creditworthiness assessment and credit scoring (excluding fraud detection); risk assessment and pricing in life and health insurance; dispatching emergency services. Credit and loan approval decisions fall here.
## 6. Law enforcement
Assessing risk of offending or re-offending, or of becoming a victim; polygraphs; evaluating evidence reliability; profiling in detection, investigation or prosecution.
## 7. Migration, asylum and border control
Polygraphs; assessing risks of a person entering a territory; examining asylum, visa and residence applications; identifying persons in migration contexts.
## 8. Administration of justice and democratic processes
Assisting a judicial authority in researching and applying facts and law; influencing the outcome of an election or referendum or voting behaviour.
Note: this is a working summary for retrieval, not legal advice."""

UK_REGULATION = """# UK AI Regulation - Sector Regulator Obligations (2026)
The UK has no single AI Act. AI is governed by existing laws applied by sector regulators. A UK deployer must map against several regimes at once.
## Data protection and automated decisions (ICO)
Under UK GDPR as amended by the Data (Use and Access) Act 2025, Articles 22A to 22D (in force 5 February 2026) govern significant solely automated decisions about individuals. Such decisions are permitted only where safeguards are documented: meaningful transparency, the ability to obtain human review, and the right to contest. This regime maps to the disclosure, human-oversight and record-keeping checks.
## Financial services (FCA)
No standalone AI rulebook. AI in financial services is governed by the Consumer Duty (PRIN 2A) requiring good outcomes and avoidance of foreseeable harm; SM&CR senior-manager accountability; SYSC 8 outsourcing rules; and operational resilience. Credit, loan and insurance decisions made with AI fall within Consumer Duty fair-treatment expectations.
## Online services and telecoms (Ofcom)
Under the Online Safety Act 2023, user-facing services face duties for illegal content including AI-generated synthetic content. Under the Telecoms Security Act 2021, AI in networks sits inside the security duty.
## Cross-sector principles (DSIT)
The 2023 pro-innovation white paper set five principles applied by all regulators: safety and robustness; transparency and explainability; fairness; accountability and governance; and contestability and redress.
## Extraterritorial note
A UK organisation whose AI outputs affect people in the EU may also be caught by the EU AI Act.
Note: this is a working summary for retrieval, not legal advice."""

COMPANY_POLICY = """# Company AI Use Policy (sample)
- All customer-facing AI interactions must disclose that the user is speaking with an automated system.
- High-risk decisions (credit, employment, access to services) require documented human review before they take effect.
- No personal data (email, phone, payment details) may appear in a stored agent output.
- Minimum acceptable confidence for an autonomous decision is 0.60. Below this, escalate.
- All decision records are retained for 365 days and must be complete and timestamped."""

SOURCES: list[tuple[str, str]] = [
    ("EU AI Act", EU_OBLIGATIONS),
    ("EU AI Act", EU_ANNEX_III),
    ("UK", UK_REGULATION),
    ("Company Policy", COMPANY_POLICY),
]


def _chunk(text: str, size: int = 600, overlap: int = 80) -> list[str]:
    words = text.split()
    step = max(size - overlap, 1)
    chunks = [" ".join(words[j:j + size]) for j in range(0, len(words), step)]
    return chunks or [text]


def ingest_from_sources() -> dict:
    """Rebuild the hybrid KB from the embedded corpus. Returns a summary dict."""
    client = QdrantClient(url=settings.qdrant_url,
                          api_key=settings.qdrant_api_key or None)
    client.set_model(DENSE_MODEL)
    client.set_sparse_model(SPARSE_MODEL)

    if client.collection_exists(settings.collection):
        client.delete_collection(settings.collection)
    client.create_collection(
        collection_name=settings.collection,
        vectors_config=client.get_fastembed_vector_params(),
        sparse_vectors_config=client.get_fastembed_sparse_vector_params(),
    )

    docs, ids, meta = [], [], []
    idx = 0
    for tag, body in SOURCES:
        for chunk in _chunk(body):
            docs.append(chunk)
            ids.append(idx)
            meta.append({"source": tag})
            idx += 1

    client.add(collection_name=settings.collection, documents=docs, ids=ids, metadata=meta)
    seen = sorted({m["source"] for m in meta})
    return {"ingested": len(docs), "sources": seen, "collection": settings.collection}
