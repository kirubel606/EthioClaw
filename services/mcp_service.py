import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.client.sse import sse_client

class MCPManager:
    def __init__(self, config_path: str = "mcp_config.json"):
        self.config_path = config_path
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stack = None
        self._lock = asyncio.Lock()

    async def _load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            return {"mcpServers": {}}
        with open(self.config_path, "r") as f:
            return json.load(f)

    async def start_servers(self):
        config = await self._load_config()
        servers = config.get("mcpServers", {})
        
        for name, server_config in servers.items():
            if "url" in server_config:
                url = server_config["url"]
                asyncio.create_task(self._connect_to_sse_server(name, url))
            elif "command" in server_config:
                command = server_config.get("command")
                args = server_config.get("args", [])
                env = server_config.get("env")
                
                params = StdioServerParameters(
                    command=command,
                    args=args,
                    env=env if env else os.environ.copy()
                )
                
                asyncio.create_task(self._connect_to_stdio_server(name, params))

    async def _connect_to_stdio_server(self, name: str, params: StdioServerParameters):
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    async with self._lock:
                        self.sessions[name] = session
                    print(f"[MCP] Connected to stdio server: {name}")
                    while True:
                        await asyncio.sleep(1)
        except Exception as e:
            print(f"[MCP] Error connecting to stdio server {name}: {e}")
            async with self._lock:
                if name in self.sessions:
                    del self.sessions[name]

    async def _connect_to_sse_server(self, name: str, url: str):
        try:
            async with sse_client(url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    async with self._lock:
                        self.sessions[name] = session
                    print(f"[MCP] Connected to SSE server: {name} ({url})")
                    while True:
                        await asyncio.sleep(1)
        except Exception as e:
            print(f"[MCP] Error connecting to SSE server {name}: {e}")
            async with self._lock:
                if name in self.sessions:
                    del self.sessions[name]

    async def list_tools(self) -> List[Dict[str, Any]]:
        all_tools = []
        async with self._lock:
            for name, session in self.sessions.items():
                try:
                    tools_result = await session.list_tools()
                    for tool in tools_result.tools:
                        all_tools.append({
                            "server": name,
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.inputSchema
                        })
                except Exception as e:
                    print(f"[MCP] Error listing tools for {name}: {e}")
        return all_tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        async with self._lock:
            session = self.sessions.get(server_name)
            if not session:
                return f"Error: MCP server '{server_name}' not found or not connected."
            
            try:
                result = await session.call_tool(tool_name, arguments)
                # MCP tool results can be complex (content list)
                texts = []
                for content in result.content:
                    if hasattr(content, 'text'):
                        texts.append(content.text)
                    elif isinstance(content, dict) and 'text' in content:
                        texts.append(content['text'])
                return "\n".join(texts)
            except Exception as e:
                return f"Error calling tool '{tool_name}' on '{server_name}': {e}"

# Singleton instance
mcp_manager = MCPManager()
