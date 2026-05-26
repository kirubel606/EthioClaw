import os
import uuid
from datetime import datetime
from ollama import Client
from fastapi.concurrency import run_in_threadpool

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct
)

QDRANT_HOST      = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT      = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME  = "chat_memory"
OLLAMA_URL       = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Score threshold — results below this are too weak to be worth injecting
SCORE_THRESHOLD  = float(os.getenv("MEMORY_SCORE_THRESHOLD", "0.60"))


# -------------------------
# Clients
# -------------------------
ollama_client = Client(host=OLLAMA_URL)

client = QdrantClient(
    host=QDRANT_HOST,
    port=QDRANT_PORT
)


# -------------------------
# COLLECTION SETUP
# -------------------------
def setup_collection():
    collections = client.get_collections().collections
    names = [c.name for c in collections]

    if COLLECTION_NAME not in names:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=768,
                distance=Distance.COSINE
            )
        )


async def setup_collection_async():
    await run_in_threadpool(setup_collection)


# -------------------------
# EMBEDDINGS
# -------------------------
def create_embedding(text: str):
    response = ollama_client.embeddings(
        model="nomic-embed-text",
        prompt=text
    )
    return response["embedding"]


async def create_embedding_async(text: str):
    return await run_in_threadpool(create_embedding, text)


# -------------------------
# SAVE MESSAGE
# -------------------------
def save_message_sync(role: str, message: str, session_id: str = "default"):
    embedding = create_embedding(message)

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "role":    role,
                    "message": message,
                    "session_id": session_id,
                    "created_at": datetime.utcnow().isoformat()
                }
            )
        ]
    )


async def save_message(role: str, message: str, session_id: str = "default"):
    await run_in_threadpool(save_message_sync, role, message, session_id)


# -------------------------
# RETRIEVE CONTEXT (score-filtered + ranked + session-scoped)
# -------------------------
def retrieve_context_sync(query: str, session_id: str | None = None, limit: int = 5) -> str:
    embedding = create_embedding(query)

    from qdrant_client.models import Filter, FieldCondition, MatchValue

    query_filter = None
    if session_id:
        query_filter = Filter(
            must=[
                FieldCondition(key="session_id", match=MatchValue(value=session_id))
            ]
        )

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=embedding,
        query_filter=query_filter,
        limit=limit
    ).points

    # Filter: only keep results above the score threshold
    filtered = [r for r in results if r.score >= SCORE_THRESHOLD]

    if not filtered:
        # If no session-specific results, try searching all sessions as a fallback
        if session_id:
             results = client.query_points(
                collection_name=COLLECTION_NAME,
                query=embedding,
                limit=limit
            ).points
             filtered = [r for r in results if r.score >= SCORE_THRESHOLD]
        
        if not filtered:
            print(f"ℹ️  No semantic memory above threshold {SCORE_THRESHOLD} for query.")
            return ""

    # Sort by score descending (highest relevance first)
    filtered.sort(key=lambda r: r.score, reverse=True)

    context_lines = []
    for result in filtered:
        role    = result.payload.get("role", "unknown")
        message = result.payload.get("message", "")
        score   = round(result.score, 3)
        context_lines.append(f"[score={score}] {role}: {message}")

    return "\n".join(context_lines)


async def retrieve_context(query: str, session_id: str | None = None, limit: int = 5) -> str:
    return await run_in_threadpool(retrieve_context_sync, query, session_id, limit)
