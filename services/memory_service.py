import os
import uuid
from ollama import Client
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct
)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

COLLECTION_NAME = "chat_memory"
OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434"
)

ollama_client = Client(
    host=OLLAMA_URL
)
client = QdrantClient(
    host=QDRANT_HOST,
    port=QDRANT_PORT
)


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


def create_embedding(text: str):

    response = ollama_client.embeddings(
        model="nomic-embed-text",
        prompt=text
    )

    return response["embedding"]


def save_message(role: str, message: str):

    embedding = create_embedding(message)

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "role": role,
                    "message": message
                }
            )
        ]
    )


def retrieve_context(query: str, limit=5):

    embedding = create_embedding(query)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=embedding,
        limit=limit
    ).points

    context = []

    for result in results:

        role = result.payload["role"]
        message = result.payload["message"]

        context.append(
            f"{role}: {message}"
        )

    return "\n".join(context)