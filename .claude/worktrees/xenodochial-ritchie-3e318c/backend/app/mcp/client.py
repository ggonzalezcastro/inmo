"""
MCP Client Adapter — transport-aware.

Selects the appropriate MCP transport based on configuration:

  MCP_TRANSPORT=http  (recommended, production)
    → MCPHTTPClientAdapter: connects to the standalone MCP HTTP microservice.
      No subprocess spawning. Fully concurrent. Requires the mcp-server
      docker-compose service to be running.

  MCP_TRANSPORT=stdio (fallback, development / legacy)
    → Shared stdio subprocess via _StdioSharedSession singleton.
      Spawns ONE subprocess at first use and reuses it for all requests,
      serialising access with an asyncio.Lock.
      Avoids the per-request subprocess-per-request problem of the old design.

Usage (same interface in both modes):
    async with MCPClientAdapter() as client:
        tools = await client.list_tools()
        result = await client.call_tool("create_appointment", {...})
"""
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.llm.base_provider import LLMToolDefinition

logger = logging.getLogger(__name__)

# Path to the MCP server module (for stdio mode)
_SERVER_MODULE = "app.mcp.server"
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent.parent)


# ---------------------------------------------------------------------------
# Stdio singleton — one shared subprocess, serialised via asyncio.Lock
# ---------------------------------------------------------------------------

class _StdioSharedSession:
    """
    Manages a single long-lived stdio MCP subprocess shared across all requests.

    This solves the per-request subprocess spawning issue while keeping backward
    compatibility with stdio transport in development environments.

    Thread-safety: asyncio.Lock serialises concurrent tool calls.
    """

    _instance: Optional["_StdioSharedSession"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self):
        self._session = None
        self._exit_stack = None
        self._call_lock = asyncio.Lock()

    @classmethod
    async def get(cls) -> "_StdioSharedSession":
        """Return (or lazily create) the singleton session."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    instance = cls()
                    await instance._start()
                    cls._instance = instance
        return cls._instance

    @classmethod
    async def reset(cls) -> None:
        """Tear down the singleton (useful for tests or graceful shutdown)."""
        async with cls._lock:
            if cls._instance is not None:
                await cls._instance._stop()
                cls._instance = None

    async def _start(self) -> None:
        from contextlib import AsyncExitStack
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", _SERVER_MODULE],
            env={"MCP_TRANSPORT": "stdio"},
            cwd=_BACKEND_DIR,
        )

        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = stdio_transport

        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self._session.initialize()
        logger.info("[MCP_STDIO] Shared subprocess started")

    async def _stop(self) -> None:
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._session = None
            logger.info("[MCP_STDIO] Shared subprocess stopped")

    async def list_tools(self) -> List[LLMToolDefinition]:
        async with self._call_lock:
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
                "[MCP_STDIO] Tools discovered",
                extra={"count": len(tool_defs)},
            )
            return tool_defs

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        async with self._call_lock:
            logger.info("[MCP_STDIO] Calling tool", extra={"tool": name})
            result = await self._session.call_tool(name, arguments)

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


# ---------------------------------------------------------------------------
# Public adapter — auto-selects transport
# ---------------------------------------------------------------------------

class MCPClientAdapter:
    """
    Transport-aware MCP client adapter.

    Selects HTTP or stdio transport based on settings.MCP_TRANSPORT:
      - "http"  → MCPHTTPClientAdapter (production, no subprocess)
      - "stdio" → _StdioSharedSession singleton (dev, one subprocess total)

    Interface is identical regardless of transport:
        async with MCPClientAdapter() as client:
            tools = await client.list_tools()
            result = await client.call_tool("name", {...})
    """

    def __init__(self):
        self._delegate = None
        self._is_http = False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    async def connect(self) -> None:
        from app.config import settings

        transport = getattr(settings, "MCP_TRANSPORT", "http").lower()

        if transport == "http":
            from app.mcp.http_client import MCPHTTPClientAdapter
            server_url = getattr(settings, "MCP_SERVER_URL", "http://localhost:8001")
            self._delegate = MCPHTTPClientAdapter(server_url)
            await self._delegate.connect()
            self._is_http = True
            logger.info(
                "[MCP] Using HTTP transport",
                extra={"url": server_url},
            )
        else:
            # Stdio singleton — no connect() needed (lazy-started on first call)
            self._delegate = await _StdioSharedSession.get()
            self._is_http = False
            logger.debug("[MCP] Using stdio transport (shared singleton)")

    async def disconnect(self) -> None:
        # Only disconnect HTTP adapters — stdio singleton lives for the process lifetime
        if self._is_http and self._delegate is not None:
            await self._delegate.disconnect()
        self._delegate = None

    async def list_tools(self) -> List[LLMToolDefinition]:
        if self._delegate is None:
            raise RuntimeError("MCPClientAdapter not connected.")
        return await self._delegate.list_tools()

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if self._delegate is None:
            raise RuntimeError("MCPClientAdapter not connected.")
        return await self._delegate.call_tool(name, arguments)
