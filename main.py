from fastapi import FastAPI, HTTPException, Body, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import traceback
import asyncio

from schema import (
    ChatRequest,
    ChatResponse,
    ChatPayload,
    DocumentUploadResponse,
    UploadedDocument,
    TradingProfileRequest,
    TradingProfileResponse,
    TradingSignalRequest,
    TradingSignalResponse,
    TradingTradeActionRequest,
    TradingTradeActionResponse,
    TradingTradeCloseRequest,
    TradingDashboardResponse,
)

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
    TRADING_STRATEGY_COLLECTION_NAME,
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
from services.trading_service import (
    init_trading_db,
    save_trading_profile,
    get_trading_profile,
    generate_trading_signal,
    get_trading_signal,
    save_trade_from_signal,
    reject_signal,
    close_trade,
    get_trading_dashboard,
    monitor_open_trades,
)


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
    await setup_document_collection_async(TRADING_STRATEGY_COLLECTION_NAME)
    await init_trading_db()

    # Start the background trade monitoring worker
    asyncio.create_task(trade_monitor_loop())


async def trade_monitor_loop():
    print("[SYSTEM] Starting trade monitor background worker...")
    while True:
        try:
            await monitor_open_trades()
        except Exception as e:
            print(f"[ERROR] Trade monitor loop failed: {e}")

        # Wait 60 seconds before next check
        await asyncio.sleep(60)


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
# TRADING MODE ENDPOINTS
# -------------------------
@app.post("/trading/profile", response_model=TradingProfileResponse)
async def save_trading_profile_endpoint(profile: TradingProfileRequest):
    try:
        saved = await save_trading_profile(profile)
        return TradingProfileResponse(**saved)
    except Exception as e:
        print("[ERROR] Failed to save trading profile:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trading/profile/{user_id}", response_model=TradingProfileResponse)
async def get_trading_profile_endpoint(user_id: str):
    try:
        profile = await get_trading_profile(user_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Trading profile not found")
        return TradingProfileResponse(**profile)
    except HTTPException:
        raise
    except Exception as e:
        print("[ERROR] Failed to get trading profile:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trading/dashboard/{user_id}", response_model=TradingDashboardResponse)
async def get_trading_dashboard_endpoint(user_id: str):
    try:
        dashboard = await get_trading_dashboard(user_id)
        return TradingDashboardResponse(**dashboard)
    except Exception as e:
        print("[ERROR] Failed to get trading dashboard:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trading/notifications/{user_id}")
async def get_trading_notifications_endpoint(user_id: str):
    try:
        notifications = await get_closed_trades_notifications(user_id)
        return {"notifications": notifications}
    except Exception as e:
        print("[ERROR] Failed to get notifications:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/trading/signals/generate", response_model=TradingSignalResponse)
async def generate_trading_signal_endpoint(request: TradingSignalRequest):
    try:
        result = await generate_trading_signal(
            user_id=request.user_id,
            session_id=request.session_id,
            pair=request.pair,
            timeframe=request.timeframe,
            balance=request.balance,
            message=request.message,
        )
        return TradingSignalResponse(**result)
    except Exception as e:
        print("[ERROR] Failed to generate trading signal:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/trading/trades/take", response_model=TradingTradeActionResponse)
async def take_trading_trade_endpoint(action: TradingTradeActionRequest):
    try:
        signal = await get_trading_signal(action.signal_id)
        if signal is None:
            raise HTTPException(status_code=404, detail="Signal not found")
        if signal.get("direction") == "HOLD" or not signal.get("actionable", True):
            raise HTTPException(status_code=400, detail="Non-actionable signals cannot be taken as trades")

        trade = await save_trade_from_signal(signal, action.user_id)
        return TradingTradeActionResponse(
            trade_id=trade["id"],
            signal_id=action.signal_id,
            status=trade["status"],
            message="Trade opened from signal",
        )
    except HTTPException:
        raise
    except Exception as e:
        print("[ERROR] Failed to take trading trade:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/trading/trades/reject", response_model=TradingTradeActionResponse)
async def reject_trading_trade_endpoint(action: TradingTradeActionRequest):
    try:
        signal = await reject_signal(action.signal_id)
        return TradingTradeActionResponse(
            trade_id="",
            signal_id=action.signal_id,
            status=signal.get("status", "REJECTED"),
            message="Signal rejected",
        )
    except Exception as e:
        print("[ERROR] Failed to reject trading signal:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/trading/trades/{trade_id}/close")
async def close_trading_trade_endpoint(trade_id: str, request: TradingTradeCloseRequest):
    try:
        trade = await close_trade(trade_id, request.outcome, request.pnl)
        return {"status": "success", "trade": trade}
    except Exception as e:
        print("[ERROR] Failed to close trading trade:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/trading/strategies/upload", response_model=DocumentUploadResponse)
async def upload_trading_strategies(
    session_id: str = Form("default"),
    files: list[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    indexed_files: list[UploadedDocument] = []

    try:
        trading_session_id = f"trading:{session_id}"
        for upload in files:
            raw_bytes = await upload.read()
            result = await index_document(
                trading_session_id,
                upload.filename,
                raw_bytes,
                collection_name=TRADING_STRATEGY_COLLECTION_NAME,
                source_type="trading_strategy",
            )
            indexed_files.append(UploadedDocument(**result.model_dump()))

        uploaded_names = ", ".join(item.filename for item in indexed_files) or "files"
        indexed_count = sum(item.chunks_indexed for item in indexed_files)
        confirmation_text = f"Indexed trading strategy files: {uploaded_names}"
        summary_text = f"Indexed {len(indexed_files)} trading strategy files with {indexed_count} document chunks."
        await save_chat_message(trading_session_id, "system", confirmation_text)
        await append_turn(trading_session_id, "system", confirmation_text)
        await refresh_summary(trading_session_id, summary_text, confirmation_text)

        return DocumentUploadResponse(
            status="success",
            session_id=session_id,
            files=indexed_files,
        )
    except Exception as e:
        print("[ERROR] Failed to upload trading strategies:", repr(e))
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
