"""
stamp_classification.py
Adds sensitivity classification to the Olist datasets in DataHub:
  - Glossary: a 'Classification' node with 4 terms (PII, Confidential, Internal, Public)
  - Per-dataset: GlossaryTerms (formal classification) + GlobalTags (operational signals)
Idempotent: safe to re-run.
"""
import time
import datahub.emitter.mce_builder as builder
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    GlobalTagsClass, TagAssociationClass,
    GlossaryTermsClass, GlossaryTermAssociationClass,
    GlossaryTermInfoClass, GlossaryNodeInfoClass,
    AuditStampClass,
)

GMS = "http://localhost:8080"
PLATFORM = "snowflake"
ENV = "PROD"

emitter = DatahubRestEmitter(gms_server=GMS)
now = int(time.time() * 1000)
audit = AuditStampClass(time=now, actor="urn:li:corpuser:datahub")

# ---- 1. Glossary node + classification terms ----
NODE = "urn:li:glossaryNode:Classification"
LEVELS = {
    "PII":          "Personal data identifying an individual. GDPR-regulated.",
    "Confidential": "Sensitive business or financial data. Restricted access.",
    "Internal":     "Operational data for internal use only.",
    "Public":       "Non-sensitive data safe for open sharing.",
}

emitter.emit(MetadataChangeProposalWrapper(
    entityUrn=NODE,
    aspect=GlossaryNodeInfoClass(
        name="Classification",
        definition="Data sensitivity classification levels."),
))
for name, definition in LEVELS.items():
    emitter.emit(MetadataChangeProposalWrapper(
        entityUrn=builder.make_term_urn(f"Classification.{name}"),
        aspect=GlossaryTermInfoClass(
            name=name, definition=definition,
            termSource="INTERNAL", parentNode=NODE),
    ))

# ---- 2. Per-dataset classification map ----
MAP = {
    "PII": {
        "customers":     ["pii", "gdpr"],
        "raw_customers": ["pii", "gdpr"],
        "stg_customers": ["pii", "gdpr"],
        "raw_payments":  ["pii", "pci", "financial"],
    },
    "Confidential": {
        "fct_revenue":           ["financial"],
        "daily_revenue":         ["financial"],
        "fct_order_performance": ["financial"],
        "raw_sellers":           ["business-partner"],
        "stg_sellers":           ["business-partner"],
        "orders_cleaned":        ["financial"],
    },
    "Internal": {
        "raw_orders":      ["internal"],
        "stg_orders":      ["internal"],
        "raw_order_items": ["internal"],
        "dim_products":    ["internal"],
    },
    "Public": {
        "raw_products": ["public"],
        "stg_products": ["public"],
        "raw_reviews":  ["public"],
        "stg_reviews":  ["public"],
    },
}

for level, datasets in MAP.items():
    term_urn = builder.make_term_urn(f"Classification.{level}")
    for ds, tags in datasets.items():
        ds_urn = builder.make_dataset_urn(PLATFORM, ds, ENV)
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=ds_urn,
            aspect=GlossaryTermsClass(
                terms=[GlossaryTermAssociationClass(urn=term_urn)],
                auditStamp=audit),
        ))
        all_tags = list(dict.fromkeys([level.lower()] + tags))
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=ds_urn,
            aspect=GlobalTagsClass(
                tags=[TagAssociationClass(tag=builder.make_tag_urn(t)) for t in all_tags]),
        ))
        print(f"  {ds:22s} -> {level}  tags={all_tags}")

print("\nDone. Re-run the search query to verify.")