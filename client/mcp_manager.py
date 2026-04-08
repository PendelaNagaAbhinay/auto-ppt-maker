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
import sys
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ──────────────────────────────────────────────
# Server definitions
# ──────────────────────────────────────────────
SERVERS = [
    {"name": "pptx",      "command": sys.executable, "args": ["servers/pptx_mcp/server.py"]},
    {"name": "wikipedia", "command": sys.executable, "args": ["servers/wikipedia_mcp/server.py"]},
    {"name": "images",    "command": sys.executable, "args": ["servers/image_fetch_mcp/server.py"]},
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
        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        for server_cfg in SERVERS:
            name = server_cfg["name"]
            try:
                # Build transport parameters
                server_params = StdioServerParameters(
                    command=server_cfg["command"],
                    args=server_cfg["args"],
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
                print(f"Connected to {name}")

                # Discover tools exposed by this server
                tools_result = await session.list_tools()
                if tools_result and tools_result.tools:
                    for tool in tools_result.tools:
                        self.tool_registry[tool.name] = (session, tool)
                        print(f"  Registered tool: {tool.name}")

            except Exception as exc:
                print(f"ERROR starting server '{name}': {exc}")

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
            return f"ERROR: Tool not found: {tool_name}"

        session, _schema = self.tool_registry[tool_name]
        print(f"Calling {tool_name} with {arguments}")

        try:
            result = await session.call_tool(tool_name, arguments)
            # result.content is a list of content blocks; concatenate their text
            parts: list[str] = []
            for block in result.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
                else:
                    parts.append(str(block))
            return "\n".join(parts)
        except Exception as exc:
            return f"ERROR: {exc}"

    # ──────────────────────────────────────────
    # 4.  stop()
    # ──────────────────────────────────────────
    async def stop(self):
        """Close all sessions and terminate server sub-processes cleanly."""
        try:
            if self._exit_stack:
                await self._exit_stack.aclose()
                print("All MCP servers stopped.")
        except Exception as exc:
            print(f"Warning during shutdown: {exc}")
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
