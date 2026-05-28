# Trade Mode Implementation

## Purpose

This document defines the separate trading-mode subsystem for the AI Trading Copilot.
The goal is to keep trading behavior isolated from the general agent/chat flow while still reusing the same product shell, memory patterns, and UI infrastructure.

Trading mode is not an autonomous auto-trading bot.
It is a deterministic trading assistant that:

- analyzes market data,
- applies explicit strategy rules,
- calculates risk,
- retrieves similar setups and user-uploaded strategy documents,
- explains the result with an LLM,
- and always keeps the human user in control.

The assistant may recommend a trade, but it never executes without a user action.

## Core Design Principle

The architecture should always remain:

`Deterministic trading logic + risk management + RAG memory + LLM explanation`

Not:

`LLM free-styling raw trades`

The LLM is only the explanation and narration layer.
The trade direction, risk math, and actionability must be produced by deterministic code.

## Product Modes

The app now has two top-level modes:

1. `agent` mode
   - Existing cognitive chat assistant behavior.
   - Uses `/chat`.
   - Uses user facts, documents, conversation memory, and tool output.

2. `trading` mode
   - Trading-only assistant behavior.
   - Uses dedicated trading endpoints.
   - Uses trading profile, market data, trading RAG memory, uploaded strategy documents, recent trades, and deterministic risk rules.

The mode must be toggled from the UI.
When the mode changes, the frontend should switch the backend flow as well.

## Trading Mode UX Goals

Trading mode should feel like:

- an intelligent market analyst,
- a disciplined risk manager,
- a personalized trading journal,
- a strategy review engine,
- and a setup validation system.

It should not feel like:

- a prediction machine,
- a random signal generator,
- or an execution bot.

The user must always see that the final decision is theirs.

## Current Implementation State

The following pieces already exist or are being introduced:

- Frontend mode toggle in the top bar.
- Trading-specific backend route prefix under `/trading`.
- Separate trading system prompt.
- Separate trading strategy document collection.
- Trading profile storage in PostgreSQL.
- Trading signal generation endpoint.
- Trading trade take/reject endpoints.
- Trading dashboard endpoint.
- Dedicated trading strategy upload endpoint.
- Twelve Data configuration in the environment example.

The trading mode still needs future expansion in areas such as:

- live trade monitoring worker,
- close-trade automation from market prices,
- richer dashboard analytics,
- and more complete strategy learning.

## Frontend Flow

### 1. Mode Toggle

The header should expose a clear toggle between:

- `Agent Mode`
- `Trading Mode`

This toggle is the primary user-facing switch.
It should be visually obvious and should change the input behavior.

### 1b. New Trading Chat Setup

Every new trading chat must begin with a fresh session setup prompt.

The setup modal should require:

- pair,
- balance,
- and timeframe.

The chat should not generate a trading signal until those values exist for the active session.

This makes each trading session explicit and avoids accidental reuse of a previous setup.

### 2. Mode Persistence

The selected mode should be stored locally so the app restores the last mode on refresh.

Suggested browser storage keys:

- `ethio_claw_mode`
- `ethio_claw_agent_session_id`
- `ethio_claw_trading_session_id`

The agent and trading modes should not reuse the same session namespace.

### 3. Input Behavior

In `agent` mode:

- normal chat input,
- file upload enabled,
- existing document RAG remains available.

In `trading` mode:

- the input should read as a setup request or signal review,
- file upload should be hidden or disabled in the regular chat input,
- the button text should become `Initiate Signal`,
- the UI should tell the user that the mode is using deterministic trading analysis.

### 3b. Trading Session Controls

Each trading chat should surface a visible control bar with:

- the active pair,
- the active balance,
- the active timeframe,
- an `Initiate Signal` button,
- and a `New Trade Chat` button.

The `Initiate Signal` action should create a new signal for the active trading session.
The `New Trade Chat` action should force the user back through the pair and balance setup modal.

### 4. Trading UI Copy

Trading mode copy should reinforce the product discipline:

- “Deterministic market analysis”
- “Risk-controlled setup review”
- “Strategy memory enabled”
- “User stays in control”

Avoid copy that implies guaranteed profit or automatic execution.

### 5. Session Separation

Trading mode should maintain a separate session id from agent mode.

This prevents:

- agent history from contaminating trading analysis,
- trading journal entries from appearing in agent history,
- and memory retrieval from mixing unrelated contexts.

Recommended session prefix:

- `trading:<session_id>`

### 6. Frontend Routing

The frontend should call different backend endpoints depending on mode:

