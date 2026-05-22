from services.memory_schema import MemoryFact


# -------------------------
# CONTRADICTION DETECTOR
# -------------------------
async def detect_contradictions(
    new_facts: list[MemoryFact],
    existing_facts: dict
) -> list[dict]:
    """
    Compares incoming extracted facts against what is already stored in Postgres.

    Returns a list of contradiction records:
      [{"key": "age", "old_value": "25", "new_value": "26", "fact": <MemoryFact>}]

    Resolution strategy: caller decides (overwrite, skip, or flag).
    """
    contradictions = []

    for fact in new_facts:
        old_value = existing_facts.get(fact.key)

        if old_value is not None and old_value.strip().lower() != fact.value.strip().lower():
            contradictions.append({
                "key":       fact.key,
                "old_value": old_value,
                "new_value": fact.value,
                "fact":      fact,
            })

    return contradictions


# -------------------------
# RESOLVE: prefer newest (default strategy)
# -------------------------
def resolve_prefer_newest(contradictions: list[dict]) -> list[MemoryFact]:
    """
    Returns the list of facts that should be saved after resolution.
    Default: newest fact wins — overwrite old value.
    """
    return [c["fact"] for c in contradictions]


# -------------------------
# RESOLVE: prefer highest confidence
# -------------------------
def resolve_prefer_confidence(
    contradictions: list[dict],
    existing_records: list[dict]
) -> list[MemoryFact]:
    """
    Returns facts where the new confidence is strictly higher than the stored one.
    Otherwise discards the new fact (keeps existing).
    """
    existing_confidence = {r["key"]: r["confidence"] for r in existing_records}
    to_save = []

    for c in contradictions:
        existing_conf = existing_confidence.get(c["key"], 0.0)
        if c["fact"].confidence > existing_conf:
            to_save.append(c["fact"])
        else:
            print(f"⚠️  Keeping existing '{c['key']}' = '{c['old_value']}' "
                  f"(confidence {existing_conf} >= new {c['fact'].confidence})")

    return to_save
