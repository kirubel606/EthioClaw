"""Build the final LLM prompt from separated trusted and untrusted context."""

from dataclasses import dataclass

from services.persona_prompt import PERSONA_PROMPT
from services.system_prompt import SYSTEM_PROMPT
from services.context_budget import apply_prompt_budget


@dataclass
class PromptAssembly:
    prompt: str
    total_tokens: int
    trimmed: bool
    dropped_sources: list[str]
    token_counts: dict[str, int]


def build_prompt(
    user_message: str,
    identity_facts: str,
    general_facts: str,
    context: str,
    document_context: str = "",
    recent_turns: str = "",
    recent_turn_records: list[dict[str, str]] | None = None,
    working_summary: str = "",
    tool_context: str = "",
    mcp_tools: str = "",
) -> PromptAssembly:
    correction_signals = [
        "that's wrong",
        "that is wrong",
        "doesn't play for",
        "doesn't exist",
        "you made that up",
        "incorrect",
        "actually",
        "no,",
        "wrong,",
    ]

    def _has_correction_signal(turns: list[dict[str, str]] | None) -> bool:
        if user_message and any(signal in user_message.lower() for signal in correction_signals):
            return True
        recent = (turns or [])[-6:]
        for turn in recent:
            if turn.get("role") != "user":
                continue
            content = (turn.get("content") or "").lower()
            if any(signal in content for signal in correction_signals):
                return True
        return False

    identity_block = identity_facts.strip() if identity_facts.strip() else "No identity facts stored yet."
    general_block = general_facts.strip() if general_facts.strip() else "No general facts stored yet."
    context_block = context.strip() if context.strip() else "No previous conversation context."
    recent_block = recent_turns.strip() if recent_turns.strip() else "No recent turns cached yet."
    summary_block = working_summary.strip() if working_summary.strip() else "No active task summary yet."
    document_block = document_context.strip() if document_context.strip() else "No uploaded document context."
    tool_block = tool_context.strip() if tool_context.strip() else "No tool output."

    if _has_correction_signal(recent_turn_records):
        correction_note = (
            "NOTE: The user has corrected a previous answer in this conversation. "
            "Treat the user's correction as ground truth. Do not repeat the previously wrong answer."
        )
        context_block = f"{correction_note}\n\n{context_block}"

    budgeted = apply_prompt_budget(
        {
            "working_summary": summary_block,
            "recent_turns": recent_block,
            "context": context_block,
            "document_context": document_block,
            "tool_context": tool_block,
        }
    )

    prompt = f"""\
{SYSTEM_PROMPT}

{PERSONA_PROMPT}

=== USER PROFILE (REFERENCE ONLY - USE WHEN ASKED ABOUT USER) ===
Identity: {identity_block}
Additional: {general_block}

=== CURRENT TASK SUMMARY ===
{budgeted.blocks["working_summary"] or "No active task summary yet."}

=== RECENT TURNS ===
{budgeted.blocks["recent_turns"] or "No recent turns cached yet."}

=== TOOL OUTPUTS ===
{budgeted.blocks["tool_context"] or "No tool output."}

=== UPLOADED DOCUMENT CONTEXT ===
{budgeted.blocks["document_context"] or "No uploaded document context."}

=== CONVERSATION HISTORY ===
{budgeted.blocks["context"] or "No previous conversation context."}

=== CURRENT EXCHANGE ===
User: {user_message}
Assistant:"""

    return PromptAssembly(
        prompt=prompt,
        total_tokens=budgeted.total_tokens,
        trimmed=budgeted.trimmed,
        dropped_sources=budgeted.dropped_sources,
        token_counts=budgeted.token_counts,
    )