- `agent` mode -> `POST /chat`
- `trading` mode -> `POST /trading/signals/generate`

The UI should render the returned result as a readable signal summary.

## Backend Flow Separation

Trading mode must not share the agent chat route.

The backend needs its own dedicated flow:

- separate request models,
- separate prompts,
- separate trade tables,
- separate strategy uploads,
- separate dashboard endpoints,
- and separate memory/session naming.

This separation matters for:

- security,
- maintainability,
- observability,
- and future refactoring.

## Trading Backend Endpoints

### Profile

#### `POST /trading/profile`

Creates or updates the user trading profile.

Payload example:

```json
{
  "user_id": "uuid",
  "balance": 1000,
  "risk_percent": 1,
  "preferred_pair": "XAUUSD",
  "preferred_timeframe": "15M",
  "style": "intraday",
  "max_daily_loss": 3,
  "max_open_trades": 1,
  "preferred_sessions": ["London", "New York"]
}
```

#### `GET /trading/profile/{user_id}`

Returns the saved trading profile for the user.

### Signal Generation

#### `POST /trading/signals/generate`

This is the main trading endpoint.

It should:

1. load the trading profile,
2. fetch market data from Twelve Data,
3. compute deterministic indicators,
4. evaluate the strategy rules,
5. retrieve trading RAG memory,
6. retrieve uploaded strategy documents,
7. retrieve recent trading turns,
8. build the trading prompt,
9. call the LLM only for explanation,
10. persist the signal,
11. return a trading signal response.

The request should support session-specific overrides such as:

- pair,
- balance,
- timeframe.

### Trade Actions

#### `POST /trading/trades/take`

Creates an open trade record from a valid signal.

This should only work when the signal is actionable.

#### `POST /trading/trades/reject`

Marks the signal as rejected.

This is important for preference learning.

Each generated signal in the UI should expose:

- take action,
- reject action,
- and a disabled state after the user chooses one.

#### `POST /trading/trades/{trade_id}/close`

Closes a trade manually or by a future worker.

This endpoint is the integration point for a later background monitoring job.

### Strategy Uploads

#### `POST /trading/strategies/upload`

Uploads trading strategy documents into a separate RAG collection.

This is not the same as the general agent document upload endpoint.

The trading collection should hold:

- strategy PDFs,
- playbooks,
- checklists,
- journals,
- notes,
- and any user-defined rule documents.

### Dashboard

#### `GET /trading/dashboard/{user_id}`

Returns performance and journal statistics such as:

- balance,
- today’s P/L,
- win rate,
- open trades,
- profit factor,
- average RR,
- best pair,
- best session,
- best market condition,
- recent trades.

## Trading Data Model

### PostgreSQL Tables

#### `trading_profiles`

Stores the user’s trading configuration.

Suggested columns:

- `user_id`
- `balance`
- `risk_percent`
- `preferred_pair`
- `preferred_timeframe`
- `style`
- `max_daily_loss`
- `max_open_trades`
- `preferred_sessions`
- `updated_at`

#### `trading_signals`

Stores each generated signal with the full explanatory context.

Suggested columns:

- `id`
- `user_id`
- `session_id`
- `pair`
- `timeframe`
- `direction`
- `confidence`
- `entry`
- `stop_loss`
- `take_profit`
- `risk_amount`
- `lot_size`
- `rr_ratio`
- `reasons`
- `market_snapshot`
- `summary`
- `actionable`
- `status`
- `created_at`

#### `trading_trades`

Stores opened and closed trades.

Suggested columns:

- `id`
- `user_id`
- `signal_id`
- `status`
- `entry`
- `stop_loss`
- `take_profit`
- `risk_amount`
- `lot_size`
- `outcome`
- `pnl`
- `opened_at`
- `closed_at`

## Trading Memory Model

Trading mode should maintain its own memory context by prefixing the session id:

- `trading:<session_id>`

This should apply to:

- Qdrant semantic retrieval,
- Redis recent turns / summary,
- Postgres history rows,
- and any future trade journaling helpers.

That keeps trading memory separate from the agent memory while still using the same services.

## RAG Sources

Trading mode should use several context sources:

### 1. Trading RAG Memory

This is the semantic memory for past trading setups, outcomes, and user preferences.

It should store:

- pair,
- setup type,
- result,
- session,
- confidence,
- notes,
- and outcome details.

### 2. Uploaded Strategy Documents

These are user-uploaded or operator-uploaded strategy files.

Examples:

