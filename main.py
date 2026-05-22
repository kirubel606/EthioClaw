from fastapi import FastAPI, HTTPException
import traceback

from schema import ChatRequest, ChatResponse

from services.memory_service   import retrieve_context, save_message, setup_collection_async
from services.memory_extractor import extract_facts
from services.memory_schema    import MemoryType
from services.prompt_builder   import build_prompt
from services.ai_service       import ask_model

from services.fact_db import (
    init_db,
    save_fact,
    get_facts,
    get_identity_facts,
    get_fact_records,
)

from services.contradiction_detector import (
    detect_contradictions,
    resolve_prefer_newest,
)

from services.fact_verifier import verify_response


app = FastAPI()


# -------------------------
# STARTUP
# -------------------------
@app.on_event("startup")
async def startup():
    await init_db()
    await setup_collection_async()


# -------------------------
# CHAT ENDPOINT
# -------------------------
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):

    try:

        # ── STEP 1: Extract typed facts from the user message ───────────────
        extracted = await extract_facts(request.message)
        new_facts = extracted.facts

        # ── STEP 2: Contradiction detection ─────────────────────────────────
        existing_flat    = await get_facts()         # {key: value}
        existing_records = await get_fact_records()  # [{key, value, confidence, ...}]

        contradictions = await detect_contradictions(new_facts, existing_flat)

        if contradictions:
            for c in contradictions:
                print(
                    f"[CONTRADICTION] — '{c['key']}': "
                    f"'{c['old_value']}' → '{c['new_value']}'"
                )

            # Resolve: newest value wins (default strategy)
            override_facts = resolve_prefer_newest(contradictions)

            # Save overrides
            for fact in override_facts:
                await save_fact(
                    fact.key,
                    fact.value,
                    fact.memory_type.value,
                    fact.confidence,
                    fact.source,
                )

            # Save non-contradicting new facts
            override_keys = {f.key for f in override_facts}
            for fact in new_facts:
                if fact.key not in override_keys and fact.key not in existing_flat:
                    await save_fact(
                        fact.key,
                        fact.value,
                        fact.memory_type.value,
                        fact.confidence,
                        fact.source,
                    )

        else:
            # ── STEP 3: Save all new facts (no contradictions) ──────────────
            for fact in new_facts:
                await save_fact(
                    fact.key,
                    fact.value,
                    fact.memory_type.value,
                    fact.confidence,
                    fact.source,
                )

        # ── STEP 4: Build USER PROFILE blocks ───────────────────────────────
        #   Identity facts  → highest trust block (name, age, profession, etc.)
        #   General facts   → secondary block
        identity_facts_dict = await get_identity_facts()
        all_facts_dict      = await get_facts()

        # Identity block: structured label
        identity_block = "\n".join(
            f"  {k}: {v}" for k, v in identity_facts_dict.items()
        )

        # General block: facts that are NOT identity
        general_block = "\n".join(
            f"  {k}: {v}"
            for k, v in all_facts_dict.items()
            if k not in identity_facts_dict
        )

        # ── STEP 5: Retrieve ranked semantic memory from Qdrant ──────────────
        context = await retrieve_context(request.message)

        # ── STEP 6: Build strictly layered prompt ───────────────────────────
        final_prompt = build_prompt(
            user_message=request.message,
            identity_facts=identity_block,
            general_facts=general_block,
            context=context
        )

        # ── STEP 7: Call LLM ─────────────────────────────────────────────────
        ai_response = await ask_model(final_prompt)

        # ── STEP 8: Hallucination check (Phase 4) ────────────────────────────
        verification = await verify_response(ai_response, all_facts_dict)

        if not verification.get("valid", True):
            violations = verification.get("violations", [])
            print(f"[HALLUCINATION DETECTED] in response — violations: {violations}")
            # Log but still return response (fail-open policy)
            # To block instead: raise HTTPException(status_code=500, detail=...)

        # ── STEP 9: Save conversation to Qdrant ──────────────────────────────
        await save_message("user",      request.message)
        await save_message("assistant", ai_response)

        # ── STEP 10: Return ───────────────────────────────────────────────────
        return ChatResponse(response=ai_response)

    except Exception as e:
        print("[ERROR] ", repr(e))
        print(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail=str(e) or "Internal Server Error (see logs)"
        )