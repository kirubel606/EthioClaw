# EthioClaw

EthioClaw is a full-stack AI chatbot project with a FastAPI backend and a Next.js frontend. The system is designed to do more than just answer prompts: it extracts user facts, stores them in structured memory, retrieves related conversation context, detects contradictions, and verifies responses against saved ground truth before returning an answer.

## What The Backend Does

The backend is the reasoning and orchestration layer. It receives chat messages, turns them into structured memory, asks the LLM for a response, and then checks that response against verified user facts.

### Core backend responsibilities

1. Accept chat requests from the frontend through `POST /chat`.
2. Extract typed facts from user statements using the LLM.
3. Store facts in Postgres with metadata such as `memory_type`, `confidence`, `source`, and `updated_at`.
4. Detect contradictions between new facts and already stored facts.
5. Retrieve related conversation history from Qdrant using embeddings.
6. Ingest uploaded PDFs, TXT files, and CSVs into a document vector store for automatic RAG.
7. Build a layered prompt that separates system rules, persona rules, user facts, uploaded document context, and recent context.
8. Call the configured Ollama model to generate the assistant response.
9. Run a post-response hallucination check against verified facts.
10. Persist the conversation turn into vector memory for future retrieval.

### Backend architecture

The backend is built with:

- `FastAPI` for HTTP routing and request validation.
- `Pydantic` for typed request and response models.
- `asyncpg` for asynchronous PostgreSQL access.
- `qdrant-client` for semantic memory storage and retrieval.
- `ollama` for local model inference.
- `httpx` for calling the model endpoint.
- `uvicorn` for development and deployment serving.
- `python-dotenv` for environment configuration.

### Memory and reasoning flow

When a chat message arrives, the backend follows a strict pipeline:

1. The message is normalized from either the legacy `message` payload or the newer `parts` payload.
2. The extractor prompts the LLM to return only real declarative user facts.
3. Facts are classified as `identity`, `preference`, or `general`.
4. Each extracted fact is compared against stored facts in Postgres.
5. If a contradiction is found, the default policy keeps the newest fact.
6. Identity facts are separated from general facts so the model can trust them more.
7. Similar past messages are fetched from Qdrant and ranked by score.
8. The prompt builder inserts system instructions, persona instructions, user profile blocks, and conversation history into one final prompt.
9. The selected LLM generates a response.
10. The verifier checks the response against verified facts and logs any direct contradictions.
11. Both user and assistant messages are saved back into semantic memory.

## What The Frontend Does

The frontend is the user-facing client built with Next.js. It provides the chat interface, the memory inspector, and the connection layer that forwards messages to the backend.

### Frontend responsibilities

- Render the chat UI and message history.
- Send user messages to the backend chat endpoint.
- Show loading and thinking states while the model is generating a response.
- Upload PDF, TXT, and CSV files so they are indexed into the agent's RAG store.
- Provide a clear-chat action for resetting the local conversation view.
- Display a memory inspector for stored facts.
- Allow adding and deleting memory items from the inspector UI.
- Provide a polished Rick Sanchez themed visual experience.

### Frontend architecture

The frontend uses:

- `Next.js` for the app router and server routes.
- `React 19` for the component layer.
- `TypeScript` for typed frontend code.
- `Tailwind CSS` for styling.
- `Radix UI` and shadcn-style components for accessible UI primitives.
- `sonner` for toast notifications.
- `lucide-react` for icons.
- `next-themes` for theme handling.
- `Vercel Analytics` for analytics support.

### Frontend implementation details

The main chat page is implemented in `frontend/components/ChatPage.tsx` and does the following:

- Keeps local message state for the conversation.
- Sends `POST` requests to `${NEXT_PUBLIC_BACKEND_URL}/chat`.
- Renders user and assistant messages through reusable message components.
- Shows an animated typing indicator while awaiting the backend.
- Auto-scrolls the message list as new content arrives.
- Opens a sidebar memory inspector when requested.

The frontend also includes API routes under `frontend/app/api/`:

- `POST /api/chat` forwards chat messages to the backend.
- `GET /api/facts`, `POST /api/facts`, and `DELETE /api/facts/[id]` currently manage a local file-backed facts store.

That means the current frontend contains a lightweight local memory prototype in addition to the backend’s Postgres-backed facts system. The chat UI talks to the FastAPI backend, while the local fact routes are used by the frontend memory panel.

## Tools And Services Used

### Backend tools

- `FastAPI` for the API surface.
- `PostgreSQL` for structured ground-truth user facts.
- `Qdrant` for semantic memory and similarity search.
- `Redis` for short-term working memory and cached conversation summaries.
- `Ollama` for local LLM inference and embeddings.
- `Nomic Embed Text` via Ollama for vector embeddings.
- `Pydantic` for typed schema validation.
- `asyncpg` for database pooling and queries.

