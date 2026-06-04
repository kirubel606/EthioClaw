# EthioClaw

EthioClaw is a FastAPI + Next.js AI chatbot with layered memory, document retrieval, tool use, and MCP support.
It is designed to do more than answer single prompts: it keeps short-term chat state, stores structured user facts,
retrieves semantically related past turns, reads uploaded documents, and can call local or MCP-provided tools.

## What The Agent Can Do

- Answer normal chat questions directly.
- Remember the current chat session, including the latest user turns and a rolling working summary.
- Answer chat-memory questions like `what did I just ask you?` and `what were we doing?` from stored session context.
- Answer identity questions like `what is my name?` directly from stored facts.
- Extract declarative user facts such as name, age, job, preferences, and other stable details.
- Store verified facts in PostgreSQL and update them when newer information contradicts older information.
- Retrieve semantically similar prior messages from Qdrant with session-scoped search and fallback search across sessions.
- Retrieve uploaded document chunks from Qdrant and use them as context for follow-up questions.
- Run safe math evaluation for arithmetic-style requests.
- Run heuristic web search context injection for explicit search requests or time-sensitive factual questions.
- Generate DOCX, PDF, and PPTX artifacts from the model response.
- Call MCP tools from configured servers during tool-enabled reasoning.

## How The Agent Works

When a message reaches `POST /chat`, the backend follows this flow:

1. Normalize the payload from either `message` or `parts`.
2. Extract structured user facts from declarative statements.
3. Save or update those facts in PostgreSQL.
4. Detect contradictions and keep the newest fact when conflicts appear.
5. Load the session working summary and recent turns from Redis or the in-process fallback store.
6. Retrieve semantic chat memory from Qdrant.
7. Retrieve matching uploaded document chunks from the document vector store.
8. Build the final prompt from system rules, persona rules, facts, memory, documents, and tool context.
9. Handle short chat-memory questions directly from the session cache when possible.
10. Resolve identity questions directly from stored facts when possible.
11. Otherwise enqueue the model call through the Redis-backed job queue with MCP tools available.
12. Run a post-response fact verification pass against saved facts.
13. Save the user and assistant messages back into conversation storage and refresh the working summary.

## Memory Layers

### Postgres facts

Postgres stores durable facts about the user in `user_facts`.
These facts are typed as `identity`, `preference`, or `general`, and are the source of truth for stable user attributes.

### Session working memory

Redis stores the current session summary and recent turns.
If Redis is unavailable, the agent falls back to an in-process memory store for the running process.
This layer is what lets the agent answer questions about the current conversation without searching the web.

### Semantic chat memory

Qdrant stores user and assistant turns as embeddings in `chat_memory`.
When the user asks something related to previous discussion, the agent retrieves the most relevant turns from the same session first,
then falls back to cross-session search if nothing strong is found.

### Document memory

Uploaded PDFs, CSVs, and plain text files are chunked, embedded, and stored in a separate Qdrant collection.
The agent can use that content as retrieval context for follow-up questions.

## Built-In Tools

### Safe math

The agent can evaluate simple arithmetic and supported math expressions locally.
It uses a restricted AST evaluator, not arbitrary code execution.

### Web search context

The agent can fetch lightweight web search results through DuckDuckGo Lite and inject the result list into the prompt.
This only triggers for explicit search-like requests or time-sensitive factual questions.

### Artifact generation

If the request is for a document, report, PDF, or presentation, the backend can generate:

- `docx`
- `pdf`
- `pptx`

The generated file is saved under `generated/` and returned as a download link.

### Fact verification

After the model responds, the backend runs a fact-check pass against saved user facts.
This is a safety check and does not block the response by default.

## MCP Support

MCP servers are configured in `mcp_config.json` and started automatically at backend startup.
The backend supports both stdio servers and SSE servers.

### Current MCP servers

The repo currently ships with these servers in `mcp_config.json`:

- `fetch`
- `skill_manager`

### `fetch`

`fetch` is started with:

```json
{
  "command": "python",
  "args": ["-m", "mcp_server_fetch"]
}
```

This server is intended for fetch-style web content retrieval through MCP.

### `skill_manager`

`skill_manager` is started with:

```json
{
  "command": "python",
  "args": ["services/skill_mcp.py"]
}
```

It exposes these tools:

- `create_skill`
- `list_skills`
- `run_skill`

Skills are saved in the `skills/` directory as Python files and must expose a `run(...)` function.

### How MCP tool names are exposed

The backend converts MCP tool names into LangChain tools using the format:

```text
server__tool_name
```

Examples:

- `skill_manager__create_skill`
- `skill_manager__list_skills`
- `skill_manager__run_skill`

The model sees these tools in the tool-enabled reasoning loop, and `main.py` executes the matching MCP call when the model selects one.

## Queue System

The backend uses Redis as the job queue backend for expensive work.

### Queued workloads

- LLM inference for `POST /chat`
- MCP tool calls
- Document ingestion and embedding during upload

### Queue behavior

- Jobs include a `request_id` so they can be traced and correlated in logs.
- LLM jobs use a default concurrency of `3`.
- Failed jobs retry up to `3` times with exponential backoff.
- If Redis is unavailable, the queue falls back to an in-process worker queue for local development.
- The Docker worker service runs `arq services.job_queue.WorkerSettings`.

### Queue environment variables

```env
QUEUE_PREFIX=ethioclaw:queue
QUEUE_RESULT_PREFIX=ethioclaw:queue:result
QUEUE_POLL_INTERVAL=0.25
QUEUE_JOB_TIMEOUT=120
QUEUE_RETRY_LIMIT=3
LLM_QUEUE_CONCURRENCY=3
DOC_QUEUE_CONCURRENCY=1
MCP_QUEUE_CONCURRENCY=1
```

