"""Unified async LLM provider interface for chat, memory, and tool workflows."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

import httpx


DEFAULT_MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5-coder:3b")
DEFAULT_PROVIDER_NAME = os.getenv("LLM_PROVIDER", "ollama").lower()


class BaseProvider(ABC):
    name = "base"

    @abstractmethod
    async def complete(self, prompt: str, model: str | None = None, options: dict[str, Any] | None = None) -> str:
        raise NotImplementedError


class OllamaProvider(BaseProvider):
    name = "ollama"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")

    async def complete(self, prompt: str, model: str | None = None, options: dict[str, Any] | None = None) -> str:
        payload: dict[str, Any] = {
            "model": model or DEFAULT_MODEL_NAME,
            "prompt": prompt,
            "stream": False,
        }
        if options:
            for key in ("temperature", "top_p", "top_k", "stop", "seed", "num_predict"):
                if key in options:
                    payload[key] = options[key]

        timeout = float((options or {}).get("timeout", 120.0))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")


class OpenAICompatibleProvider(BaseProvider):
    name = "openai"

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def complete(self, prompt: str, model: str | None = None, options: dict[str, Any] | None = None) -> str:
        payload: dict[str, Any] = {
            "model": model or DEFAULT_MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": (options or {}).get("temperature", 0),
        }
        if options:
            for key in ("max_tokens", "top_p", "stop", "presence_penalty", "frequency_penalty"):
                if key in options:
                    payload[key] = options[key]

        timeout = float((options or {}).get("timeout", 120.0))
        async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
            response = await client.post(f"{self.base_url}/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "") or ""


class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("ANTHROPIC_API_KEY", "")
        self.base_url = (base_url or os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")).rstrip("/")

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured for the selected provider")
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    async def complete(self, prompt: str, model: str | None = None, options: dict[str, Any] | None = None) -> str:
        payload: dict[str, Any] = {
            "model": model or DEFAULT_MODEL_NAME,
            "max_tokens": (options or {}).get("max_tokens", 1024),
            "messages": [{"role": "user", "content": prompt}],
        }
        if options and "temperature" in options:
            payload["temperature"] = options["temperature"]

        timeout = float((options or {}).get("timeout", 120.0))
        async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
            response = await client.post(f"{self.base_url}/messages", json=payload)
        response.raise_for_status()
        data = response.json()

        parts: list[str] = []
        for content in data.get("content", []):
            if isinstance(content, dict) and content.get("type") == "text":
                parts.append(content.get("text", ""))
        return "".join(parts)


class GroqProvider(OpenAICompatibleProvider):
    name = "groq"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            api_key=api_key if api_key is not None else os.getenv("GROQ_API_KEY", ""),
        )


@lru_cache(maxsize=1)
def get_provider() -> BaseProvider:
    provider_name = DEFAULT_PROVIDER_NAME
    if provider_name == "openai":
        return OpenAICompatibleProvider()
    if provider_name == "anthropic":
        return AnthropicProvider()
    if provider_name == "groq":
        return GroqProvider()
    if provider_name == "ollama":
        return OllamaProvider()
    raise ValueError(f"Unsupported LLM_PROVIDER value: {provider_name}")
