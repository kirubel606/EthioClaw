import json
from services.llm_client import call_llm
from services.memory_schema import MemoryFact, MemoryType, ExtractedFacts, resolve_memory_type


def _is_question_only(message: str) -> bool:
    """
    Heuristic: if the message is purely a question, skip extraction.
    Questions can't contain declarative user facts — only queries.
    """
    stripped = message.strip()
    # Pure question: ends with ? and has no declarative clause before it
    lines = [l.strip() for l in stripped.splitlines() if l.strip()]
    return all(l.endswith("?") for l in lines) if lines else False


async def extract_facts(message: str) -> ExtractedFacts:
    """
    Extracts structured, typed MemoryFact objects from a user message.
    Only processes DECLARATIVE statements and user CORRECTIONS — questions are skipped.
    Returns an ExtractedFacts container (never raises — empty on failure).
    """

    # Fast skip: pure question messages contain no declarable facts
    if _is_question_only(message):
        return ExtractedFacts()

    prompt = f"""
Extract personal facts or user corrections from this message.

STRICT RULES:
- ONLY extract facts from DECLARATIVE first-person statements ("My name is X", "I am 26", "I work as Y") or user CORRECTIONS of prior statements (e.g. "X plays for Y not Z", "the player is X not Y", "actually, X doesn't exist").
- For user corrections (where the user corrects a previous mistake or fact), classify the memory_type as "correction".
- NEVER extract from questions ("What is my name?", "How old am I?") — return empty facts for those.
- NEVER use placeholder words like "your_name", "your_age", "unknown" as values.
- If the message is a question or contains no real personal declarations or corrections, return {{"facts": []}}.
- Values must be real, concrete data — not template words.

Message:
{message}

Classify each fact:
- "identity"   → name, age, profession, job, nationality, location
- "preference" → likes, dislikes, habits, hobbies
- "correction" → user corrections of previous facts (e.g., "X plays for Y not Z", "the player is X not Y", "you got X wrong, it is Y")
- "general"    → anything else

Return ONLY valid JSON, no markdown:
{{
  "facts": [
    {{
      "key":         "name|age|profession|...",
      "value":       "actual_value_here",
      "memory_type": "identity|preference|general|correction",
      "confidence":  1.0,
      "source":      "user"
    }}
  ]
}}

If no declarative facts or corrections exist, return: {{"facts": []}}
"""

    response = await call_llm(prompt)

    if not response:
        return ExtractedFacts()

    # Strip markdown artifacts
    cleaned = response.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    # Placeholder guard — reject known bad values at validation time
    PLACEHOLDER_VALUES = {
        "your_name", "your_age", "your_profession", "unknown",
        "none", "n/a", "null", "not provided", "your_location"
    }

    try:
        raw = json.loads(cleaned)
        facts = []

        for item in raw.get("facts", []):
            try:
                value = str(item.get("value", "")).strip()

                # Skip placeholder values that slipped through
                if value.lower() in PLACEHOLDER_VALUES or not value:
                    print(f"⚠️  Rejected placeholder fact: {item}")
                    continue

                # Force upgrade memory_type for known identity keys
                declared = MemoryType(item.get("memory_type", "general"))
                resolved = resolve_memory_type(item["key"], declared)

                fact = MemoryFact(
                    key=item["key"],
                    value=value,
                    memory_type=resolved,
                    confidence=float(item.get("confidence", 1.0)),
                    source=item.get("source", "user")
                )
                facts.append(fact)

                # Write correction immediately to Postgres user_facts with type="correction"
                if resolved == MemoryType.CORRECTION:
                    try:
                        from services.fact_db import save_fact
                        await save_fact(
                            key=fact.key,
                            value=fact.value,
                            memory_type=MemoryType.CORRECTION.value,
                            confidence=1.0,  # high confidence
                            source=fact.source
                        )
                        print(f"✅ Immediate correction saved to Postgres: {fact.key} -> {fact.value}")
                    except Exception as db_err:
                        print(f"❌ Failed to save correction fact directly to Postgres: {db_err}")

            except Exception as parse_err:
                print(f"⚠️  Skipping malformed fact item: {item} — {parse_err}")

        return ExtractedFacts(facts=facts)

    except json.JSONDecodeError:
        print("❌ INVALID JSON FROM EXTRACTOR:", response)
        return ExtractedFacts()