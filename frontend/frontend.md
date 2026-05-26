# Cognitive Chatbot Frontend Integration Guide

This document provides a comprehensive overview of the backend API, the required environment variables, and the guidelines for building a frontend (such as the Reflex web client) to integrate with this cognitive chatbot system.

---

## 1. System Architecture Overview

The backend acts as an orchestrator for a **Cognitive Memory System** consisting of three layers:
1. **Short-Term Context & Semantic Memory (Vector Search)**: Managed via Qdrant vector database.
2. **Ground Truth Facts & User Profile (Relational)**: Managed via Postgres database.
3. **LLM Engine**: Managed via Ollama.

### Lifecycle of a Chat Message
1. **Fact Extraction**: When a user sends a message, the backend extracts facts (`MemoryFact`) from the message.
2. **Contradiction Detection**: Extracted facts are compared against existing database facts. If a contradiction is detected (e.g., name changed from "Bob" to "Robert"), the default resolution strategy overrides the old fact.
3. **Retrieval**: Semantically relevant chat history context is pulled from Qdrant.
4. **Structured Context Injection**: User profile facts (broken into high-trust Identity facts and secondary General facts) and Qdrant context are compiled into a layered system prompt.
5. **LLM Inference**: The LLM responds.
6. **Hallucination Verification**: The LLM's response is validated against the Postgres ground truth facts. Any hallucinations/violations are logged.
7. **Persistence**: The conversation turn is saved to the Qdrant database.

---

## 2. Environment Variables (.env)

The application requires specific configurations to locate the databases, LLM engines, and identify the environment.

### Backend Configurations (`env.example`)
Create a `.env` file in your root folder using the following schema:

```env
# Ollama Local LLM Configuration
OLLAMA_URL=http://host.docker.internal:11434
MODEL_NAME=qwen2.5-coder:3b

# Vector Search Database
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# Relational Ground Truth Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=memory
POSTGRES_USER=ai
POSTGRES_PASSWORD=ai

# Application Mode
APP_ENV=development
```

### Frontend Configurations
For the frontend (e.g., inside the `frontend/` directory), you need a variable referencing the running backend:

```env
BACKEND_URL=http://backend:8000
```
*(Replace `backend:8000` with `localhost:8000` or the corresponding IP/domain depending on whether you run locally or inside a Docker network).*

---

## 3. Backend API Endpoints

### 3.1. Submit Chat Message
* **Endpoint**: `POST /chat`
* **Description**: Sends a message to the AI chatbot, processes memories, extracts facts, checks for hallucinations, and returns the response.
* **Content-Type**: `application/json`

#### Request Payload
```json
{
  "message": "Hello, my name is John and I am a software engineer."
}
```

#### Response Payload
```json
{
  "response": "Hello John! It's great to meet a software engineer. How can I assist you today?"
}
```

---

### 3.2. Fetch All User Facts
* **Endpoint**: `GET /facts`
* **Description**: Returns all extracted or manually injected facts stored in the Postgres database.
* **Response Format**: `application/json`

#### Response Payload
```json
{
  "facts": [
    {
      "key": "name",
      "value": "John",
      "memory_type": "identity",
      "confidence": 1.0,
      "source": "user"
    },
    {
      "key": "occupation",
      "value": "software engineer",
      "memory_type": "identity",
      "confidence": 1.0,
      "source": "user"
    }
  ]
}
```

---

### 3.3. Inject/Update Fact Manually
* **Endpoint**: `POST /facts`
* **Description**: Manually inserts or overwrites a fact in the ground truth Postgres database.
* **Content-Type**: `application/json`

#### Request Payload
```json
{
  "key": "favorite_drink",
  "value": "Coffee",
  "memory_type": "preference",
  "confidence": 0.95,
  "source": "user"
}
```
* **Memory Types**: `"identity" | "preference" | "general"`
* **Confidence**: Float range `0.0` to `1.0`
* **Source**: `str` (typically `"user"`)

#### Response Payload
```json
{
  "status": "success"
}
```

---

### 3.4. Delete Fact
* **Endpoint**: `DELETE /facts/{key}`
* **Description**: Deletes a specific fact by its key name.
* **Path Parameter**: `key` (e.g. `favorite_drink`)
* **Response Format**: `application/json`

#### Response Payload
```json
{
  "status": "success"
}
```

---

## 4. Frontend Component & View Requirements

To build a complete controller interface, your frontend should implement these key areas:

### 1. Header Control Bar
* Displays connection status.
* A "Clear Chat" button to reset the local chat UI.

### 2. Chat Section (Split View - 60% Width)
* **Message Feed**: Displays chronological dialogue. Renders distinct user and assistant avatars.
* **Loading State**: An indicator/spinner showing when the AI is processing/thinking.
* **Input Bar**: A text input field with a submit button. It should submit the request on click or when the `Enter` key is pressed.

### 3. Ground Truth Memory Inspector (Split View - 40% Width)
* **Facts List**: A structured table or list showing all user facts retrieved from Postgres (`GET /facts`).
  * Shows: **Key**, **Value**, **Type** (color-coded badges based on class/trust level), **Confidence**, and **Actions**.
  * Actions include **Edit** (triggers an edit modal or inline edit) and **Delete** (triggers a `DELETE /facts/{key}` request).
