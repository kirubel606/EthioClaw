from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Union

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from services.json_utils import extract_json_blocks
from services.llm_provider import DEFAULT_MODEL_NAME, DEFAULT_PROVIDER_NAME, get_provider


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[dict[str, Any]]
    raw: str
    provider: str


class LangChainService:
    def __init__(self) -> None:
        self._provider = None

    def _get_provider(self):
        if self._provider is None:
            self._provider = get_provider()
        return self._provider

    def _render_messages(
        self,
        messages: List[Union[SystemMessage, HumanMessage, AIMessage, ToolMessage]],
    ) -> str:
        rendered: list[str] = []
        for message in messages:
            role = getattr(message, "type", message.__class__.__name__.replace("Message", "").lower())
            content = getattr(message, "content", "")
            rendered.append(f"{role.upper()}: {content}")
            tool_calls = getattr(message, "tool_calls", None)
            if not tool_calls:
                additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
                tool_calls = additional_kwargs.get("tool_calls")
            if tool_calls:
                rendered.append(f"{role.upper()} TOOL_CALLS: {json.dumps(tool_calls, ensure_ascii=False, default=str)}")
        return "\n".join(rendered)

    def _build_prompt(self, messages: str, mcp_tools: list[dict[str, Any]]) -> str:
        tool_block = json.dumps(mcp_tools, ensure_ascii=False, default=str, indent=2) if mcp_tools else "[]"
        return (
            "You are a tool-using assistant.\n"
            "Use the available tools only when they improve the answer.\n"
            "Respond with plain text when no tool is needed.\n"
            "If you need tools, return only one JSON object with this schema:\n"
            '{"content":"assistant text or empty string","tool_calls":[{"name":"server__tool","args":{},"id":"unique_id"}]}\n'
            "Do not wrap the JSON in markdown.\n\n"
            "=== AVAILABLE TOOLS ===\n"
            f"{tool_block}\n\n"
            "=== CONVERSATION ===\n"
            f"{messages}\n\n"
            "=== RESPONSE ==="
        )

    def _parse_response(self, raw_text: str) -> tuple[str, list[dict[str, Any]]]:
        blocks = extract_json_blocks(raw_text)
        for block in blocks:
            tool_calls = block.get("tool_calls")
            if isinstance(tool_calls, list):
                content = str(block.get("content", "") or "")
                return content, [call for call in tool_calls if isinstance(call, dict)]
        return raw_text.strip(), []

    async def call_llm_with_tools(
        self,
        messages: List[Union[SystemMessage, HumanMessage, AIMessage, ToolMessage]],
        mcp_tools: List[Dict[str, Any]] | None = None,
        *,
        request_id: str | None = None,
        model: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> LLMResponse:
        provider_name = DEFAULT_PROVIDER_NAME
        started_at = time.perf_counter()
        prompt = self._build_prompt(self._render_messages(messages), mcp_tools or [])

        print(
            json.dumps(
                {
                    "event": "llm_request_start",
                    "request_id": request_id,
                    "provider": provider_name,
                    "model": model or DEFAULT_MODEL_NAME,
                },
                ensure_ascii=False,
            )
        )

        try:
            provider = self._get_provider()
            provider_name = getattr(provider, "name", "unknown")
            raw_text = await provider.complete(
                prompt,
                model=model or DEFAULT_MODEL_NAME,
                options=options or {"temperature": 0, "timeout": 120.0},
            )
            content, tool_calls = self._parse_response(raw_text)
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            print(
                json.dumps(
                    {
                        "event": "llm_request_success",
                        "request_id": request_id,
                        "provider": provider_name,
                        "model": model or DEFAULT_MODEL_NAME,
                        "latency_ms": latency_ms,
                    },
                    ensure_ascii=False,
                )
            )
            return LLMResponse(content=content, tool_calls=tool_calls, raw=raw_text, provider=provider_name)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            print(
                json.dumps(
                    {
                        "event": "llm_request_failure",
                        "request_id": request_id,
                        "provider": provider_name,
                        "model": model or DEFAULT_MODEL_NAME,
                        "latency_ms": latency_ms,
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                )
            )
            raise


langchain_service = LangChainService()
