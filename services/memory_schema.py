from enum import Enum
from pydantic import BaseModel, Field


# -------------------------
# MEMORY TYPE ENUM
# -------------------------
class MemoryType(str, Enum):
    IDENTITY   = "identity"    # name, age, profession — highest trust, always injected
    PREFERENCE = "preference"  # likes, dislikes, habits — medium trust
    GENERAL    = "general"     # everything else — lower trust


# -------------------------
# SINGLE TYPED MEMORY FACT
# -------------------------
class MemoryFact(BaseModel):
    key:         str        = Field(...,  description="Fact key, e.g. 'name', 'age'")
    value:       str        = Field(...,  description="Fact value, e.g. 'Kirubel', '26'")
    memory_type: MemoryType = Field(MemoryType.GENERAL, description="Category of this fact")
    confidence:  float      = Field(1.0, ge=0.0, le=1.0, description="Certainty 0.0–1.0")
    source:      str        = Field("user", description="Origin: 'user' | 'inferred'")


# -------------------------
# BATCH EXTRACTION RESULT
# -------------------------
class ExtractedFacts(BaseModel):
    facts: list[MemoryFact] = []


# -------------------------
# IDENTITY KEYS (always treated as IDENTITY type)
# -------------------------
IDENTITY_KEYS = {"name", "age", "profession", "job", "occupation", "nationality", "location"}


def resolve_memory_type(key: str, declared_type: MemoryType) -> MemoryType:
    """
    Upgrade declared type to IDENTITY if the key is a known identity field.
    Prevents the LLM from accidentally classifying 'name' as 'general'.
    """
    if key.lower() in IDENTITY_KEYS:
        return MemoryType.IDENTITY
    return declared_type
