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