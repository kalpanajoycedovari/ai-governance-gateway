from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .datahub_mcp import client, enrich_asset

router = APIRouter(prefix="/mcp", tags=["datahub-mcp"])


class EnrichRequest(BaseModel):
    table: str
    action: str = "read"
    platform: Optional[str] = None


@router.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "mcp_ready": client.ready,
        "server": "mcp-server-datahub",
        "tool_count": len(client.tools),
        "tools": sorted(client.tools),
        "error": client.last_error,
    }


@router.get("/tools")
async def tools() -> Dict[str, Any]:
    """Exact input schemas, straight from the live MCP handshake."""
    if not client.ready:
        raise HTTPException(503, "MCP not running: " + str(client.last_error))
    return client.tools


@router.post("/enrich")
async def enrich_post(req: EnrichRequest) -> Dict[str, Any]:
    return await enrich_asset(req.table, req.action, req.platform)


@router.get("/enrich")
async def enrich_get(
    table: str = Query(...),
    action: str = Query("read"),
    platform: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """GET twin, so n8n on Windows can dodge the hanging-POST bug."""
    return await enrich_asset(table, action, platform)

@router.get("/raw")
async def raw_call(
    tool: str = Query(...),
    args_json: str = Query("{}"),
) -> Dict[str, Any]:
    """Call any MCP tool with raw JSON args and return the unmassaged result."""
    import json as _json

    if not client.ready:
        raise HTTPException(503, "MCP not running: " + str(client.last_error))
    try:
        args = _json.loads(args_json)
    except Exception as exc:
        raise HTTPException(400, "bad args_json: " + str(exc))
    result = await client.call(tool, args)
    return {"tool": tool, "args": args, "result": result}
