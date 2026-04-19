"""
MCP HTTP Client Adapter.

Connects to a running MCP server via SSE/HTTP instead of spawning a subprocess.
This is the production-grade transport — avoids the per-request process overhead
that makes the stdio adapter unsuitable for concurrent workloads.

The MCP server must be running as a separate service (see docker-compose.yml)
before this client can connect.

Usage:
    async with MCPHTTPClientAdapter("http://mcp-server:8001") as client:
        tools = await client.list_tools()
        result = await client.call_tool("create_appointment", {...})
"""
import json
import logging
from typing import Any, Dict, List, Optional

from mcp import ClientSession
from mcp.client.sse import sse_client

from app.services.llm.base_provider import LLMToolDefinition

logger = logging.getLogger(__name__)


class MCPHTTPClientAdapter:
    """
    HTTP/SSE-based MCP client.

    Connects to an already-running MCP HTTP server. Unlike the stdio adapter,
    this does NOT spawn any subprocess — the server is a persistent microservice.

    Implements the same interface as MCPClientAdapter (stdio):
        - list_tools() -> List[LLMToolDefinition]
        - call_tool(name, args) -> dict
    """

    def __init__(self, server_url: str):
        """
        Args:
            server_url: Base URL of the MCP server, e.g. "http://mcp-server:8001".
                        The SSE endpoint is automatically appended as "/sse".
        """
        self._server_url = server_url.rstrip("/")
        self._sse_url = f"{self._server_url}/sse"
        self._session: Optional[ClientSession] = None
        self._exit_stack = None

    # ── Context manager ──────────────────────────────────────────────────────

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    # ── Connection management ─────────────────────────────────────────────────

    async def connect(self) -> None:
        """Establish an SSE connection to the MCP server."""
        from contextlib import AsyncExitStack

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        try:
            streams = await self._exit_stack.enter_async_context(
                sse_client(self._sse_url)
            )
            read_stream, write_stream = streams

            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await self._session.initialize()
            logger.info(
                "[MCP_HTTP] Connected to MCP server",
                extra={"url": self._server_url},
            )
        except Exception as exc:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._session = None
            raise ConnectionError(
                f"[MCP_HTTP] Could not connect to MCP server at {self._sse_url}: {exc}"
            ) from exc

    async def disconnect(self) -> None:
        """Close the SSE connection."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._session = None
            logger.info("[MCP_HTTP] Disconnected from MCP server")

    # ── Tool interface ────────────────────────────────────────────────────────

    async def list_tools(self) -> List[LLMToolDefinition]:
        """
        Discover available tools from the MCP server.
        Returns them in the unified LLMToolDefinition format.
        """
        if not self._session:
            raise RuntimeError(
                "MCP HTTP client not connected. Use 'async with' or call connect() first."
            )

        result = await self._session.list_tools()

        tool_defs = []
        for tool in result.tools:
            params = dict(tool.inputSchema) if tool.inputSchema else {}
            tool_defs.append(
                LLMToolDefinition(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=params,
                )
            )

        logger.info(
            "[MCP_HTTP] Tools discovered",
            extra={"count": len(tool_defs), "names": [t.name for t in tool_defs]},
        )
        return tool_defs

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool on the MCP server and return the result.

        Args:
            name:      Tool name (e.g. "get_available_appointment_slots")
            arguments: Tool arguments as a dict

        Returns:
            Dict with tool result (parsed from JSON content)
        """
        if not self._session:
            raise RuntimeError(
                "MCP HTTP client not connected. Use 'async with' or call connect() first."
            )

        logger.info(
            "[MCP_HTTP] Calling tool",
            extra={"tool": name, "args": arguments},
        )

        result = await self._session.call_tool(name, arguments)

        # Parse the result content
        if result.content:
            for content_item in result.content:
                if hasattr(content_item, "text"):
                    try:
                        return json.loads(content_item.text)
                    except json.JSONDecodeError:
                        return {"success": True, "result": content_item.text}

        if result.isError:
            return {"success": False, "error": "Tool execution failed"}

        return {"success": True, "result": None}
