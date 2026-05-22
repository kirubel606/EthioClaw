import os
import httpx


from dotenv import load_dotenv

load_dotenv()

AI_MODEL_URL = os.getenv("OLLAMA_URL") + "/api/generate"
AI_MODEL_NAME = os.getenv("MODEL_NAME")


async def ask_model(prompt: str):

    payload = {
        "model": AI_MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    async with httpx.AsyncClient() as client:

        response = await client.post(
            AI_MODEL_URL,
            json=payload,
            timeout=60
        )

    response.raise_for_status()

    data = response.json()

    return data["response"]