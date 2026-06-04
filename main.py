from fastapi import FastAPI, HTTPException, Body, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import base64
import traceback
import re
import json
import time
import uuid

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
from services.agent_tools import (
    build_tool_bundle,
    generate_artifact,
    GENERATED_DIR,
    resolve_identity_question,
    resolve_memory_question,
    sanitize_untrusted_text,
)
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
from services.json_utils import extract_json_blocks
from services.job_queue import (
    job_queue,
    LLM_QUEUE_CONCURRENCY,
    DOC_QUEUE_CONCURRENCY,
    MCP_QUEUE_CONCURRENCY,
)
from services.llm_provider import DEFAULT_PROVIDER_NAME


from services.mcp_service import mcp_manager
from services.langchain_service import langchain_service
from services.llm_client import MODEL_NAME as LLM_MODEL_NAME
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage


def _serialize_message(message):
    message_type = getattr(message, "type", message.__class__.__name__.replace("Message", "").lower())
    if message_type == "ai":
        message_type = "assistant"
    elif message_type == "human":
        message_type = "user"
    payload = {
        "role": message_type,
        "content": getattr(message, "content", ""),
    }
    tool_call_id = getattr(message, "tool_call_id", None)
    if tool_call_id:
        payload["tool_call_id"] = tool_call_id
    tool_calls = getattr(message, "tool_calls", None)
    if not tool_calls:
        additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
        tool_calls = additional_kwargs.get("tool_calls")
    if tool_calls:
        payload["tool_calls"] = tool_calls
    return payload


def _deserialize_messages(serialized_messages: list[dict]) -> list:
    messages = []
    for item in serialized_messages:
        role = item.get("role", "user")
        content = item.get("content", "")
        if role == "system":
            messages.append(SystemMessage(content=content))
        elif role in {"assistant", "ai"}:
            tool_calls = item.get("tool_calls", [])
            if tool_calls:
                messages.append(AIMessage(content=content, additional_kwargs={"tool_calls": tool_calls}))
            else:
                messages.append(AIMessage(content=content))
        elif role == "tool":
            messages.append(ToolMessage(content=content, tool_call_id=item.get("tool_call_id", "queued_tool")))
        else:
            messages.append(HumanMessage(content=content))
    return messages


async def _llm_inference_job(payload: dict) -> dict:
    messages = _deserialize_messages(payload.get("messages", []))
    mcp_tools = payload.get("mcp_tools", [])
    response = await langchain_service.call_llm_with_tools(messages, mcp_tools, request_id=payload.get("request_id"))
    return {
        "content": response.content,
        "tool_calls": getattr(response, "tool_calls", []),
    }


async def _mcp_tool_job(payload: dict) -> dict:
    server_name = payload["server_name"]
    tool_name = payload["tool_name"]
    arguments = payload.get("arguments", {})
    result = await mcp_manager.call_tool(server_name, tool_name, arguments)
    return {"result": sanitize_untrusted_text(result, 4000)}


async def _document_ingestion_job(payload: dict) -> dict:
    session_id = payload["session_id"]
    filename = payload["filename"]
    raw_bytes = base64.b64decode(payload.get("raw_bytes", "").encode("ascii"))
    result = await index_document(session_id, filename, raw_bytes)
    return result.model_dump()


job_queue.register_handler("llm_inference", _llm_inference_job, concurrency=LLM_QUEUE_CONCURRENCY)
job_queue.register_handler("mcp_tool", _mcp_tool_job, concurrency=MCP_QUEUE_CONCURRENCY)
job_queue.register_handler("document_ingestion", _document_ingestion_job, concurrency=DOC_QUEUE_CONCURRENCY)

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
    await mcp_manager.start_servers()
    await job_queue.start()


@app.on_event("shutdown")
async def shutdown():
    await job_queue.stop()


