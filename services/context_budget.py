"""Prompt budget management for chat context assembly.

This module trims prompt blocks by source priority so the agent keeps the
highest-value context inside the model window without cutting mid-chunk when
it can avoid doing so.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass


MODEL_CONTEXT_TOKENS = int(os.getenv("MODEL_CONTEXT_TOKENS", "8192"))
REDIS_SESSION_TOKEN_LIMIT = 600
QDRANT_CHAT_TOKEN_LIMIT = 800
QDRANT_DOCUMENT_TOKEN_LIMIT = 1000
TOOL_CONTEXT_TOKEN_LIMIT = 400
SYSTEM_PROMPT_TOKEN_LIMIT = 500


@dataclass
class BudgetedPromptBlocks:
    blocks: dict[str, str]
    total_tokens: int
    trimmed: bool
    dropped_sources: list[str]
    token_counts: dict[str, int]


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    words = re.findall(r"\S+", text)
    return max(1, math.ceil(len(words) * 1.33))


def _split_by_chunk_boundaries(text: str) -> list[str]:
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", text or "") if chunk.strip()]
    if chunks:
        return chunks
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if lines:
        return lines
    return [text.strip()] if text.strip() else []


def _trim_chunks_to_budget(chunks: list[str], max_tokens: int, preserve: str) -> list[str]:
    if max_tokens <= 0 or not chunks:
        return []

    ordered_chunks = chunks if preserve == "start" else list(reversed(chunks))
    kept: list[str] = []
    total = 0

    for chunk in ordered_chunks:
        chunk_tokens = estimate_tokens(chunk)
        if total and total + chunk_tokens > max_tokens:
            break
        if chunk_tokens > max_tokens and not kept:
            # Keep the chunk boundary intact even when it is larger than the
            # available budget; this avoids mid-sentence truncation.
            kept.append(chunk)
            break
        kept.append(chunk)
        total += chunk_tokens

    if preserve == "start":
        return kept
    return list(reversed(kept))


def trim_text_to_budget(text: str, max_tokens: int, preserve: str = "end") -> str:
    text = (text or "").strip()
    if not text or max_tokens <= 0:
        return ""

    if estimate_tokens(text) <= max_tokens:
        return text

    chunks = _split_by_chunk_boundaries(text)
    kept = _trim_chunks_to_budget(chunks, max_tokens, preserve=preserve)
    return "\n\n".join(kept).strip()


def apply_prompt_budget(blocks: dict[str, str]) -> BudgetedPromptBlocks:
    """Trim prompt blocks according to the agent memory priority rules."""

    normalized = {name: (value or "").strip() for name, value in blocks.items()}
    token_counts = {name: estimate_tokens(value) for name, value in normalized.items()}
    dropped_sources: list[str] = []
    trimmed = False

    per_block_limits = {
        "working_summary": REDIS_SESSION_TOKEN_LIMIT // 3,
        "recent_turns": REDIS_SESSION_TOKEN_LIMIT - (REDIS_SESSION_TOKEN_LIMIT // 3),
        "context": QDRANT_CHAT_TOKEN_LIMIT,
        "document_context": QDRANT_DOCUMENT_TOKEN_LIMIT,
        "tool_context": TOOL_CONTEXT_TOKEN_LIMIT,
    }
    preserve_modes = {
        "working_summary": "end",
        "recent_turns": "start",
        "context": "end",
        "document_context": "end",
        "tool_context": "end",
    }

    for name, limit in per_block_limits.items():
        current = normalized.get(name, "")
        if not current:
            continue
        trimmed_text = trim_text_to_budget(current, limit, preserve=preserve_modes[name])
        if trimmed_text != current:
            normalized[name] = trimmed_text
            token_counts[name] = estimate_tokens(trimmed_text)
            trimmed = True
            dropped_sources.append(name)

    total_tokens = sum(estimate_tokens(value) for value in normalized.values())

    if total_tokens > MODEL_CONTEXT_TOKENS:
        trim_order = [
            ("document_context", "end"),
            ("context", "end"),
            ("recent_turns", "start"),
            ("tool_context", "end"),
            ("working_summary", "end"),
        ]

        for name, preserve in trim_order:
            if total_tokens <= MODEL_CONTEXT_TOKENS:
                break

            current = normalized.get(name, "")
            if not current:
                continue

            available = max(0, MODEL_CONTEXT_TOKENS - (total_tokens - estimate_tokens(current)))
            trimmed_text = trim_text_to_budget(current, available, preserve=preserve)
            if trimmed_text != current:
                normalized[name] = trimmed_text
                token_counts[name] = estimate_tokens(trimmed_text)
                trimmed = True
                if name not in dropped_sources:
                    dropped_sources.append(name)
                total_tokens = sum(estimate_tokens(value) for value in normalized.values())

    return BudgetedPromptBlocks(
        blocks=normalized,
        total_tokens=total_tokens,
        trimmed=trimmed,
        dropped_sources=dropped_sources,
        token_counts=token_counts,
    )
