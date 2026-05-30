from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.utils.rate_limit import limiter

router = APIRouter()


class MCPServerRegister(BaseModel):
    name: str
    endpoint: str
    api_key: str = ""


@router.post("/api/v1/mcp/register")
@limiter.limit("20/minute")  # type: ignore[untyped-decorator]
async def register_mcp_server(server: MCPServerRegister, request: Request) -> dict[str, Any]:
    from app.mcp.server import get_mcp_registry

    registry = get_mcp_registry()
    registry.register(server.name, server.endpoint, server.api_key)
    return {"status": "registered", "name": server.name}


@router.get("/api/v1/mcp/servers")
async def list_mcp_servers() -> dict[str, Any]:
    from app.mcp.server import get_mcp_registry

    return {"servers": get_mcp_registry().list_servers()}


@router.post("/api/v1/mcp/{server_name}/call/{tool_name}")
@limiter.limit("30/minute")  # type: ignore[untyped-decorator]
async def call_mcp_tool(
    server_name: str,
    tool_name: str,
    params: dict[str, Any] = {},
    request: Request = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    from app.mcp.server import get_mcp_registry

    result = await get_mcp_registry().call_tool(server_name, tool_name, params)
    return result
