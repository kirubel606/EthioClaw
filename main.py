from fastapi import FastAPI, HTTPException, Body, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import traceback

from schema import ChatRequest, ChatResponse, ChatPayload, DocumentUploadResponse, UploadedDocument

from services.memory_service   import retrieve_context, save_message, setup_collection_async
from services.memory_extractor import extract_facts
from services.memory_schema    import MemoryType, MemoryFact
from services.prompt_builder   import build_prompt
from services.ai_service       import ask_model
from services.conversation_cache import (
    append_turn,
    get_recent_turns,
    get_summary,
    refresh_summary,
)
from services.agent_tools import build_tool_bundle, generate_artifact, GENERATED_DIR
from services.document_service import (
    index_document,
    retrieve_document_context,
    setup_document_collection_async,
)

from services.fact_db import (
    init_db,
    save_fact,
    get_facts,
    get_identity_facts,
    get_fact_records,
    delete_fact,
    save_chat_message,
    get_sessions,
    get_session_history,
    delete_session,
)

from services.contradiction_detector import (
    detect_contradictions,
    resolve_prefer_newest,
)

from services.fact_verifier import verify_response


app = FastAPI()
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/generated", StaticFiles(directory=str(GENERATED_DIR)), name="generated")

# Allow the frontend (and any other origin during development) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# STARTUP
# -------------------------
@app.on_event("startup")
async def startup():
    await init_db()
    await setup_collection_async()
    await setup_document_collection_async()


# -------------------------
# CHAT ENDPOINT
# -------------------------
@app.post("/chat", response_model=ChatResponse)
async def chat(http_request: Request, request: dict = Body(...)):
    """Accept both the new ChatPayload format and the legacy simple format.
    The function extracts a unified `request_message` string for downstream processing.
    """
    # New format: parts list
    if "parts" in request and isinstance(request["parts"], list):
        request_message = "".join(part.get("text", "") for part in request["parts"])
    # Legacy format: simple message field
    elif "message" in request:
        request_message = request["message"]
    else:
        raise HTTPException(status_code=400, detail="Invalid request payload")

    session_id = str(request.get("session_id") or request.get("conversation_id") or "default")

    try:

        # ── STEP 1: Extract typed facts from the user message ───────────────
        extracted = await extract_facts(request_message)
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

        # ── STEP 5: Retrieve short-term cache + tool output ─────────────────
        working_summary = await get_summary(session_id)
        recent_turns = await get_recent_turns(session_id, limit=8)
        recent_turn_block = "\n".join(
            f"  {turn['role']}: {turn['content']}" for turn in recent_turns
        )
        tool_bundle = await build_tool_bundle(request_message)

        # ── STEP 6: Retrieve ranked semantic memory from Qdrant ──────────────
        context = await retrieve_context(request_message, session_id=session_id, limit=8)
        document_context = await retrieve_document_context(
            request_message,
            session_id=session_id,
            limit=8,
        )

        # ── STEP 7: Build strictly layered prompt ───────────────────────────
        final_prompt = build_prompt(
            user_message=request_message,
            identity_facts=identity_block,
            general_facts=general_block,
            context=context,
            document_context=document_context,
            recent_turns=recent_turn_block,
            working_summary=working_summary,
            tool_context=tool_bundle.context,
        )

        # ── STEP 8: Call LLM ─────────────────────────────────────────────────
        assistant_text = await ask_model(final_prompt)

        # ── STEP 9: Hallucination check (Phase 4) ────────────────────────────
        verification = await verify_response(assistant_text, all_facts_dict)

        if not verification.get("valid", True):
            violations = verification.get("violations", [])
            print(f"[HALLUCINATION DETECTED] in response — violations: {violations}")
            # Log but still return response (fail-open policy)
            # To block instead: raise HTTPException(status_code=500, detail=...)

        ai_response = assistant_text

        # If the request asked for a document, create the file from the response.
        if tool_bundle.artifact_kind:
            artifact_title = tool_bundle.artifact_title or "generated-content"
            artifact_path = generate_artifact(tool_bundle.artifact_kind, artifact_title, assistant_text)
            artifact_url = f"{str(http_request.base_url).rstrip('/')}/generated/{artifact_path.name}"
            ai_response = f"{assistant_text}\n\nGenerated file: [Download the presentation]({artifact_url})"

        # ── STEP 10: Save conversation to Qdrant, short-term cache and Postgres history ────────
        await save_message("user",      request_message, session_id=session_id)
        await save_message("assistant", ai_response,     session_id=session_id)
        await save_chat_message(session_id, "user", request_message)
        await save_chat_message(session_id, "assistant", ai_response)
        await append_turn(session_id, "user", request_message)
        await append_turn(session_id, "assistant", ai_response)
        await refresh_summary(session_id, request_message, ai_response)

        # ── STEP 11: Return ──────────────────────────────────────────────────
        return ChatResponse(response=ai_response)

    except Exception as e:
        print("[ERROR] ", repr(e))
        print(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail=str(e) or "Internal Server Error (see logs)"
        )


@app.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_documents(
    session_id: str = Form("default"),
    files: list[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    indexed_files: list[UploadedDocument] = []

    try:
        for upload in files:
            raw_bytes = await upload.read()
            result = await index_document(session_id, upload.filename, raw_bytes)
            indexed_files.append(UploadedDocument(**result.model_dump()))

        uploaded_names = ", ".join(item.filename for item in indexed_files) or "files"
        indexed_count = sum(item.chunks_indexed for item in indexed_files)
        confirmation_text = f"Indexed uploaded files: {uploaded_names}"
        summary_text = f"Indexed {len(indexed_files)} uploaded files with {indexed_count} document chunks."
        await save_chat_message(session_id, "system", confirmation_text)
        await append_turn(session_id, "system", confirmation_text)
        await refresh_summary(session_id, summary_text, confirmation_text)

        return DocumentUploadResponse(
            status="success",
            session_id=session_id,
            files=indexed_files,
        )
    except Exception as e:
        print("[ERROR] Failed to upload documents:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# FACTS MANAGEMENT ENDPOINTS
# -------------------------
@app.get("/facts")
async def get_all_facts_endpoint():
    try:
        records = await get_fact_records()
        return {"facts": records}
    except Exception as e:
        print("[ERROR] Failed to get facts:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/facts")
async def save_fact_endpoint(fact: MemoryFact):
    try:
        await save_fact(
            fact.key,
            fact.value,
            fact.memory_type.value,
            fact.confidence,
            fact.source
        )
        return {"status": "success"}
    except Exception as e:
        print("[ERROR] Failed to save fact:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/facts/{key}")
async def delete_fact_endpoint(key: str):
    try:
        await delete_fact(key)
        return {"status": "success"}
    except Exception as e:
        print("[ERROR] Failed to delete fact:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------
# SESSION MANAGEMENT ENDPOINTS
# -------------------------
@app.get("/sessions")
async def get_all_sessions_endpoint():
    try:
        sessions = await get_sessions()
        return {"sessions": sessions}
    except Exception as e:
        print("[ERROR] Failed to get sessions:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}/history")
async def get_session_history_endpoint(session_id: str):
    try:
        history = await get_session_history(session_id)
        return {"history": history}
    except Exception as e:
        print("[ERROR] Failed to get session history:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/sessions/{session_id}")
async def delete_session_endpoint(session_id: str):
    try:
        await delete_session(session_id)
        return {"status": "success"}
    except Exception as e:
        print("[ERROR] Failed to delete session:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))
