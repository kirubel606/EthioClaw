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
    Only processes DECLARATIVE statements — questions are skipped.
    Returns an ExtractedFacts container (never raises — empty on failure).
    """

    # Fast skip: pure question messages contain no declarable facts
    if _is_question_only(message):
        return ExtractedFacts()

    prompt = f"""
Extract personal facts about the USER from this message.

STRICT RULES:
- ONLY extract facts from DECLARATIVE first-person statements ("My name is X", "I am 26", "I work as Y").
- NEVER extract from questions ("What is my name?", "How old am I?") — return empty facts for those.
- NEVER use placeholder words like "your_name", "your_age", "unknown" as values.
- If the message is a question or contains no real personal declarations, return {{"facts": []}}.
- Values must be real, concrete data — not template words.

Message:
{message}

Classify each fact:
- "identity"   → name, age, profession, job, nationality, location
- "preference" → likes, dislikes, habits, hobbies
- "general"    → anything else

Return ONLY valid JSON, no markdown:
{{
  "facts": [
    {{
      "key":         "name|age|profession|...",
      "value":       "actual_value_here",
      "memory_type": "identity|preference|general",
      "confidence":  0.95,
      "source":      "user"
    }}
  ]
}}

If no declarative facts exist, return: {{"facts": []}}
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

            except Exception as parse_err:
                print(f"⚠️  Skipping malformed fact item: {item} — {parse_err}")

        return ExtractedFacts(facts=facts)

    except json.JSONDecodeError:
        print("❌ INVALID JSON FROM EXTRACTOR:", response)
        return ExtractedFacts()