- trading plans,
- PDFs,
- notes,
- playbooks,
- spreadsheets,
- and journaling docs.

These documents should be indexed into a separate collection:

- `trading_strategy_knowledge`

This keeps strategy documents separate from the general agent document knowledge.

### 3. Recent Trading Turns

Recent trading messages should be retrieved from short-term memory so the assistant can answer:

- “What were we analyzing?”
- “Why did we reject the last setup?”
- “What changed since the last signal?”

### 4. Trading Profile

The user profile is not optional.
It defines the risk boundaries and preferred style.

### 5. Market Snapshot

This is the live market state fetched from Twelve Data and transformed into indicators.

## Market Data Integration

### Provider

Use Twelve Data as the first market-data source.

Environment variables:

- `TWELVE_DATA_BASE_URL`
- `TWELVE_DATA_API_KEY`

The API key should stay blank in the example env file and be filled later.

### Market Fetching

The signal generator should fetch at least the latest 100 candles.

The response should include:

- OHLCV candles,
- symbol,
- timeframe,
- and raw API metadata where useful.

### Supported Default Symbols

At minimum, support:

- `XAUUSD`

Future expansions can add:

- forex pairs,
- indices,
- crypto,
- and equities if the provider supports them.

### Timeframe Mapping

The UI timeframe should be normalized into Twelve Data intervals.

Example mapping:

- `1M` -> `1min`
- `5M` -> `5min`
- `15M` -> `15min`
- `1H` -> `1h`
- `4H` -> `4h`
- `1D` -> `1day`

## Deterministic Trading Engine

The deterministic engine should be the source of truth for direction and risk.

### Indicators

Compute at least:

- EMA 20
- EMA 50
- RSI
- ATR
- MACD
- market structure
- support / resistance
- bullish or bearish engulfing pattern

### Example Rule Set

Long bias can be derived from a combination of:

- EMA20 above EMA50,
- RSI above neutral,
- MACD histogram positive,
- bullish engulfing,
- bullish structure.

Short bias can be derived from the inverse.

If the setup is mixed or weak, return HOLD.

### Direction Policy

The engine should be conservative:

- prefer HOLD when uncertain,
- prefer fewer trades over more trades,
- never force a signal to look actionable,
- and never produce a random direction just to satisfy the UI.

### Confidence Policy

Confidence should reflect rule agreement only.

It is not a subjective “vibe” score.

Confidence should move down when:

- indicators conflict,
- structure is weak,
- RAG memory warns about the setup type,
- or strategy docs disagree.

## Risk Engine

Risk management is mandatory.

The trade should only be considered if it fits the profile constraints.

### Required Calculations

- risk amount,
- lot size,
- RR ratio,
- exposure,
- and max-loss checks.

### Core Formula

```text
Risk Amount = Balance × Risk Percentage
```

### Lot Size Formula

```text
Lot Size = Risk Amount / (Stop Loss Distance × Pip Value)
```

### Risk Constraints

The engine should respect:

- `max_daily_loss`,
- `max_open_trades`,
- `risk_percent`,
- and any future exposure ceiling.

### Actionability Rules

A signal should not be actionable if:

- the user profile is missing,
- the market data is too thin,
- the stop distance is invalid,
- the setup is HOLD,
- or the profile risk rules are violated.

## Trading System Prompt

Trading mode needs its own system prompt.

This prompt must:

- define the trading assistant role,
- forbid raw prediction,
- forbid invented prices,
- enforce the “user in control” rule,
- require respect for risk boundaries,
- require use of RAG memory and strategy docs,
- and force the model to stay in explanation mode.

Prompt responsibilities:

- explain the deterministic signal,
- summarize the market context,
- mention how the strategy docs influenced the interpretation,
- reference prior outcomes if relevant,
- and clearly say when the proper action is HOLD.

The prompt should never allow the model to turn weak evidence into a strong trade call.

## Trading Prompt Context Blocks

The prompt should include:

1. Trading profile
2. Market snapshot
3. Deterministic signal
4. Risk summary
5. Retrieved RAG memory
6. Uploaded strategy documents
7. Recent trades
8. Session context
9. User message

This layered prompt structure mirrors the existing agent prompt architecture, but it is trading-specific.

## LLM Role in Trading Mode

The LLM should:

- make the output readable,
- summarize the reasoning,
- produce concise justification text,
- and help the user interpret the setup.

The LLM must not:

- override the deterministic engine,
- invent new levels,
- invent a new direction,
- or claim certainty.

If the deterministic engine says HOLD, the LLM must explain why it is HOLD.

