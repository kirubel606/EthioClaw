from fastapi import FastAPI, HTTPException

from schema import ChatRequest, ChatResponse
from services.ai_service import ask_model

from services.memory_service import (
    setup_collection,
    retrieve_context,
    save_message
)

app = FastAPI()
setup_collection()

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):

    try:

        context = retrieve_context(
            request.message
        )

        final_prompt = f"""
You are a helpful AI assistant.

Previous conversation context:
{context}

Current User Message:
{request.message}

Assistant:
"""

        ai_response = await ask_model(
            final_prompt
        )

        save_message(
            "user",
            request.message
        )

        save_message(
            "assistant",
            ai_response
        )

        return ChatResponse(
            response=ai_response
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )