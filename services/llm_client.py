"""Compatibility wrapper for the unified provider interface."""

from __future__ import annotations

import os
from typing import Any

from services.llm_provider import DEFAULT_MODEL_NAME, get_provider


MODEL_NAME = os.getenv("MODEL_NAME", DEFAULT_MODEL_NAME)


async def call_llm(prompt: str, model: str | None = None, options: dict[str, Any] | None = None) -> str:
    provider = get_provider()
    return await provider.complete(prompt, model=model or MODEL_NAME, options=options)