### Adding a new MCP server

Add a new entry under `mcpServers` in `mcp_config.json`.

```json
{
  "mcpServers": {
    "my_server": {
      "command": "python",
      "args": ["path/to/server.py"]
    }
  }
}
```

You can also point at an SSE endpoint:

```json
{
  "mcpServers": {
    "remote_server": {
      "url": "http://localhost:3000/sse"
    }
  }
}
```

If you add environment-specific variables for the server, include them under `env`.

## API Endpoints

### `POST /chat`

Sends a chat message to the assistant and returns:

```json
{
  "response": "..."
}
```

The backend accepts both:

- `{"message":"..."}`
- `{"parts":[{"type":"text","text":"..."}]}`

### `POST /documents/upload`

Uploads documents for session-scoped indexing into the document vector store.

### `GET /facts`

Returns all stored facts.

### `POST /facts`

Adds or overwrites a stored fact.

### `DELETE /facts/{key}`

Deletes a fact by key.

### `GET /sessions`

Returns chat sessions.

### `GET /sessions/{session_id}/history`

Returns the saved message history for a session.

### `DELETE /sessions/{session_id}`

Deletes a session and its chat history.

## Setup

### Backend environment variables

```env
OLLAMA_URL=http://host.docker.internal:11434
MODEL_NAME=qwen2.5-coder:3b
LLM_PROVIDER=ollama
OPENAI_API_KEY=
OPENAI_BASE_URL=
ANTHROPIC_API_KEY=
GROQ_API_KEY=

QDRANT_HOST=qdrant
QDRANT_PORT=6333

POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=memory
POSTGRES_USER=ai
POSTGRES_PASSWORD=ai

REDIS_URL=redis://redis:6379/0
CACHE_MAX_TURNS=12
QUEUE_BACKEND=arq

MODEL_CONTEXT_TOKENS=8192
QUEUE_PREFIX=ethioclaw:queue
QUEUE_RESULT_PREFIX=ethioclaw:queue:result
QUEUE_POLL_INTERVAL=0.25
QUEUE_JOB_TIMEOUT=120
QUEUE_RETRY_LIMIT=3
LLM_QUEUE_CONCURRENCY=3
DOC_QUEUE_CONCURRENCY=1
MCP_QUEUE_CONCURRENCY=1
MEMORY_SCORE_THRESHOLD=0.60
DOCUMENT_SCORE_THRESHOLD=0.45
DOCUMENT_CHUNK_SIZE=1400
DOCUMENT_CHUNK_OVERLAP=160

WEB_SEARCH_USER_AGENT=Mozilla/5.0 (compatible; EthioClaw/1.0)
WEB_SEARCH_TIMEOUT=20
WEB_SEARCH_LIMIT=5
```

### Frontend environment variables

```env
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000
```

### Local run

1. Start Postgres, Qdrant, Redis, and Ollama.
2. Make sure the Ollama model and embedding model are available.
3. Start the backend so it can initialize the database, memory stores, and MCP servers.
4. Start the frontend and point it at the backend URL.

### Docker

The repo includes `docker-compose.yml` and a backend `Dockerfile` for containerized setup.
Use them if you want the full stack in one place.

### Prompt budget

The backend trims prompt blocks before they reach the model:

- `working_summary` and `recent_turns` share the Redis session budget.
- `context` uses the Qdrant chat-memory budget.
- `document_context` uses the document retrieval budget.
- `tool_context` uses the tool-output budget.

The total prompt size is also capped by `MODEL_CONTEXT_TOKENS`.

### LLM providers

- `LLM_PROVIDER=ollama` uses local Ollama through `OLLAMA_URL`.
- `LLM_PROVIDER=openai` uses the OpenAI-compatible endpoint from `OPENAI_BASE_URL`.
- `LLM_PROVIDER=anthropic` uses Anthropic's Messages API.
- `LLM_PROVIDER=groq` uses Groq's OpenAI-compatible endpoint.
- The provider is selected from `LLM_PROVIDER` and all completions flow through the same async interface.
- If the configured provider is unavailable, the request fails with a structured error and the trace includes the provider name.

## Project Structure

- `main.py` wires the FastAPI app, chat route, startup tasks, and response pipeline.
- `services/memory_service.py` stores and retrieves semantic chat memory in Qdrant.
- `services/conversation_cache.py` stores the session summary and recent turns.
- `services/memory_extractor.py` extracts structured facts from user messages.
- `services/fact_db.py` manages Postgres-backed facts and chat history.
- `services/document_service.py` handles document ingestion and retrieval.
- `services/agent_tools.py` implements math, web search, memory-question handling, and artifact generation.
- `services/job_queue.py` provides Redis-backed queue execution for LLM, MCP, and document jobs.
- `services/mcp_service.py` loads and calls MCP servers.
- `services/langchain_service.py` binds MCP tools into the model reasoning loop.
- `frontend/components/ChatPage.tsx` is the main chat UI.
- `frontend/components/MemoryInspector.tsx` shows stored facts in the UI.

## Notes

- The assistant uses fail-open verification: contradictory output is logged, but the response is still returned.
- Redis is short-term working memory, not a general cache layer.
- The queue falls back to an in-process worker queue if Redis is unavailable.
- The Docker Compose worker service points at `services.job_queue.WorkerSettings`.
- Web search is heuristic and is not a browser automation feature.
- The agent does not cache full responses or embeddings.
- The current behavior depends heavily on the configured Ollama model quality and the available tools.