### Frontend tools

- `Next.js` and `React` for the interface.
- `TypeScript` for safer component and API code.
- `Tailwind CSS` for layout and styling.
- `Radix UI` for accessible primitives.
- `shadcn/ui` style components for faster UI composition.
- `Vercel Analytics` for usage tracking.

### Deployment and runtime tools

- `Docker` and `docker-compose` for containerized setup.
- Environment variables for backend and frontend configuration.
- CORS middleware in FastAPI so the frontend can call the backend during development.

## What Was Accomplished

This project now includes a working memory-aware chatbot pipeline instead of a simple prompt-and-response app.

### Completed backend improvements

- Prompt hierarchy was hardened so system rules and persona rules are separated and applied in a strict order.
- The database layer was upgraded to a typed fact schema instead of a single unstructured key-value store.
- Memory retrieval now uses Qdrant scores and filters out weak semantic matches.
- Fact extraction is typed and constrained, which reduces false memory writes from vague or placeholder output.
- Contradiction detection is built in so the assistant can notice when the user changes a previously stored fact.
- The default resolution strategy is explicit: newest fact wins.
- A hallucination verification pass runs after generation to catch direct contradictions in the final response.
- The backend exposes clean facts-management endpoints for inspection and manual maintenance.
- A Redis-backed working-memory cache now stores the current task summary and recent turns so the agent can answer questions like "what were we doing?"
- Tool support was added for safe math evaluation, web search context injection, and on-demand DOCX, PDF, and PPTX generation.
- Uploaded PDF, TXT, and CSV files are chunked, embedded, and stored in Qdrant so they participate in retrieval automatically.

### Completed frontend improvements

- A full chat interface is in place with message rendering, avatars, loading states, and auto-scroll behavior.
- The user can clear the visible chat session without touching server-side memory.
- The memory inspector shows stored facts and supports add/delete interactions.
- The UI is themed around the Rick Sanchez persona with custom visual styling instead of a generic chat layout.
- The frontend is wired to the backend through a configurable environment variable, so it can run locally or behind Docker.

### Product outcome

The result is a chatbot system that:

- Remembers verified user facts.
- Distinguishes identity facts from general facts.
- Retrieves related context from prior turns.
- Responds with a consistent persona.
- Detects and logs contradictions.
- Verifies outputs against saved facts.
- Presents the experience through a usable web interface.

## Backend API

### `POST /chat`

Sends a message to the assistant and returns the model response.

Example request:

```json
{
  "message": "Hello, my name is Rick and I am a 70 year old scientist."
}
```

Example response:

```json
{
  "response": "Wubba lubba dub dub! Nice to meet you, Rick."
}
```

### `GET /facts`

Returns all stored facts from Postgres.

### `POST /facts`

Manually inserts or overwrites a fact in the ground-truth store.

### `DELETE /facts/{key}`

Deletes a fact by key.

## Environment Variables

### Backend

```env
OLLAMA_URL=http://host.docker.internal:11434
MODEL_NAME=qwen2.5-coder:3b

QDRANT_HOST=qdrant
QDRANT_PORT=6333

POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=memory
POSTGRES_USER=ai
POSTGRES_PASSWORD=ai

APP_ENV=development
```

### Frontend

```env
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000
```

## Project Structure

- `main.py` wires the FastAPI app, startup tasks, chat route, and fact routes.
- `services/ai_service.py` sends prompts to the model layer.
- `services/llm_client.py` calls Ollama.
- `services/memory_service.py` stores and retrieves semantic conversation memory in Qdrant.
- `services/fact_db.py` manages Postgres-backed user facts.
- `services/memory_extractor.py` turns freeform user input into structured memory facts.
- `services/contradiction_detector.py` compares new facts to stored facts and resolves conflicts.
- `services/fact_verifier.py` checks assistant responses for factual contradictions.
- `frontend/components/ChatPage.tsx` is the main client interface.
- `frontend/components/MemoryInspector.tsx` handles the facts sidebar.
- `frontend/app/api/chat/route.ts` forwards chat requests to the backend.
- `frontend/app/api/facts/route.ts` and `frontend/app/api/facts/[id]/route.ts` manage the local file-backed memory prototype.

## Notes

- The assistant persona is intentionally opinionated and Rick-themed.
- The backend uses a fail-open verification policy: hallucinations are logged, but the response is still returned.
- The frontend memory inspector currently uses its own file-based API routes, which are separate from the backend Postgres facts store.
