from services.llm_client import call_llm

async def ask_model(prompt: str):
    return await call_llm(prompt)