# -------------------------
# CHAT ENDPOINT
# -------------------------
@app.post("/chat", response_model=ChatResponse)
async def chat(http_request: Request, request: dict = Body(...)):
    """Accept both the new ChatPayload format and the legacy simple format.
    The function extracts a unified `request_message` string for downstream processing.
    """
    request_id = str(uuid.uuid4())
    request_started_at = time.perf_counter()
    trace = {
        "request_id": request_id,
        "session_id": "unknown",
        "intent": "chat",
        "model": LLM_MODEL_NAME,
        "provider": DEFAULT_PROVIDER_NAME,
        "stages": {
            "fact_extraction": {"facts_found": 0, "latency_ms": 0},
            "memory_retrieval": {"postgres": 0, "redis_turns": 0, "qdrant_chat": 0, "qdrant_docs": 0},
            "context_assembly": {"total_tokens": 0, "trimmed": False, "dropped_sources": []},
            "execution": {"mode": "llm", "latency_ms": 0, "tool_calls": []},
            "memory_update": {"redis": False, "qdrant": False, "postgres": False},
        },
        "errors": [],
        "total_latency_ms": 0,
    }

    # New format: parts list
    if "parts" in request and isinstance(request["parts"], list):
        request_message = "".join(part.get("text", "") for part in request["parts"])
    # Legacy format: simple message field
    elif "message" in request:
        request_message = request["message"]
    else:
        trace["errors"].append("Invalid request payload")
        trace["total_latency_ms"] = int((time.perf_counter() - request_started_at) * 1000)
        print(json.dumps(trace, ensure_ascii=False))
        return JSONResponse(
            status_code=400,
            content={
                "error": "Invalid request payload",
                "request_id": request_id,
            },
        )

    session_id = str(request.get("session_id") or request.get("conversation_id") or "default")
    trace["session_id"] = session_id

    try:
        # ── STEP 1: Extract typed facts from the user message ───────────────
        fact_started_at = time.perf_counter()
        extracted = await extract_facts(request_message)
        new_facts = extracted.facts
        trace["stages"]["fact_extraction"]["facts_found"] = len(new_facts)
        trace["stages"]["fact_extraction"]["latency_ms"] = int((time.perf_counter() - fact_started_at) * 1000)

        # ── STEP 2: Contradiction detection ─────────────────────────────────
        existing_flat    = await get_facts()
        contradictions = await detect_contradictions(new_facts, existing_flat)

        if contradictions:
            override_facts = resolve_prefer_newest(contradictions)
            for fact in override_facts:
                await save_fact(fact.key, fact.value, fact.memory_type.value, fact.confidence, fact.source)
            override_keys = {f.key for f in override_facts}
            for fact in new_facts:
                if fact.key not in override_keys and fact.key not in existing_flat:
                    await save_fact(fact.key, fact.value, fact.memory_type.value, fact.confidence, fact.source)
        else:
            for fact in new_facts:
                await save_fact(fact.key, fact.value, fact.memory_type.value, fact.confidence, fact.source)

        # ── STEP 3: Build Context Blocks ───────────────────────────────
        identity_facts_dict = await get_identity_facts()
        all_facts_dict      = await get_facts()
        identity_block = "\n".join(f"  {k}: {v}" for k, v in identity_facts_dict.items())
        general_block = "\n".join(f"  {k}: {v}" for k, v in all_facts_dict.items() if k not in identity_facts_dict)
        trace["stages"]["memory_retrieval"]["postgres"] = len(all_facts_dict)

        working_summary = await get_summary(session_id)
        recent_turns = await get_recent_turns(session_id, limit=8)
        recent_turn_block = "\n".join(f"  {turn['role']}: {turn['content']}" for turn in recent_turns)
        trace["stages"]["memory_retrieval"]["redis_turns"] = len(recent_turns)

        tool_bundle = None
        identity_memory_answer = resolve_identity_question(request_message, identity_facts_dict)
        direct_memory_answer = resolve_memory_question(
            request_message,
            recent_turns=recent_turns,
            working_summary=working_summary,
        )

        if identity_memory_answer:
            final_answer = identity_memory_answer
            trace["stages"]["execution"]["mode"] = "identity_query"
            trace["stages"]["execution"]["latency_ms"] = int((time.perf_counter() - request_started_at) * 1000)
        elif direct_memory_answer:
            final_answer = direct_memory_answer
            trace["stages"]["execution"]["mode"] = "memory_query"
            trace["stages"]["execution"]["latency_ms"] = int((time.perf_counter() - request_started_at) * 1000)
        else:
            prompt_started_at = time.perf_counter()
            tool_bundle = await build_tool_bundle(request_message)
            context = await retrieve_context(request_message, session_id=session_id, limit=8)
            document_context = await retrieve_document_context(request_message, session_id=session_id, limit=8)
            trace["stages"]["memory_retrieval"]["qdrant_chat"] = len([line for line in context.splitlines() if line.strip()])
            trace["stages"]["memory_retrieval"]["qdrant_docs"] = len([line for line in document_context.splitlines() if line.strip()])

            # ── STEP 4: LangChain Reasoning Loop ──────────────────────────────────────
            mcp_tools = await mcp_manager.list_tools()

            prompt_assembly = build_prompt(
                user_message=request_message,
                identity_facts=identity_block,
                general_facts=general_block,
                context=context,
                document_context=document_context,
                recent_turns=recent_turn_block,
                recent_turn_records=recent_turns,
                working_summary=working_summary,
                tool_context=tool_bundle.context,
                mcp_tools=""
            )
            system_content = prompt_assembly.prompt
            trace["stages"]["context_assembly"]["total_tokens"] = prompt_assembly.total_tokens
            trace["stages"]["context_assembly"]["trimmed"] = prompt_assembly.trimmed
            trace["stages"]["context_assembly"]["dropped_sources"] = prompt_assembly.dropped_sources

            messages = [
                SystemMessage(content=system_content),
                HumanMessage(content=request_message)
            ]
            serialized_messages = [_serialize_message(message) for message in messages]

            max_iterations = 8 # Slightly more headroom for complex tasks
            final_answer = ""
            tool_calls_seen: list[str] = []

            for i in range(max_iterations):
                llm_result = await job_queue.enqueue(
                    "llm_inference",
                    {
                        "request_id": request_id,
                        "messages": serialized_messages,
                        "mcp_tools": mcp_tools,
                    },
                )
                ai_content = llm_result.get("content", "")
                tool_calls = llm_result.get("tool_calls", [])

                # 1. Detect tool calls (Native + Robust Fallback)
                if not tool_calls and "{" in ai_content:
                    json_blocks = extract_json_blocks(ai_content)
                    for data in json_blocks:
                        t_name = None
                        # Support multiple JSON schemas the LLM might output
                        if "server" in data and "tool" in data:
                            t_name = f"{data['server']}__{data['tool']}"
                        elif "name" in data:
                            t_name = data["name"]
                        elif "tool" in data:
                            t_name = data["tool"]

                        if t_name:
                            # Auto-fix missing server prefix
                            if "__" not in t_name:
                                for mt in mcp_tools:
                                    if mt["name"] == t_name:
                                        t_name = f"{mt['server']}__{t_name}"
                                        break

                            tool_calls.append({
                                "name": t_name,
                                "args": data.get("arguments", data.get("args", data.get("parameters", {}))),
                                "id": f"fb_{i}_{len(tool_calls)}"
                            })

                # 2. If NO tools detected, this turn IS the final answer.
                if not tool_calls:
                    # STRIP ANY JSON FROM FINAL ANSWER (Last line of defense)
                    # We remove anything from the first '{' to the last '}'
                    content = ai_content
                    if "{" in content and "}" in content:
                        # Greedily remove everything between the first { and last }
                        content = re.sub(r"\{.*\}", "", content, flags=re.DOTALL).strip()

                    # If after stripping we have nothing left, use the original message
                    final_answer = content or ai_content
                    break

                # 3. If tools detected, execute and CONTINUE the loop.
                messages.append(AIMessage(content=ai_content, tool_calls=tool_calls))
                serialized_messages.append(_serialize_message(messages[-1]))

                for tool_call in tool_calls:
                    name = tool_call["name"]
                    server_name, tool_name = name.split("__", 1) if "__" in name else ("internal", name)

                    print(f"[REASONING] Step {i+1}: Calling {server_name}.{tool_name}")
                    tool_result = await job_queue.enqueue(
                        "mcp_tool",
                        {
                            "request_id": request_id,
                            "server_name": server_name,
                            "tool_name": tool_name,
                            "arguments": tool_call["args"],
                        },
                    )
                    tool_result = tool_result.get("result", "")
                    tool_calls_seen.append(name)

                    messages.append(ToolMessage(
                        content=tool_result,
                        tool_call_id=tool_call.get("id", "fallback_id")
                    ))
                    serialized_messages.append(_serialize_message(messages[-1]))

                # Reset final_answer for safety
                final_answer = ""

            if not final_answer:
                final_answer = messages[-1].content if messages else "I encountered an error while processing your request."

            trace["stages"]["execution"]["mode"] = "hybrid" if tool_calls_seen else "llm"
            trace["stages"]["execution"]["tool_calls"] = tool_calls_seen
            trace["stages"]["execution"]["latency_ms"] = int((time.perf_counter() - prompt_started_at) * 1000)

        # ── STEP 5: Post-processing ─────────────────────────────────────────
        verification = await verify_response(final_answer, all_facts_dict)
        if not verification.get("valid", True):
            print(f"[HALLUCINATION DETECTED] — violations: {verification.get('violations', [])}")

        ai_response = final_answer

        if tool_bundle and tool_bundle.artifact_kind:
            artifact_title = tool_bundle.artifact_title or "generated-content"
            artifact_path = generate_artifact(tool_bundle.artifact_kind, artifact_title, final_answer)
            artifact_url = f"{str(http_request.base_url).rstrip('/')}/generated/{artifact_path.name}"
            ai_response = f"{final_answer}\n\nGenerated file: [Download the presentation]({artifact_url})"

        # ── STEP 6: Save conversation ───────────────────────────────────────
        await save_message("user", request_message, session_id=session_id)
        await save_message("assistant", ai_response, session_id=session_id)
        await save_chat_message(session_id, "user", request_message)
        await save_chat_message(session_id, "assistant", ai_response)
        await append_turn(session_id, "user", request_message)
        await append_turn(session_id, "assistant", ai_response)
        await refresh_summary(session_id, request_message, ai_response)
        trace["stages"]["memory_update"] = {"redis": True, "qdrant": True, "postgres": True}
        trace["total_latency_ms"] = int((time.perf_counter() - request_started_at) * 1000)
        print(json.dumps(trace, ensure_ascii=False))

        return ChatResponse(response=ai_response)

    except Exception as e:
        print("[ERROR] ", repr(e))
        print(traceback.format_exc())
        trace["errors"].append(str(e) or "Internal Server Error")
        trace["total_latency_ms"] = int((time.perf_counter() - request_started_at) * 1000)
        print(json.dumps(trace, ensure_ascii=False))

        return JSONResponse(
            status_code=500,
            content={
                "error": str(e) or "Internal Server Error",
                "request_id": request_id,
            },
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
            result = await job_queue.enqueue(
                "document_ingestion",
                {
                    "request_id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "filename": upload.filename,
                    "raw_bytes": base64.b64encode(raw_bytes).decode("ascii"),
                },
            )
            indexed_files.append(UploadedDocument(**result))

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