## Journal and Learning

After each trading signal or trade outcome, persist:

- the setup characteristics,
- the market regime,
- the timeframe,
- the session,
- the confidence,
- the RR,
- the outcome,
- and the user’s decision.

This is the long-term learning loop.

### Learning Targets

Store enough information to later answer:

- What setups does the user prefer?
- Which pair performs best?
- Which session performs best?
- Which market regime performs best?
- Which setups get rejected often?
- Which signals win after confirmation?

### Future Learning Uses

This journal can later drive:

- frequency adjustment,
- setup filtering,
- session preference learning,
- and signal suppression for patterns the user repeatedly rejects.

## Monitoring and Trade Close Flow

The first implementation can keep monitoring manual or worker-driven.

The future production version should:

- check open trades on a timer,
- read current prices,
- compare against stop loss and take profit,
- close trades automatically,
- and persist the result.

Suggested worker cadence:

- every 30 to 60 seconds.

Future worker inputs:

- Redis queue,
- or Celery,
- or a similar background job runner.

## Recommended Backend File Changes

The following files are part of the current implementation plan:

- `main.py`
  - register trading endpoints,
  - initialize trading DB tables,
  - initialize the trading document collection.

- `schema.py`
  - add trading request and response models.

- `services/trading_system_prompt.py`
  - define the trading system prompt.

- `services/trading_prompt_builder.py`
  - build the layered trading prompt.

- `services/trading_service.py`
  - implement profiles, signal generation, trade actions, and dashboard data.

- `services/document_service.py`
  - support multiple document collections and source types.

- `env.exmaple`
  - add Twelve Data settings and trading collection settings.

- `frontend/components/Header.tsx`
  - add the mode toggle.

- `frontend/components/ChatPage.tsx`
  - route requests by mode,
  - maintain separate sessions,
  - format trading responses.

- `frontend/components/ChatInput.tsx`
  - adjust placeholder, button labels, and upload visibility based on mode.

## Environment Variables

### Backend

Required for trading mode:

```env
TWELVE_DATA_BASE_URL=https://api.twelvedata.com
TWELVE_DATA_API_KEY=
TRADING_STRATEGY_COLLECTION_NAME=trading_strategy_knowledge
```

The API key should be populated later, after the major feature updates are complete.

### Existing backend variables still apply

- Postgres connection settings,
- Redis settings,
- Qdrant settings,
- and existing model settings.

## Acceptance Criteria

Trading mode is considered functional when:

1. The UI can switch between agent and trading modes.
2. Trading mode calls a dedicated trading endpoint.
3. Trading mode does not reuse the `/chat` flow.
4. A trading profile can be saved and retrieved.
5. A signal can be generated from market data.
6. The signal response includes risk math and reasoning.
7. Strategy documents can be uploaded into the trading RAG path.
8. Trading RAG context is retrieved separately from agent context.
9. The LLM only explains the deterministic signal.
10. The user can take or reject the signal.
11. Dashboard stats can be queried later from trading records.

## Future Enhancements

After the first working version, the next stages should be:

1. Live trade monitoring worker
2. Better dashboard analytics
3. Strategy-specific memory retrieval improvements
4. Multi-timeframe analysis
5. Economic calendar filtering
6. Market regime detection
7. User preference learning
8. Richer trade journal visualizations
9. Better lot-size modeling per instrument
10. More precise support/resistance logic

## Open Questions for Later

These are intentionally left for future refinement:

- Should trades be tied to authenticated users instead of a default profile?
- Should strategy uploads be visible in a dedicated trading UI panel?
- Should the trading dashboard be a separate page?
- Should the system use a separate Qdrant collection for trading memory instead of prefixed sessions?
- Should the close-trade worker run in Celery, APScheduler, or another job runner?
- Should market data be cached locally to reduce Twelve Data usage?

## Practical Build Order

If you continue this feature later, the best order is:

1. Finalize the trading prompt and signal schema.
2. Finish market data and indicator validation.
3. Add a dedicated trading dashboard view.
4. Add trade monitoring and close automation.
5. Add richer journal analytics.
6. Add preference learning from rejects and wins.
7. Tighten risk calculations per instrument.

## Summary

Trading mode should remain a separate, deterministic, risk-aware subsystem.
It should reuse the platform’s existing memory and RAG strengths, but never blend into the agent chat path.

The product should always behave like:

- a disciplined trading copilot,
- a journal-driven analyst,
- and a risk-first decision assistant.

Not:

- an autonomous trading robot.
