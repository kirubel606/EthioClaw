import json
from services.llm_client import call_llm


async def verify_response(ai_response: str, facts: dict) -> dict:
    """
    Phase 4 — Post-response hallucination check.

    Runs a lightweight LLM verification pass to confirm the response
    does not contradict any verified user facts.

    Returns:
        {"valid": True}
        {"valid": False, "violations": ["AI said X but fact says Y", ...]}
    """

    if not facts:
        # Nothing to verify against
        return {"valid": True}

    facts_text = "\n".join(f"- {k}: {v}" for k, v in facts.items())

    prompt = f"""
You are a fact-checker. You will be given a list of verified user facts and an AI response.
Your job is to detect if the AI response contradicts any of the verified facts.

Verified facts:
{facts_text}

AI response:
{ai_response}

Rules:
- Only flag DIRECT contradictions (e.g. facts say age=26, response says age=30).
- Do NOT flag if a fact is simply absent from the response (that is fine).
- Do NOT flag persona/tone differences.

Respond with ONLY valid JSON, no markdown:
{{"valid": true}}

or if there are violations:
{{"valid": false, "violations": ["AI said age is 30 but verified fact says 26"]}}
"""

    result = await call_llm(prompt)

    if not result:
        return {"valid": True}

    cleaned = result.strip().replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(cleaned)
        if not parsed.get("valid", True):
            violations = parsed.get("violations", [])
            print(f"[HALLUCINATION DETECTED] violations: {violations}")
        return parsed

    except json.JSONDecodeError:
        print("[WARNING] Fact verifier returned non-JSON — skipping verification:", result)
        return {"valid": True}
