from services.persona_prompt import PERSONA_PROMPT
from services.system_prompt import SYSTEM_PROMPT


def build_prompt(
    user_message: str,
    identity_facts: str,
    general_facts: str,
    context: str,
    document_context: str = "",
    recent_turns: str = "",
    working_summary: str = "",
    tool_context: str = "",
) -> str:
    identity_block = identity_facts.strip() if identity_facts.strip() else "No identity facts stored yet."
    general_block = general_facts.strip() if general_facts.strip() else "No general facts stored yet."
    context_block = context.strip() if context.strip() else "No previous conversation context."
    recent_block = recent_turns.strip() if recent_turns.strip() else "No recent turns cached yet."
    summary_block = working_summary.strip() if working_summary.strip() else "No active task summary yet."
    document_block = document_context.strip() if document_context.strip() else "No uploaded document context."
    tool_block = tool_context.strip() if tool_context.strip() else "No tool output."

    return f"""\
{SYSTEM_PROMPT}

{PERSONA_PROMPT}

=== USER PROFILE (REFERENCE ONLY - USE WHEN ASKED ABOUT USER) ===
Identity: {identity_block}
Additional: {general_block}

=== CURRENT TASK SUMMARY ===
{summary_block}

=== RECENT TURNS ===
{recent_block}

=== TOOL OUTPUTS ===
{tool_block}

=== UPLOADED DOCUMENT CONTEXT ===
{document_block}

=== CONVERSATION HISTORY ===
{context_block}

=== CURRENT EXCHANGE ===
User: {user_message}
Assistant:"""
