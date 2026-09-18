"""Generic OpenAI-compatible chat client for the DevLog MCP server.

Spawns server.py as a subprocess and speaks MCP to it over stdio, while
talking to any OpenAI-compatible chat-completions endpoint (llama.cpp's
llama-server, Ollama, vLLM, or OpenAI's own API) over HTTP via httpx. The
server never knows which backend is on the other end; this script is the
only thing that needs to change to swap backends.

Usage:
    # local llama.cpp server (llama-server --jinja ...)
    python client.py --base-url http://127.0.0.1:8080/v1 --model qwen2.5-instruct

    # OpenAI's actual API
    python client.py --base-url https://api.openai.com/v1 --model gpt-4o --api-key sk-...
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from mcp import types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

SERVER_PATH = Path(__file__).parent / "server.py"


def to_openai_tools(tools: list[types.Tool]) -> list[dict]:
    """Convert MCP tool definitions into OpenAI-style function-calling schemas."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            },
        }
        for tool in tools
    ]


async def call_mcp_tool(session: ClientSession, name: str, arguments: dict) -> str:
    """Invoke an MCP tool and flatten its result content into plain text."""
    result = await session.call_tool(name, arguments)
    texts = [
        block.text for block in result.content if isinstance(block, types.TextContent)
    ]
    return "\n".join(texts) if texts else "(tool returned no text content)"


async def chat_round(
    http_client: httpx.AsyncClient,
    session: ClientSession,
    base_url: str,
    model: str,
    messages: list[dict],
    tools: list[dict],
) -> None:
    """Run one user turn to completion, executing tool calls until the model answers."""
    while True:
        response = await http_client.post(
            f"{base_url}/chat/completions",
            json={"model": model, "messages": messages, "tools": tools},
        )
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            print(f"assistant> {message.get('content', '')}")
            return

        for call in tool_calls:
            name = call["function"]["name"]
            arguments = json.loads(call["function"]["arguments"] or "{}")
            print(f"  [calling {name}({arguments})]")
            try:
                result_text = await call_mcp_tool(session, name, arguments)
            except Exception as exc:
                result_text = f"Error calling {name}: {exc}"
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result_text,
                }
            )


async def repl(
    http_client: httpx.AsyncClient,
    session: ClientSession,
    base_url: str,
    model: str,
    tools: list[dict],
    system_prompt: str | None,
) -> None:
    """Read user input from the terminal and drive chat_round until exit/quit."""
    messages = [{"role": "system", "content": system_prompt}] if system_prompt else []
    print(
        f"Connected. {len(tools)} DevLog tools available. "
        "Type 'tools' to see available tools. Type 'exit' to quit."
    )
    while True:
        try:
            user_input = input("you> ").strip()
        except EOFError:
            break
        if not user_input:
            continue
        if user_input in ("exit", "quit"):
            break
        if user_input == "tools":
            for tool in tools:
                function = tool["function"]
                print(f"  {function['name']}: {function['description']}")
            continue
        messages.append({"role": "user", "content": user_input})
        await chat_round(http_client, session, base_url, model, messages, tools)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("DEVLOG_LLM_BASE_URL", "http://127.0.0.1:8080/v1"),
        help="OpenAI-compatible base URL (default: local llama.cpp server)",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Model name as the backend expects it, e.g. qwen2.5-instruct or gpt-4o",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("DEVLOG_LLM_API_KEY", ""),
        help="Bearer token, if the backend requires one (unused by most local servers)",
    )
    args = parser.parse_args()

    headers = {"Authorization": f"Bearer {args.api_key}"} if args.api_key else {}
    server_params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            tools_result = await session.list_tools()
            oai_tools = to_openai_tools(tools_result.tools)

            async with httpx.AsyncClient(headers=headers, timeout=120) as http_client:
                await repl(
                    http_client,
                    session,
                    args.base_url,
                    args.model,
                    oai_tools,
                    init_result.instructions,
                )


if __name__ == "__main__":
    asyncio.run(main())
