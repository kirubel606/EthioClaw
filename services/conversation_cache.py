import json
import os
from typing import Any

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover - optional dependency
    redis = None


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SESSION_PREFIX = "chat:session"
DEFAULT_SESSION_ID = "default"
MAX_TURNS = int(os.getenv("CACHE_MAX_TURNS", "12"))

_redis_client = None
_local_store: dict[str, dict[str, Any]] = {}


def _session_key(session_id: str) -> str:
    return f"{SESSION_PREFIX}:{session_id}"


def _fallback_state(session_id: str) -> dict[str, Any]:
    return _local_store.setdefault(session_id, {"summary": "", "turns": []})


async def _get_redis_client():
    global _redis_client

    if redis is None:
        return None

    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)

    try:
        await _redis_client.ping()
        return _redis_client
    except Exception:
        return None


def _clean_text(value: str, limit: int = 4000) -> str:
    text = (value or "").strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


async def get_summary(session_id: str = DEFAULT_SESSION_ID) -> str:
    client = await _get_redis_client()
    if client is None:
        return _fallback_state(session_id)["summary"]

    value = await client.get(f"{_session_key(session_id)}:summary")
    return value or ""


async def set_summary(session_id: str, summary: str) -> None:
    summary = _clean_text(summary, 12000)
    client = await _get_redis_client()
    if client is None:
        _fallback_state(session_id)["summary"] = summary
        return

    await client.set(f"{_session_key(session_id)}:summary", summary)


async def get_recent_turns(session_id: str = DEFAULT_SESSION_ID, limit: int = 8) -> list[dict[str, str]]:
    client = await _get_redis_client()
    if client is None:
        return _fallback_state(session_id)["turns"][-limit:]

    raw = await client.lrange(f"{_session_key(session_id)}:turns", 0, max(limit - 1, 0))
    turns: list[dict[str, str]] = []
    for item in raw:
        try:
            parsed = json.loads(item)
            if isinstance(parsed, dict) and "role" in parsed and "content" in parsed:
                turns.append({"role": str(parsed["role"]), "content": str(parsed["content"])})
        except json.JSONDecodeError:
            continue
    return turns


async def append_turn(
    session_id: str,
    role: str,
    content: str,
    limit: int = MAX_TURNS,
) -> None:
    entry = {
        "role": role,
        "content": _clean_text(content),
    }

    client = await _get_redis_client()
    if client is None:
        state = _fallback_state(session_id)
        state["turns"].append(entry)
        state["turns"] = state["turns"][-limit:]
        return

    key = f"{_session_key(session_id)}:turns"
    await client.rpush(key, json.dumps(entry))
    await client.ltrim(key, -limit, -1)


async def build_memory_block(session_id: str = DEFAULT_SESSION_ID, limit: int = 8) -> str:
    summary = await get_summary(session_id)
    turns = await get_recent_turns(session_id, limit=limit)

    summary_block = summary.strip() or "No working summary yet."
    if turns:
        turn_lines = "\n".join(f"  {turn['role']}: {turn['content']}" for turn in turns)
    else:
        turn_lines = "  No recent turns."

    return (
        "=== CURRENT TASK SUMMARY ===\n"
        f"{summary_block}\n\n"
        "=== RECENT TURNS ===\n"
        f"{turn_lines}"
    )


async def refresh_summary(
    session_id: str,
    latest_user_message: str,
    latest_assistant_message: str,
) -> str:
    from services.llm_client import call_llm

    previous_summary = await get_summary(session_id)
    recent_turns = await get_recent_turns(session_id, limit=MAX_TURNS)
    recent_text = "\n".join(f"- {turn['role']}: {turn['content']}" for turn in recent_turns[-MAX_TURNS:])

    prompt = f"""
You maintain the short-term working memory for a chatbot.
Update the summary of what the user and assistant are currently doing.

Rules:
- Focus on the active task, unresolved questions, names, files, and tool outputs.
- Keep it concise, ideally 1 to 3 short sentences.
- Do not add fictional details.
- If the latest exchange changes the task, reflect the change.
- Use plain text only.

Current summary:
{previous_summary or "None"}

Recent turns:
{recent_text or "None"}

Latest user message:
{latest_user_message}

Latest assistant message:
{latest_assistant_message}
"""

    try:
        summary = (await call_llm(prompt)).strip()
        summary = summary.replace("```json", "").replace("```", "").strip()
        await set_summary(session_id, summary)
        return summary
    except Exception:
        fallback_summary = _clean_text(f"{latest_user_message} | {latest_assistant_message}", 1200)
        await set_summary(session_id, fallback_summary)
        return fallback_summary
