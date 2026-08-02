"""LLM fact extraction via Groq. The model's ENTIRE job: turn a raw request
into the action fields of ActionFacts. It never sets identity (actor_id /
actor_role come from the authenticated caller) and it never returns a verdict.

Pydantic validation is the guard rail: a hallucinated field or out-of-vocabulary
enum raises, and the caller fails closed to human review.
"""
from __future__ import annotations
import os
import json
from groq import Groq
from schemas import (ActionFacts, ActionType, Scope, Sensitivity,
                     Environment, ActorRole)

MODEL = "llama-3.3-70b-versatile"


def _vocab(enum_cls) -> str:
    return ", ".join(e.value for e in enum_cls)


FACT_EXTRACTION_PROMPT = f"""You are a fact extractor for an AI governance gateway.
Read the user's request and output ONLY a JSON object describing the action.
You do NOT decide whether it is allowed. You do NOT assign identity or roles.

Output exactly these keys:
  action_type          one of: {_vocab(ActionType)}
  resource             short human name of the thing being acted on (string)
  resource_sensitivity one of: {_vocab(Sensitivity)}
  data_categories      list of strings from: pii, financial, health, credentials, secrets, internal, public
  scope                one of: {_vocab(Scope)}   (single item, bulk many, all everything)
  reversible           boolean, true if the action can be undone
  environment          one of: {_vocab(Environment)}
  extraction_confidence number 0.0 to 1.0, how confident you are in THIS extraction

Rules:
- Choose the closest allowed value. Never invent values outside the lists.
- If data categories are unclear, use ["internal"]. If clearly none, use ["public"].
- Deletions, purges, and overwrites are usually reversible=false.
- Output raw JSON only. No markdown, no code fences, no commentary."""


_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY is not set in the environment")
        _client = Groq(api_key=key)
    return _client


def extract_facts(request_text: str, actor_id: str,
                  actor_role: str = "developer") -> ActionFacts:
    """Extract structured facts from a raw request. Fails closed on bad output."""
    client = _get_client()
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": FACT_EXTRACTION_PROMPT},
            {"role": "user", "content": request_text},
        ],
    )
    content = resp.choices[0].message.content or ""
    content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    data = json.loads(content)  # raises on non-JSON -> caller fails closed

    # Identity is trusted from the caller, NEVER from the model.
    data["actor_id"] = actor_id
    data["actor_role"] = actor_role
    data["raw_request"] = request_text

    return ActionFacts.model_validate(data)  # raises on bad enum/field -> fail closed


if __name__ == "__main__":
    from engine import GovernanceEngine
    sample = ("The finance agent wants to permanently delete every customer "
              "billing record from the production database.")
    facts = extract_facts(sample, actor_id="agent_finance_02", actor_role="finance_agent")
    print("EXTRACTED FACTS")
    print(facts.model_dump_json(indent=2))
    print()
    print(GovernanceEngine().evaluate(facts).explain())