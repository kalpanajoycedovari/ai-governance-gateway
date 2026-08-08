"""DataHub MCP client for the AI Governance Gateway.

Metadata enrichment goes through the official open-source DataHub MCP
server (mcp-server-datahub) rather than raw GraphQL. MCP supplies facts;
the deterministic policy engine supplies the verdict.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

log = logging.getLogger("datahub_mcp")

class DataHubMCPToolError(RuntimeError):
    """An MCP tool returned an error payload instead of data."""

DATAHUB_GMS_URL = os.getenv("DATAHUB_GMS_URL", "http://localhost:8080")
DATAHUB_GMS_TOKEN = os.getenv("DATAHUB_GMS_TOKEN", "")
UVX_COMMAND = os.getenv("UVX_COMMAND", "uvx")

DESTRUCTIVE = {"delete", "drop", "truncate", "export", "deploy"}

# DataHub stores these lowercase; the policy engine reads canonical form.
TAG_CANONICAL = {
    "pii": "PII",
    "confidential": "Confidential",
    "internal": "Internal",
    "public": "Public",
    "gdpr": "GDPR",
    "pci": "PCI",
    "financial": "Financial",
    "business-partner": "BusinessPartner",
}


class DataHubMCPClient:
    """One long-lived stdio session, shared across requests."""

    def __init__(self) -> None:
        self._stack: Optional[AsyncExitStack] = None
        self._session: Optional[ClientSession] = None
        self._lock = asyncio.Lock()
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.ready = False
        self.last_error: Optional[str] = None

    async def start(self) -> None:
        env = dict(os.environ)
        env["DATAHUB_GMS_URL"] = DATAHUB_GMS_URL
        if DATAHUB_GMS_TOKEN:
            env["DATAHUB_GMS_TOKEN"] = DATAHUB_GMS_TOKEN

        params = StdioServerParameters(
            command=UVX_COMMAND,
            args=["mcp-server-datahub@latest"],
            env=env,
        )
        try:
            self._stack = AsyncExitStack()
            read, write = await self._stack.enter_async_context(stdio_client(params))
            self._session = await self._stack.enter_async_context(
                ClientSession(read, write)
            )
            await self._session.initialize()
            listed = await self._session.list_tools()
            self.tools = {t.name: (t.inputSchema or {}) for t in listed.tools}
            self.ready = True
            self.last_error = None
            log.info("DataHub MCP ready. Tools: %s", sorted(self.tools))
        except Exception as exc:
            self.last_error = repr(exc)
            self.ready = False
            log.exception("DataHub MCP failed to start")

    async def stop(self) -> None:
        self.ready = False
        if self._stack is not None:
            try:
                await self._stack.aclose()
            except Exception:
                log.warning("MCP shutdown was not clean", exc_info=True)
        self._stack = None
        self._session = None

    async def call(self, tool: str, args: Dict[str, Any]) -> Any:
        if not self.ready or self._session is None:
            raise RuntimeError("DataHub MCP not running: " + str(self.last_error))
        async with self._lock:
            result = await self._session.call_tool(tool, args)
        payload = _unwrap(result)
        if getattr(result, "isError", False):
            raise DataHubMCPToolError(str(payload)[:400])
        if isinstance(payload, str) and "validation error for call[" in payload:
            raise DataHubMCPToolError(payload[:400])
        return payload


def _unwrap(result: Any) -> Any:
    chunks: List[str] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            chunks.append(text)
    raw = "\n".join(chunks).strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _walk(node: Any):
    """Yield every scalar in an arbitrarily nested MCP response."""
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
        else:
            yield current


def _urns(payload: Any, kind: str) -> List[str]:
    prefix = "urn:li:" + kind + ":"
    seen: List[str] = []
    for value in _walk(payload):
        if isinstance(value, str) and value.startswith(prefix) and value not in seen:
            seen.append(value)
    return seen


def _tag_names(payload: Any) -> List[str]:
    out: List[str] = []
    for urn in _urns(payload, "tag"):
        raw = urn.split("urn:li:tag:", 1)[-1].strip("()").lower()
        name = TAG_CANONICAL.get(raw, raw)
        if name not in out:
            out.append(name)
    return out


def _term_names(payload: Any) -> List[str]:
    out: List[str] = []
    for urn in _urns(payload, "glossaryTerm"):
        name = urn.split("urn:li:glossaryTerm:", 1)[-1].strip("()")
        if name not in out:
            out.append(name)
    return out


def _owner_names(payload: Any) -> List[str]:
    out: List[str] = []
    for urn in _urns(payload, "corpuser"):
        name = urn.split("urn:li:corpuser:", 1)[-1].strip("()")
        if name and name not in out:
            out.append(name)
    return out


def _classification(terms: List[str]) -> Optional[str]:
    for term in terms:
        if term.startswith("Classification."):
            return term.split(".", 1)[1]
    return None


client = DataHubMCPClient()


async def enrich_asset(
    table: str,
    action: str = "read",
    platform: Optional[str] = None,
) -> Dict[str, Any]:
    """Return the DataHub facts the policy engine needs. No decisions here."""

    facts: Dict[str, Any] = {
        "table": table,
        "action": action,
        "source": "datahub-mcp-server",
        "tools_used": [],
        "urn": None,
        "tags": [],
        "glossary_terms": [],
        "owner": None,
        "owners": [],
        "classification": None,
        "downstream_count": 0,
        "downstream_urns": [],
        "metadata_found": False,
        "errors": [],
    }

    search_args: Dict[str, Any] = {"query": table, "num_results": 10}
    if platform:
        search_args["filter"] = "platform = " + platform

    try:
        hits = await client.call("search", search_args)
        facts["tools_used"].append("search")
    except Exception as exc:
        facts["errors"].append("search: " + str(exc))
        return facts

    candidates = _urns(hits, "dataset")
    if not candidates:
        return facts

    # Prefer an exact table-name match over the top-scoring fuzzy hit.
    needle = "," + table.lower() + ","
    urn = next((u for u in candidates if needle in u.lower()), candidates[0])

    facts["urn"] = urn
    facts["metadata_found"] = True

    try:
        entity = await client.call("get_entities", {"urns": [urn]})
        facts["tools_used"].append("get_entities")
        facts["tags"] = _tag_names(entity)
        facts["glossary_terms"] = _term_names(entity)
        owners = _owner_names(entity)
        facts["owners"] = owners
        facts["owner"] = owners[0] if owners else None
        facts["classification"] = _classification(facts["glossary_terms"])
    except Exception as exc:
        facts["errors"].append("get_entities: " + str(exc))

    if action.lower() in DESTRUCTIVE:
        try:
            lineage = await client.call(
                "get_lineage",
                {"urn": urn, "upstream": False, "max_hops": 2, "max_results": 30},
            )
            facts["tools_used"].append("get_lineage")
            downstream = [u for u in _urns(lineage, "dataset") if u != urn]
            facts["downstream_urns"] = downstream
            facts["downstream_count"] = len(downstream)
        except Exception as exc:
            facts["errors"].append("get_lineage: " + str(exc))

    return facts