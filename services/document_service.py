import csv
import os
import re
import uuid
from io import BytesIO, StringIO
from pathlib import Path
from typing import Iterable

from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from services.memory_service import create_embedding, create_embedding_async


QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
DOCUMENT_COLLECTION_NAME = os.getenv("DOCUMENT_COLLECTION_NAME", "document_knowledge")
TRADING_STRATEGY_COLLECTION_NAME = os.getenv(
    "TRADING_STRATEGY_COLLECTION_NAME",
    "trading_strategy_knowledge",
)
DOCUMENT_SCORE_THRESHOLD = float(os.getenv("DOCUMENT_SCORE_THRESHOLD", "0.45"))
DOCUMENT_CHUNK_SIZE = int(os.getenv("DOCUMENT_CHUNK_SIZE", "1400"))
DOCUMENT_CHUNK_OVERLAP = int(os.getenv("DOCUMENT_CHUNK_OVERLAP", "160"))

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


class UploadedDocumentResult(BaseModel):
    filename: str
    file_type: str
    chunks_indexed: int
    characters: int


def setup_document_collection(collection_name: str = DOCUMENT_COLLECTION_NAME):
    collections = client.get_collections().collections
    names = [c.name for c in collections]

    if collection_name not in names:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE),
        )


async def setup_document_collection_async(collection_name: str = DOCUMENT_COLLECTION_NAME):
    await run_in_threadpool(setup_document_collection, collection_name)


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _chunk_text(text: str, chunk_size: int = DOCUMENT_CHUNK_SIZE, overlap: int = DOCUMENT_CHUNK_OVERLAP) -> list[str]:
    text = _normalize_text(text)
    if not text:
        return []

    if chunk_size <= overlap:
        overlap = max(0, chunk_size // 4)

    step = max(1, chunk_size - overlap)
    chunks: list[str] = []
    for start in range(0, len(text), step):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _extract_text_from_pdf(raw_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(raw_bytes))
    pages: list[str] = []
    for page in reader.pages:
        extracted = page.extract_text() or ""
        extracted = extracted.strip()
        if extracted:
            pages.append(extracted)
    return "\n\n".join(pages)


def _decode_text(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")


def _extract_text_from_csv(raw_bytes: bytes) -> str:
    text = _decode_text(raw_bytes)
    reader = csv.reader(StringIO(text))
    rows = list(reader)
    if not rows:
        return ""

    header = rows[0]
    lines = [f"Columns: {', '.join(header)}"]

    for index, row in enumerate(rows[1:], start=1):
        if not row:
            continue
        pairs = []
        for column_index, value in enumerate(row):
            column_name = header[column_index] if column_index < len(header) else f"column_{column_index + 1}"
            pairs.append(f"{column_name}={value}")
        lines.append(f"Row {index}: " + " | ".join(pairs))

    return "\n".join(lines)


def extract_document_text(filename: str, raw_bytes: bytes) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        return _extract_text_from_pdf(raw_bytes), "pdf"
    if suffix == ".csv":
        return _extract_text_from_csv(raw_bytes), "csv"
    return _decode_text(raw_bytes), "text"


async def index_document(
    session_id: str,
    filename: str,
    raw_bytes: bytes,
    collection_name: str = DOCUMENT_COLLECTION_NAME,
    source_type: str = "document",
) -> UploadedDocumentResult:
    text, file_type = extract_document_text(filename, raw_bytes)
    normalized = _normalize_text(text)
    if not normalized:
        return UploadedDocumentResult(
            filename=filename,
            file_type=file_type,
            chunks_indexed=0,
            characters=0,
        )

    chunks = _chunk_text(normalized)
    points: list[PointStruct] = []

    for chunk_index, chunk in enumerate(chunks):
        vector = await create_embedding_async(f"{filename}\n\n{chunk}")
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "source_type": source_type,
                    "session_id": session_id,
                    "filename": filename,
                    "file_type": file_type,
                    "chunk_index": chunk_index,
                    "message": chunk,
                },
            )
        )

    if points:
        client.upsert(collection_name=collection_name, points=points)

    return UploadedDocumentResult(
        filename=filename,
        file_type=file_type,
        chunks_indexed=len(points),
        characters=len(normalized),
    )


def _format_document_point(point) -> str:
    payload = point.payload or {}
    filename = payload.get("filename", "uploaded document")
    chunk_index = payload.get("chunk_index", 0)
    message = str(payload.get("message", "")).strip().replace("\n", " ")
    snippet = message[:420]
    score = round(point.score, 3)
    return f"[score={score}] {filename} chunk {chunk_index}: {snippet}"


def retrieve_document_context_sync(
    query: str,
    session_id: str | None = None,
    limit: int = 6,
    collection_name: str = DOCUMENT_COLLECTION_NAME,
    source_type: str = "document",
) -> str:
    vector = create_embedding(query)

    query_filter = None
    if session_id:
        query_filter = Filter(
            must=[
                FieldCondition(key="source_type", match=MatchValue(value=source_type)),
                FieldCondition(key="session_id", match=MatchValue(value=session_id)),
            ]
        )

    points = client.query_points(
        collection_name=collection_name,
        query=vector,
        limit=limit,
        query_filter=query_filter,
    ).points

    filtered = [point for point in points if point.score >= DOCUMENT_SCORE_THRESHOLD]

    if not filtered and session_id:
        points = client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit,
        ).points
        filtered = [point for point in points if point.score >= DOCUMENT_SCORE_THRESHOLD]

    if not filtered:
        return ""

    filtered.sort(key=lambda item: item.score, reverse=True)
    return "\n".join(_format_document_point(point) for point in filtered)


async def retrieve_document_context(
    query: str,
    session_id: str | None = None,
    limit: int = 6,
    collection_name: str = DOCUMENT_COLLECTION_NAME,
    source_type: str = "document",
) -> str:
    return await run_in_threadpool(
        retrieve_document_context_sync,
        query,
        session_id,
        limit,
        collection_name,
        source_type,
    )
