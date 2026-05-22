from services.system_prompt import SYSTEM_PROMPT
from services.persona_prompt import PERSONA_PROMPT


def build_prompt(user_message: str, identity_facts: str, general_facts: str, context: str) -> str:
    """
    Builds a strictly layered prompt.
    Order: SYSTEM RULES → IDENTITY (truth) → GENERAL FACTS → SEMANTIC MEMORY → PERSONA → USER INPUT
    """

    identity_block = identity_facts.strip() if identity_facts.strip() else "No identity facts stored yet."
    general_block  = general_facts.strip()  if general_facts.strip()  else "No general facts stored yet."
    context_block  = context.strip()        if context.strip()        else "No previous conversation context."

    return f"""\
{SYSTEM_PROMPT}

=== USER PROFILE — IDENTITY (ABSOLUTE TRUTH — ALWAYS CORRECT) ===
These are verified identity facts. Treat them as immutable ground truth.
{identity_block}

=== USER PROFILE — ADDITIONAL FACTS ===
{general_block}

=== SEMANTIC MEMORY (PAST CONVERSATION CONTEXT) ===
{context_block}

{PERSONA_PROMPT}

=== USER MESSAGE ===
{user_message}

=== YOUR RESPONSE ===
"""