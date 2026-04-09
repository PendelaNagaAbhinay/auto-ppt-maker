"""
MCP Manager — Starts MCP servers, discovers tools, and routes tool calls.

Usage:
    from client.mcp_manager import MCPManager

    manager = MCPManager()
    await manager.start()
    tools  = await manager.get_all_tools()
    result = await manager.call_tool("get_summary", {"topic": "water cycle"})
    await manager.stop()
"""

import asyncio
import os
import sys
from contextlib import AsyncExitStack
from datetime import datetime

from dotenv import dotenv_values
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ──────────────────────────────────────────────
# Project root & environment
# ──────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Load env vars from servers/.env so subprocesses get API keys
_env_file = os.path.join(PROJECT_ROOT, "servers", ".env")
_dotenv_vars = dotenv_values(_env_file) if os.path.exists(_env_file) else {}
SERVER_ENV = {**os.environ, **_dotenv_vars}


def _log(msg: str) -> None:
    """Timestamped debug log."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[MCPManager {ts}] {msg}")


# ──────────────────────────────────────────────
# Server definitions
# ──────────────────────────────────────────────
SERVERS = [
    {"name": "pptx",      "command": sys.executable, "args": [os.path.join(PROJECT_ROOT, "servers", "pptx_mcp", "server.py")]},
    {"name": "wikipedia", "command": sys.executable, "args": [os.path.join(PROJECT_ROOT, "servers", "wikipedia_mcp", "server.py")]},
    {"name": "images",    "command": sys.executable, "args": [os.path.join(PROJECT_ROOT, "servers", "image_fetch_mcp", "server.py")]},
]


class MCPManager:
    """Manages MCP server lifecycles, tool discovery, and tool-call routing."""

    def __init__(self):
        self.sessions: dict[str, ClientSession] = {}          # server_name -> session
        self.tool_registry: dict[str, tuple] = {}             # tool_name  -> (session, tool_schema)
        self._exit_stack: AsyncExitStack | None = None        # keeps contexts alive

    # ──────────────────────────────────────────
    # 1.  start()
    # ──────────────────────────────────────────
    async def start(self):
        """Start every MCP server, connect via stdio, and discover tools."""
        _log(f"Starting MCP servers (project root: {PROJECT_ROOT})")
        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        for server_cfg in SERVERS:
            name = server_cfg["name"]
            try:
                # Build transport parameters
                _log(f"Launching server '{name}': {server_cfg['args']}")
                server_params = StdioServerParameters(
                    command=server_cfg["command"],
                    args=server_cfg["args"],
                    env=SERVER_ENV,
                )

                # Open stdio transport  (context kept alive by exit_stack)
                stdio_transport = stdio_client(server_params)
                read_stream, write_stream = await self._exit_stack.enter_async_context(
                    stdio_transport
                )

                # Create and initialise the MCP session
                session = await self._exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await session.initialize()

                self.sessions[name] = session
                _log(f"Connected to {name}")

                # Discover tools exposed by this server
                tools_result = await session.list_tools()
                if tools_result and tools_result.tools:
                    for tool in tools_result.tools:
                        self.tool_registry[tool.name] = (session, tool)
                        _log(f"  Registered tool: {tool.name} (from {name})")

            except Exception as exc:
                _log(f"ERROR starting server '{name}': {exc}")

        _log(f"Startup complete: {len(self.sessions)} servers, {len(self.tool_registry)} tools")

    # ──────────────────────────────────────────
    # 2.  get_all_tools()
    # ──────────────────────────────────────────
    async def get_all_tools(self) -> list[dict]:
        """Return every registered tool in OpenAI function-calling format."""
        tools_list: list[dict] = []
        for tool_name, (_session, tool_schema) in self.tool_registry.items():
            tools_list.append({
                "type": "function",
                "function": {
                    "name": tool_schema.name,
                    "description": tool_schema.description or "",
                    "parameters": tool_schema.inputSchema if tool_schema.inputSchema else {},
                },
            })
        return tools_list

    # ──────────────────────────────────────────
    # 3.  call_tool()
    # ──────────────────────────────────────────
    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Route a tool call to the correct MCP session and return the result as a string."""
        if tool_name not in self.tool_registry:
            _log(f"Tool not found: {tool_name}")
            return f"ERROR: Tool not found: {tool_name}"

        session, _schema = self.tool_registry[tool_name]
        _log(f"Calling {tool_name} with {arguments}")

        try:
            result = await session.call_tool(tool_name, arguments)
            # result.content is a list of content blocks; concatenate their text
            parts: list[str] = []
            if result.content:
                for block in result.content:
                    if hasattr(block, "text"):
                        parts.append(block.text)
                    else:
                        parts.append(str(block))
            response = "\n".join(parts) if parts else "(empty response)"
            _log(f"Tool {tool_name} returned {len(response)} chars")
            return response
        except Exception as exc:
            _log(f"ERROR calling {tool_name}: {exc}")
            return f"ERROR: {exc}"

    # ──────────────────────────────────────────
    # 4.  stop()
    # ──────────────────────────────────────────
    async def stop(self):
        """Close all sessions and terminate server sub-processes cleanly."""
        try:
            if self._exit_stack:
                await self._exit_stack.aclose()
                _log("All MCP servers stopped.")
        except Exception as exc:
            _log(f"Warning during shutdown: {exc}")
        finally:
            self.sessions.clear()
            self.tool_registry.clear()
            self._exit_stack = None


# ──────────────────────────────────────────────
# Quick smoke-test
# ──────────────────────────────────────────────
async def test_mcp():
    manager = MCPManager()
    await manager.start()

    tools = await manager.get_all_tools()
    print("\nAvailable tools:", [t["function"]["name"] for t in tools])

    result = await manager.call_tool(
        "get_summary",
        {"topic": "water cycle"},
    )
    print("Test result:", result)

    await manager.stop()


if __name__ == "__main__":
    asyncio.run(test_mcp())
