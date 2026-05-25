# services/llm_client.py
import os
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/") + "/api/generate"
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5-coder:3b")

async def call_llm(prompt: str):
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False
            }
        )

    response.raise_for_status()
    return response.json()["response"]
