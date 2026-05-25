from pydantic import BaseModel
from typing import List


class Part(BaseModel):
    type: str
    text: str


class ChatPayload(BaseModel):
    parts: List[Part]
    id: str
    role: str


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


class UploadedDocument(BaseModel):
    filename: str
    file_type: str
    chunks_indexed: int
    characters: int


class DocumentUploadResponse(BaseModel):
    status: str
    session_id: str
    files: list[UploadedDocument]
