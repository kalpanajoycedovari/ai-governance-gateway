"""
stamp_classification_openbank.py
Adds sensitivity classification to the OpenBank (postgres) finance datasets in DataHub.
Reuses the same Classification glossary terms created by stamp_classification.py.
Idempotent: safe to re-run.
"""
import time
import datahub.emitter.mce_builder as builder
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    GlobalTagsClass, TagAssociationClass,
    GlossaryTermsClass, GlossaryTermAssociationClass,
    AuditStampClass,
)

GMS = "http://localhost:8080"
PLATFORM = "postgres"
ENV = "PROD"

emitter = DatahubRestEmitter(gms_server=GMS)
now = int(time.time() * 1000)
audit = AuditStampClass(time=now, actor="urn:li:corpuser:datahub")

# Full postgres dataset names (schema.table), mapped to classification + tags
MAP = {
    "PII": {
        "openbank.raw.transactions": ["pii", "gdpr", "financial"],
    },
    "Confidential": {
        "openbank.marts.fct_monthly_spending":        ["financial"],
        "openbank.marts.fct_savings_rate":            ["financial"],
        "openbank.marts.fct_cashflow_daily":          ["financial"],
        "openbank.marts.dim_recurring_subscriptions": ["financial"],
    },
    "Internal": {
        "openbank.marts.fct_category_trends":   ["internal"],
        "openbank.ml.cashflow_forecast":        ["internal"],
        "openbank.ml.transaction_categories":   ["internal"],
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
        print(f"  {ds:45s} -> {level}  tags={all_tags}")

print("\nDone. Check the tables in the DataHub UI to verify.")