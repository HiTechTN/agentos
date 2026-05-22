"""MCP (Model Context Protocol) integration for external tools."""

import httpx

from app.utils.logging import get_logger

logger = get_logger("mcp")


class MCPServer:
    def __init__(self, name: str, endpoint: str, api_key: str = ""):
        self.name = name
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.logger = get_logger(f"mcp_{name}")

    async def call_tool(self, tool_name: str, params: dict | None = None) -> dict:
        self.logger.log_action(
            "mcp", "call_tool", "started", details={"server": self.name, "tool": tool_name}
        )
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.endpoint}/call",
                    json={"tool": tool_name, "params": params or {}},
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            self.logger.log_error(
                "mcp", "call_tool", str(e), details={"server": self.name, "tool": tool_name}
            )
            return {"error": str(e)}

    async def list_tools(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.endpoint}/tools")
                resp.raise_for_status()
                data = resp.json()
                return data.get("tools", [])
        except Exception as e:
            self.logger.log_warn("mcp", "list_tools", str(e))
            return []


class MCPRegistry:
    def __init__(self):
        self.servers: dict[str, MCPServer] = {}

    def register(self, name: str, endpoint: str, api_key: str = ""):
        self.servers[name] = MCPServer(name, endpoint, api_key)
        logger.log_action(
            "mcp", "register", "completed", details={"name": name, "endpoint": endpoint}
        )

    def get(self, name: str) -> MCPServer | None:
        return self.servers.get(name)

    def unregister(self, name: str):
        if name in self.servers:
            del self.servers[name]
            logger.log_action("mcp", "unregister", "completed", details={"name": name})

    async def call_tool(self, server_name: str, tool_name: str, params: dict | None = None) -> dict:
        server = self.get(server_name)
        if not server:
            return {"error": f"MCP server '{server_name}' not found"}
        return await server.call_tool(tool_name, params)

    def list_servers(self) -> list[dict]:
        return [{"name": name, "endpoint": s.endpoint} for name, s in self.servers.items()]


_mcp_registry: MCPRegistry | None = None


def get_mcp_registry() -> MCPRegistry:
    global _mcp_registry
    if _mcp_registry is None:
        _mcp_registry = MCPRegistry()
    return _mcp_registry