* **Manual Injector**: A form at the bottom allowing rapid fact insertion:
  * Input for Key and Value.
  * Selection dropdown for Type (`identity`, `preference`, `general`).
  * Input/Slider for Confidence (`0.0 - 1.0`).
  * Button to submit the `POST /facts` request.

---

## 5. Development Pitfalls & Best Practices (Reflex-Specific)

If you are developing this frontend using **Reflex**, keep the following best practices in mind to avoid common compilation bugs:

### A. Explicit Setter Handlers (Reflex 0.9+)
Reflex 0.9 has deprecated and disabled auto-generated state setters (`set_VARNAME`) by default. You must explicitly define event handlers in your state classes:
```python
class State(rx.State):
    current_message: str = ""

    @rx.event
    def set_current_message(self, val: str):
        self.current_message = val
```
Do not rely on the `state_auto_setters=True` configuration flag, as it will be removed in version 1.0.

### B. Use `rx.cond` for Frontend Logic
Do not use standard Python ternary operations (`value if condition else fallback`) when rendering state-dependent attributes (like color schemes, borders, and text values) or inside event loops (like `rx.foreach`). Standard Python logic executes once at compile time, leading to `VarTypeError` or static results. Instead, use `rx.cond`:
```python
# Correct
color_scheme=rx.cond(item["memory_type"] == "identity", "orange", "blue")

# Incorrect (Will crash compilation)
color_scheme="orange" if item["memory_type"] == "identity" else "blue"
```

### C. Always Provide Fallback Value for `rx.cond`
When using `rx.cond` within event handler lambdas or properties, you must pass the third argument (`false_value`). If you do not want an action to occur, pass `None`:
```python
# Correct
on_key_down=lambda e: rx.cond(e == "Enter", State.send_message(), None)

# Incorrect (Will fail with ValueError)
on_key_down=lambda e: rx.cond(e == "Enter", State.send_message())
```

### D. Bypass Telemetry Prompt during `reflex init`
In non-interactive docker/CI environments, `reflex init` will hang waiting for anonymous telemetry input. Add `telemetry_enabled=False` to your `rx.Config` inside `rxconfig.py` to prevent this behavior.

### E. Disable Deprecated Sitemap Plugin String Format
Import and use the class directly in `disable_plugins` inside `rxconfig.py` to avoid deprecation warnings:
```python
from reflex_base.plugins.sitemap import SitemapPlugin

config = rx.Config(
    app_name="frontend",
    telemetry_enabled=False,
    disable_plugins=[SitemapPlugin],
)
```

## Changes Implemented:

1.  **Memory Bank Functionality Enhancements**:
    *   **Toast Notifications**: Integrated `useToast` for visual feedback on memory operations. Users now receive success/error toast notifications when adding, deleting, or editing memories.
    *   **Memory Refetching**: The memory list automatically refetches from the backend after add, delete, or edit operations, ensuring the UI is always up-to-date.
    *   **Edit Functionality**:
        *   The `Memory` interface was updated to include all fields (`key`, `value`, `memory_type`, `confidence`, `source`, `timestamp`) returned by the backend's `/facts` endpoint.
        *   `MemoryInspector.tsx` now supports inline editing of fact values. Each memory item displays an "Edit" button that, when clicked, transforms the displayed fact into an editable input field. "Save" and "Cancel" buttons are provided for managing changes.
        *   A new `onEditMemory` prop was added to `MemoryInspector.tsx` to handle the update logic.
        *   The `handleEditMemory` function was implemented in `ChatPage.tsx` to make the `POST /facts` API call for updating facts and managing toast notifications.

2.  **Custom Theme Color Picker Enhancements**:
    *   `tailwind.config.js` was updated to directly consume CSS variables (`var(--...)`) for all theme-related colors (`background`, `foreground`, `primary`, `secondary`, `accent`, `border`, `card`, `popover`, `muted`, `input`, `ring`, `destructive`, `chart-*`, and `sidebar-*`). This ensures that custom colors selected via the settings modal are correctly applied throughout the UI via Tailwind CSS classes.

3.  **"Rick and Morty" References Removal**:
    *   All explicit "Rick and Morty" references, including character names, avatar images (`rick-avatar.jpg`), and persona descriptions in `frontend/components/ChatPage.tsx`, `frontend/components/ChatMessage.tsx`, `frontend/components/ChatInput.tsx`, `frontend/components/Header.tsx`, `frontend/components/MemoryInspector.tsx`, `frontend/app/layout.tsx`, `services/persona_prompt.py`, and `services/system_prompt.py` have been replaced with generic "AI Assistant" branding and a more professional persona.
    *   The default theme name was changed from `rick` to `toxic`.
    *   The `portal-effect` class and any direct image imports of `rick-avatar.jpg` were removed.
    *   Lingering `--rick-` CSS variables in `frontend/app/globals.css` were updated to `--theme-`.

These changes make the frontend more robust, user-friendly, and visually customizable, while also aligning with a more generic and professional AI assistant brand.