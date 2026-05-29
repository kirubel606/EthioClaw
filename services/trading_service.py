import json
import os
import uuid
from datetime import datetime

import httpx

import services.fact_db as fact_db
from services.ai_service import ask_model
from services.conversation_cache import append_turn, get_recent_turns, get_summary, refresh_summary
from services.document_service import retrieve_document_context, TRADING_STRATEGY_COLLECTION_NAME
from services.fact_db import save_chat_message
from services.memory_service import retrieve_context, save_message
from services.trading_prompt_builder import build_trading_prompt

TWELVE_DATA_BASE_URL = os.getenv("TWELVE_DATA_BASE_URL", "https://api.twelvedata.com").rstrip("/")
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "").strip()

def _trading_session_id(session_id: str) -> str:
    # Use the session_id as provided by the frontend.
    # The frontend already prefixes trading sessions with 'trading-session-'.
    return session_id


def _normalize_symbol(symbol: str) -> str:
    clean = symbol.strip().upper().replace(" ", "")
    # Common Aliases
    if clean == "XAUUSD":
        return "XAU/USD"
    if clean == "USOIL" or clean == "WTI":
        return "WTI/USD"
    if clean == "UKOIL" or clean == "BRENT":
        return "BRENT/USD"
    
    if "/" in clean:
        return clean
    if len(clean) == 6 and clean.isalpha():
        return f"{clean[:3]}/{clean[3:]}"
    return clean


def _normalize_interval(timeframe: str) -> str:
    value = timeframe.strip().upper()
    return {
        "1M": "1min",
        "3M": "3min",
        "5M": "5min",
        "15M": "15min",
        "30M": "30min",
        "1H": "1h",
        "4H": "4h",
        "1D": "1day",
    }.get(value, value.lower())


def _parse_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    k = 2 / (period + 1)
    ema_values = [values[0]]
    for price in values[1:]:
        ema_values.append((price * k) + (ema_values[-1] * (1 - k)))
    return ema_values


def _rsi(values: list[float], period: int = 14) -> float:
    if len(values) <= period:
        return 50.0

    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, len(values)):
        delta = values[index] - values[index - 1]
        gains.append(max(delta, 0.0))
        losses.append(abs(min(delta, 0.0)))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _macd(values: list[float]) -> dict[str, float]:
    if len(values) < 35:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
    ema12 = _ema_series(values, 12)
    ema26 = _ema_series(values, 26)
    macd_line = [ema12[index] - ema26[index] for index in range(len(ema26))]
    signal_line = _ema_series(macd_line, 9)
    return {
        "macd": macd_line[-1],
        "signal": signal_line[-1],
        "histogram": macd_line[-1] - signal_line[-1],
    }


def _atr(candles: list[dict], period: int = 14) -> float:
    if len(candles) <= period:
        return 0.0

    true_ranges: list[float] = []
    for index in range(1, len(candles)):
        high = candles[index]["high"]
        low = candles[index]["low"]
        prev_close = candles[index - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    if not true_ranges:
        return 0.0

    window = true_ranges[-period:]
    return sum(window) / len(window)


def _bullish_engulfing(candles: list[dict]) -> bool:
    if len(candles) < 2:
        return False
    prev = candles[-2]
    current = candles[-1]
    return (
        prev["close"] < prev["open"]
        and current["close"] > current["open"]
        and current["open"] <= prev["close"]
        and current["close"] >= prev["open"]
    )


def _bearish_engulfing(candles: list[dict]) -> bool:
    if len(candles) < 2:
        return False
    prev = candles[-2]
    current = candles[-1]
    return (
        prev["close"] > prev["open"]
        and current["close"] < current["open"]
        and current["open"] >= prev["close"]
        and current["close"] <= prev["open"]
    )


def _structure_bias(candles: list[dict]) -> str:
    if len(candles) < 8:
        return "neutral"

    recent = candles[-6:]
    highs = [c["high"] for c in recent[:-1]]
    lows = [c["low"] for c in recent[:-1]]
    last_close = recent[-1]["close"]

    if last_close > max(highs):
        return "bullish"
    if last_close < min(lows):
        return "bearish"
    return "neutral"


def _support_resistance(candles: list[dict]) -> tuple[float, float]:
    recent = candles[-20:] if len(candles) >= 20 else candles
    supports = [c["low"] for c in recent]
    resistances = [c["high"] for c in recent]
    return min(supports), max(resistances)


def _pip_value_for_symbol(symbol: str) -> float:
    """
    Returns the dollar value of a 1.00 move for 1 standard lot.
    - Forex: 1.00 move = $100,000 (0.0001 pip = $10)
    - Gold:  1.00 move = $100
    - Oil:   1.00 move = $1000
    """
    clean = symbol.upper().replace("/", "")
    if clean.startswith("XAU"): # Gold
        return 100.0
    if clean.startswith("WTI") or clean == "USOIL" or clean.startswith("BRENT"):
        return 1000.0
    return 100000.0 # Forex standard lot


async def init_trading_db() -> None:
    if fact_db.pool is None:
        raise RuntimeError("Postgres pool is not initialized")

    async with fact_db.pool.acquire() as conn:
        # Migration for trading_profiles
        # 1. Add session_id if missing
        await conn.execute("ALTER TABLE trading_profiles ADD COLUMN IF NOT EXISTS session_id TEXT;")
        # 2. If user_id is the primary key and session_id is not, we need to swap.
        # This is a bit complex in SQL, so we'll check the current PK.
        pk_info = await conn.fetchrow("""
            SELECT a.attname
            FROM   pg_index i
            JOIN   pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE  i.indrelid = 'trading_profiles'::regclass
            AND    i.indisprimary;
        """)
        
        if pk_info and pk_info['attname'] == 'user_id':
            print("[DB] Migrating trading_profiles PRIMARY KEY from user_id to session_id")
            # Set session_id to user_id for existing records if it's null
            await conn.execute("UPDATE trading_profiles SET session_id = user_id WHERE session_id IS NULL;")
            await conn.execute("ALTER TABLE trading_profiles ALTER COLUMN session_id SET NOT NULL;")
            await conn.execute("ALTER TABLE trading_profiles DROP CONSTRAINT trading_profiles_pkey;")
            await conn.execute("ALTER TABLE trading_profiles ADD PRIMARY KEY (session_id);")

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trading_profiles (
                session_id          TEXT PRIMARY KEY,
                user_id             TEXT NOT NULL,
                balance             DOUBLE PRECISION NOT NULL DEFAULT 1000,
                risk_percent        DOUBLE PRECISION NOT NULL DEFAULT 3,
                preferred_pair      TEXT NOT NULL DEFAULT 'XAUUSD',
                preferred_timeframe TEXT NOT NULL DEFAULT '15M',
                style               TEXT NOT NULL DEFAULT 'intraday',
                max_daily_loss      DOUBLE PRECISION NOT NULL DEFAULT 3,
                max_open_trades     INTEGER NOT NULL DEFAULT 1,
                preferred_sessions  TEXT[] NOT NULL DEFAULT '{}',
                updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trading_signals (
                id               TEXT PRIMARY KEY,
                user_id          TEXT NOT NULL,
                session_id       TEXT NOT NULL,
                pair             TEXT NOT NULL,
                timeframe        TEXT NOT NULL,
                balance          DOUBLE PRECISION NOT NULL,
                direction        TEXT NOT NULL,
                confidence       DOUBLE PRECISION NOT NULL,
                entry            DOUBLE PRECISION,
                stop_loss        DOUBLE PRECISION,
                take_profit      DOUBLE PRECISION,
                risk_amount      DOUBLE PRECISION NOT NULL,
                lot_size         DOUBLE PRECISION NOT NULL,
                rr_ratio         TEXT NOT NULL,
                reasons          TEXT NOT NULL,
                market_snapshot  TEXT NOT NULL,
                summary          TEXT NOT NULL,
                actionable       BOOLEAN NOT NULL DEFAULT TRUE,
                status           TEXT NOT NULL DEFAULT 'READY',
                created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        await conn.execute("ALTER TABLE trading_signals ADD COLUMN IF NOT EXISTS balance DOUBLE PRECISION NOT NULL DEFAULT 0;")

        # Migration for trading_trades
        await conn.execute("ALTER TABLE trading_trades ADD COLUMN IF NOT EXISTS session_id TEXT;")
        await conn.execute("UPDATE trading_trades SET session_id = 'default' WHERE session_id IS NULL;")

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trading_trades (
                id             TEXT PRIMARY KEY,
                user_id        TEXT NOT NULL,
                session_id     TEXT NOT NULL,
                signal_id      TEXT NOT NULL,
                status         TEXT NOT NULL DEFAULT 'OPEN',
                entry          DOUBLE PRECISION,
                stop_loss      DOUBLE PRECISION,
                take_profit    DOUBLE PRECISION,
                risk_amount    DOUBLE PRECISION NOT NULL DEFAULT 0,
                lot_size       DOUBLE PRECISION NOT NULL DEFAULT 0,
                outcome        TEXT,
                pnl            DOUBLE PRECISION NOT NULL DEFAULT 0,
                opened_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                closed_at      TIMESTAMPTZ
            );
            """
        )


async def get_trading_profile(session_id: str) -> dict | None:
    if fact_db.pool is None:
        raise RuntimeError("Postgres pool is not initialized")

    async with fact_db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT session_id, user_id, balance, risk_percent, preferred_pair, preferred_timeframe,
                   style, max_daily_loss, max_open_trades, preferred_sessions, updated_at
            FROM trading_profiles
            WHERE session_id = $1
            """,
            session_id,
        )
        return dict(row) if row else None


async def save_trading_profile(payload) -> dict:
    if fact_db.pool is None:
        raise RuntimeError("Postgres pool is not initialized")

    session_id = getattr(payload, 'session_id', 'default')
    user_id = getattr(payload, 'user_id', 'default')

    async with fact_db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO trading_profiles (
                session_id, user_id, balance, risk_percent, preferred_pair, preferred_timeframe,
                style, max_daily_loss, max_open_trades, preferred_sessions, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
            ON CONFLICT (session_id) DO UPDATE SET
                balance = EXCLUDED.balance,
                risk_percent = EXCLUDED.risk_percent,
                preferred_pair = EXCLUDED.preferred_pair,
                preferred_timeframe = EXCLUDED.preferred_timeframe,
                style = EXCLUDED.style,
                max_daily_loss = EXCLUDED.max_daily_loss,
                max_open_trades = EXCLUDED.max_open_trades,
                preferred_sessions = EXCLUDED.preferred_sessions,
                updated_at = NOW()
            RETURNING session_id, user_id, balance, risk_percent, preferred_pair, preferred_timeframe,
                      style, max_daily_loss, max_open_trades, preferred_sessions, updated_at
            """,
            session_id,
            user_id,
            payload.balance,
            payload.risk_percent,
            payload.preferred_pair,
            payload.preferred_timeframe,
            payload.style,
            payload.max_daily_loss,
            payload.max_open_trades,
            payload.preferred_sessions or [],
        )
        return dict(row)


async def update_session_balance(session_id: str, new_balance: float) -> dict:
    if fact_db.pool is None:
        raise RuntimeError("Postgres pool is not initialized")

    async with fact_db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE trading_profiles
            SET balance = $2, updated_at = NOW()
            WHERE session_id = $1
            RETURNING *
            """,
            session_id,
            new_balance,
        )
        if row is None:
            # If profile doesn't exist, create it with this balance
            return await _ensure_profile(session_id, user_id="default", balance=new_balance)
        return dict(row)

async def _ensure_profile(session_id: str, user_id: str = "default", balance: float = 1000.0) -> dict:
    profile = await get_trading_profile(session_id)
    if profile:
        return profile

    from types import SimpleNamespace

    default_payload = SimpleNamespace(
        session_id=session_id,
        user_id=user_id,
        balance=balance,
        risk_percent=3.0,
        preferred_pair="XAUUSD",
        preferred_timeframe="15M",
        style="intraday",
        max_daily_loss=3.0,
        max_open_trades=1,
        preferred_sessions=[],
    )
    return await save_trading_profile(default_payload)


async def _store_signal(signal: dict) -> dict:
    if fact_db.pool is None:
        raise RuntimeError("Postgres pool is not initialized")

    async with fact_db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO trading_signals (
                id, user_id, session_id, pair, timeframe, direction, confidence,
                balance, entry, stop_loss, take_profit, risk_amount, lot_size, rr_ratio,
                reasons, market_snapshot, summary, actionable, status, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, NOW())
            RETURNING *
            """,
            signal["signal_id"],
            signal["user_id"],
            signal["session_id"],
            signal["pair"],
            signal["timeframe"],
            signal["direction"],
            signal["confidence"],
            signal["balance"],
            signal.get("entry"),
            signal.get("stop_loss"),
            signal.get("take_profit"),
            signal["risk_amount"],
            signal["lot_size"],
            signal["rr_ratio"],
            "\n".join(signal.get("reasons", [])),
            json.dumps(signal.get("market_snapshot", {})),
            signal.get("summary", ""),
            signal.get("actionable", True),
            signal.get("status", "READY"),
        )
        return dict(row)


async def get_trading_signal(signal_id: str) -> dict | None:
    if fact_db.pool is None:
        raise RuntimeError("Postgres pool is not initialized")

    async with fact_db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM trading_signals WHERE id = $1", signal_id)
        return dict(row) if row else None


async def save_trade_from_signal(signal: dict, user_id: str) -> dict:
    if fact_db.pool is None:
        raise RuntimeError("Postgres pool is not initialized")

    trade_id = str(uuid.uuid4())
    async with fact_db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO trading_trades (
                id, user_id, session_id, signal_id, status, entry, stop_loss, take_profit,
                risk_amount, lot_size, outcome, pnl, opened_at
            )
            VALUES ($1, $2, $3, $4, 'OPEN', $5, $6, $7, $8, $9, NULL, 0, NOW())
            RETURNING *
            """,
            trade_id,
            user_id,
            signal["session_id"],
            signal["id"],
            signal["entry"],
            signal["stop_loss"],
            signal["take_profit"],
            signal["risk_amount"],
            signal["lot_size"],
        )
        await conn.execute("UPDATE trading_signals SET status = 'TAKEN' WHERE id = $1", signal["id"])
        return dict(row)


async def reject_signal(signal_id: str) -> dict:
    if fact_db.pool is None:
        raise RuntimeError("Postgres pool is not initialized")

    async with fact_db.pool.acquire() as conn:
        await conn.execute("UPDATE trading_signals SET status = 'REJECTED' WHERE id = $1", signal_id)
    signal = await get_trading_signal(signal_id)
    return signal or {"id": signal_id, "status": "REJECTED"}


async def close_trade(trade_id: str, outcome: str, pnl: float = 0.0) -> dict:
    if fact_db.pool is None:
        raise RuntimeError("Postgres pool is not initialized")

    async with fact_db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE trading_trades
            SET status = 'CLOSED', outcome = $2, pnl = $3, closed_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            trade_id,
            outcome,
            pnl,
        )
        if row is None:
            raise RuntimeError(f"Trade {trade_id} not found")
        
        # Update session balance
        await conn.execute(
            "UPDATE trading_profiles SET balance = balance + $1 WHERE session_id = $2",
            pnl,
            row["session_id"],
        )
        return dict(row)


async def monitor_open_trades() -> list[dict]:
    """
    Fetches all OPEN trades, gets current prices, and closes them if SL or TP is hit.
    Returns a list of trades that were closed in this run.
    """
    if fact_db.pool is None:
        return []

    async with fact_db.pool.acquire() as conn:
        open_trades = await conn.fetch(
            """
            SELECT t.*, s.pair, s.direction
            FROM trading_trades t
            JOIN trading_signals s ON t.signal_id = s.id
            WHERE t.status = 'OPEN'
            """
        )

    if not open_trades:
        return []

    closed_trades = []
    # Group trades by pair to minimize API calls
    pairs = list(set(t["pair"] for t in open_trades))

    # For simplicity, we fetch each pair individually for now.
    # In production, we'd use a batch quote endpoint.
    current_prices = {}
    for pair in pairs:
        try:
            # We only need the latest price, but we use fetch_market_data which gives 100 candles.
            # We could optimize this by adding a fetch_latest_price function.
            candles, _ = await fetch_market_data(pair, "1M", outputsize=1)
            if candles:
                current_prices[pair] = candles[-1]["close"]
        except Exception as e:
            print(f"[MONITOR] Failed to fetch price for {pair}: {e}")

    for trade in open_trades:
        pair = trade["pair"]
        if pair not in current_prices:
            continue

        price = current_prices[pair]
        sl = trade["stop_loss"]
        tp = trade["take_profit"]
        direction = trade["direction"]
        lot_size = trade["lot_size"]
        entry = trade["entry"]

        hit_sl = False
        hit_tp = False

        if direction == "BUY":
            if sl and price <= sl:
                hit_sl = True
            elif tp and price >= tp:
                hit_tp = True
        elif direction == "SELL":
            if sl and price >= sl:
                hit_sl = True
            elif tp and price <= tp:
                hit_tp = True

        # Calculate current PnL for the dashboard
        multiplier = _pip_value_for_symbol(pair)
        current_pnl = round((price - entry) * lot_size * multiplier if direction == "BUY" else (entry - price) * lot_size * multiplier, 2)
        
        # Update live PnL in database
        async with fact_db.pool.acquire() as update_conn:
            await update_conn.execute("UPDATE trading_trades SET pnl = $1 WHERE id = $2", current_pnl, trade["id"])

        if hit_sl or hit_tp:
            outcome = "LOSS" if hit_sl else "WIN"
            # Use the calculated current_pnl for closing
            pnl = current_pnl

            try:
                closed = await close_trade(trade["id"], outcome, pnl)
                closed_trades.append(closed)
                print(f"[MONITOR] Closed trade {trade['id']} for {pair} as {outcome}. PnL: {pnl}")
            except Exception as e:
                print(f"[MONITOR] Failed to close trade {trade['id']}: {e}")

    return closed_trades


async def get_trading_dashboard(session_id: str) -> dict:
    if fact_db.pool is None:
        raise RuntimeError("Postgres pool is not initialized")

    profile = await _ensure_profile(session_id)

    async with fact_db.pool.acquire() as conn:
        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total_trades,
                COUNT(*) FILTER (WHERE status = 'OPEN') AS open_trades,
                COUNT(*) FILTER (WHERE outcome = 'WIN') AS wins,
                COUNT(*) FILTER (WHERE outcome = 'LOSS') AS losses,
                COALESCE(SUM(pnl), 0) AS todays_pl,
                COALESCE(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END), 0) AS gross_profit,
                COALESCE(SUM(CASE WHEN pnl < 0 THEN ABS(pnl) ELSE 0 END), 0) AS gross_loss
            FROM trading_trades
            WHERE session_id = $1
            """,
            session_id,
        )

        # Calculate average RR from signals associated with closed trades
        rr_stats = await conn.fetchrow(
            """
            SELECT AVG(ABS(s.take_profit - s.entry) / NULLIF(ABS(s.entry - s.stop_loss), 0)) as avg_rr
            FROM trading_trades t
            JOIN trading_signals s ON t.signal_id = s.id
            WHERE t.session_id = $1 AND t.status = 'CLOSED'
            """,
            session_id,
        )

        # Find best pair
        best_pair_row = await conn.fetchrow(
            """
            SELECT s.pair, SUM(t.pnl) as total_pnl
            FROM trading_trades t
            JOIN trading_signals s ON t.signal_id = s.id
            WHERE t.session_id = $1 AND t.status = 'CLOSED'
            GROUP BY s.pair
            ORDER BY total_pnl DESC
            LIMIT 1
            """,
            session_id,
        )

        recent = await conn.fetch(
            """
            SELECT t.id, t.signal_id, t.status, t.outcome, t.pnl, t.opened_at, t.closed_at, s.pair
            FROM trading_trades t
            JOIN trading_signals s ON t.signal_id = s.id
            WHERE t.session_id = $1
            ORDER BY t.opened_at DESC
            LIMIT 5
            """,
            session_id,
        )

    total = int(stats["total_trades"] or 0)
    wins = int(stats["wins"] or 0)
    losses = int(stats["losses"] or 0)
    gross_profit = float(stats["gross_profit"] or 0)
    gross_loss = float(stats["gross_loss"] or 0)

    win_rate = round((wins / total) * 100, 2) if total else 0.0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss else (round(gross_profit, 2) if gross_profit else 0.0)
    avg_rr_val = float(rr_stats["avg_rr"] or 0.0)
    avg_rr_str = f"1:{round(avg_rr_val, 2)}" if avg_rr_val else "1:2.0"

    best_pair = best_pair_row["pair"] if best_pair_row else profile["preferred_pair"]

    return {
        "user_id": profile["user_id"],
        "session_id": session_id,
        "balance": float(profile["balance"]),
        "todays_pl": float(stats["todays_pl"] or 0),
        "win_rate": win_rate,
        "open_trades": int(stats["open_trades"] or 0),
        "profit_factor": profit_factor,
        "average_rr": avg_rr_str,
        "best_pair": best_pair,
        "best_session": (profile["preferred_sessions"][0] if profile["preferred_sessions"] else "London"),
        "best_market_condition": "Trending",
        "recent_trades": [dict(item) for item in recent],
    }


async def get_closed_trades_notifications(session_id: str) -> list[dict]:
    if fact_db.pool is None:
        return []

    async with fact_db.pool.acquire() as conn:
        # Fetch trades closed in the last 60 seconds.
        # In a real app, you'd use a 'notified' boolean column.
        rows = await conn.fetch(
            """
            SELECT t.*, s.pair, s.direction
            FROM trading_trades t
            JOIN trading_signals s ON t.signal_id = s.id
            WHERE t.session_id = $1 
              AND t.status = 'CLOSED' 
              AND t.closed_at > NOW() - INTERVAL '1 minute'
            ORDER BY t.closed_at DESC
            """,
            session_id,
        )
        return [dict(row) for row in rows]
async def get_recent_trades_text(session_id: str, limit: int = 5) -> str:
    if fact_db.pool is None:
        raise RuntimeError("Postgres pool is not initialized")

    async with fact_db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, signal_id, status, outcome, pnl, opened_at, closed_at
            FROM trading_trades
            WHERE session_id = $1
            ORDER BY opened_at DESC
            LIMIT $2
            """,
            session_id,
            limit,
        )

    if not rows:
        return ""

    lines = []
    for row in rows:
        lines.append(
            f"  trade_id={row['id']} status={row['status']} outcome={row['outcome'] or 'n/a'} pnl={row['pnl']}"
        )
    return "\n".join(lines)


async def fetch_market_data(pair: str, timeframe: str, outputsize: int = 100) -> tuple[list[dict], dict]:
    if not TWELVE_DATA_API_KEY:
        raise RuntimeError("TWELVE_DATA_API_KEY is not configured")

    symbol = _normalize_symbol(pair)
    interval = _normalize_interval(timeframe)
    url = f"{TWELVE_DATA_BASE_URL}/time_series"

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVE_DATA_API_KEY,
        "format": "JSON",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()

    values = payload.get("values") or []
    candles: list[dict] = []
    for item in reversed(values):
        candles.append(
            {
                "datetime": item.get("datetime"),
                "open": _parse_float(item.get("open")),
                "high": _parse_float(item.get("high")),
                "low": _parse_float(item.get("low")),
                "close": _parse_float(item.get("close")),
                "volume": _parse_float(item.get("volume")),
            }
        )

    if outputsize >= 30 and len(candles) < 30:
        raise RuntimeError(f"Insufficient candles returned by Twelve Data (requested {outputsize}, got {len(candles)})")

    return candles, payload


def _build_market_snapshot(candles: list[dict]) -> dict:
    closes = [c["close"] for c in candles]
    ema20 = _ema_series(closes, 20)[-1]
    ema50 = _ema_series(closes, 50)[-1]
    rsi = _rsi(closes)
    macd = _macd(closes)
    atr = _atr(candles)
    support, resistance = _support_resistance(candles)
    structure = _structure_bias(candles)
    latest = candles[-1]

    return {
        "latest_close": round(latest["close"], 5),
        "latest_datetime": latest["datetime"],
        "ema20": round(ema20, 5),
        "ema50": round(ema50, 5),
        "rsi": round(rsi, 2),
        "macd": round(macd["macd"], 5),
        "macd_signal": round(macd["signal"], 5),
        "macd_histogram": round(macd["histogram"], 5),
        "atr": round(atr, 5),
        "support": round(support, 5),
        "resistance": round(resistance, 5),
        "market_structure": structure,
        "bullish_engulfing": _bullish_engulfing(candles),
        "bearish_engulfing": _bearish_engulfing(candles),
    }


def _deterministic_signal(pair: str, timeframe: str, candles: list[dict], profile: dict, balance: float) -> dict:
    closes = [c["close"] for c in candles]
    latest = candles[-1]
    ema20 = _ema_series(closes, 20)[-1]
    ema50 = _ema_series(closes, 50)[-1]
    rsi = _rsi(closes)
    macd = _macd(closes)
    atr = _atr(candles)
    structure = _structure_bias(candles)
    bullish_engulfing = _bullish_engulfing(candles)
    bearish_engulfing = _bearish_engulfing(candles)

    bullish_score = 0
    bearish_score = 0
    reasons: list[str] = []

    if ema20 > ema50:
        bullish_score += 1
        reasons.append("EMA20 is above EMA50")
    elif ema20 < ema50:
        bearish_score += 1
        reasons.append("EMA20 is below EMA50")

    if rsi >= 55:
        bullish_score += 1
        reasons.append(f"RSI is supportive at {round(rsi, 2)}")
    elif rsi <= 45:
        bearish_score += 1
        reasons.append(f"RSI is weak at {round(rsi, 2)}")

    if macd["histogram"] > 0:
        bullish_score += 1
        reasons.append("MACD histogram is positive")
    elif macd["histogram"] < 0:
        bearish_score += 1
        reasons.append("MACD histogram is negative")

    if bullish_engulfing:
        bullish_score += 1
        reasons.append("Bullish engulfing candle confirmed")
    if bearish_engulfing:
        bearish_score += 1
        reasons.append("Bearish engulfing candle confirmed")

    if structure == "bullish":
        bullish_score += 1
        reasons.append("Recent market structure is bullish")
    elif structure == "bearish":
        bearish_score += 1
        reasons.append("Recent market structure is bearish")

    # DETERMINISTIC DIRECTION
    # Lowered threshold: 2 points lead for BUY/SELL
    if bullish_score >= 2 and bullish_score > bearish_score + 1:
        direction = "BUY"
    elif bearish_score >= 2 and bearish_score > bullish_score + 1:
        direction = "SELL"
    else:
        direction = "WAIT"

    # CONFIDENCE
    confidence = min(95.0, 40.0 + max(bullish_score, bearish_score) * 12.0)
    if direction == "WAIT":
        confidence = max(20.0, confidence - 20.0)

    # RISK & LEVELS
    # We calculate levels even for WAIT if there's a clear bias, so user can choose to take it.
    effective_direction = direction
    if direction == "WAIT":
        if bullish_score > bearish_score: effective_direction = "BUY"
        elif bearish_score > bullish_score: effective_direction = "SELL"
    
    risk_percent = 0.0
    if effective_direction != "WAIT":
        if confidence >= 85: risk_percent = 5.0
        elif confidence >= 70: risk_percent = 4.0
        else: risk_percent = 3.0

    risk_amount = round(balance * (risk_percent / 100.0), 2)
    entry = round(latest["close"], 5)

    stop_loss = None
    take_profit = None
    lot_size = 0.0
    rr_ratio = "0:0"
    
    # We provide levels even for WAIT if it has any bias
    if effective_direction in {"BUY", "SELL"}:
        atr_val = atr or max(entry * 0.0025, 0.0001)
        if effective_direction == "BUY":
            stop_loss = round(entry - (atr_val * 1.5), 5)
            take_profit = round(entry + (atr_val * 2.5), 5)
        else:
            stop_loss = round(entry + (atr_val * 1.5), 5)
            take_profit = round(entry - (atr_val * 2.5), 5)

        stop_distance = abs(entry - stop_loss) or 0.0001
        reward_distance = abs(take_profit - entry)
        rr = reward_distance / stop_distance
        rr_ratio = f"1:{round(rr, 2)}"
        
        multiplier = _pip_value_for_symbol(pair)
        # Lot Size = Risk / (StopDistance * Multiplier)
        if risk_amount > 0:
            lot_size = round(max(risk_amount / max(stop_distance * multiplier, 0.0001), 0.01), 2)
        else:
            # Fallback lot size for WAIT signals so they can be taken manually
            # Using a default 3% risk just for the calculation
            temp_risk = round(balance * 0.03, 2)
            lot_size = round(max(temp_risk / max(stop_distance * multiplier, 0.0001), 0.01), 2)

    market_snapshot = _build_market_snapshot(candles)
    
    if direction == "WAIT":
        summary = (
            f"DISCIPLINED WAIT: Indicators are mixed ({bullish_score}B / {bearish_score}S). "
            "No high-probability setup detected. However, potential levels are provided if you wish to execute a manual bias."
        )
    else:
        summary = (
            f"{direction} {pair} confirmed with {round(confidence, 2)}% confluence. "
            f"Risk: ${risk_amount} ({risk_percent}%). Terminal setup ready."
        )

    return {
        "pair": pair,
        "timeframe": timeframe,
        "direction": direction,
        "confidence": round(confidence, 2),
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_amount": risk_amount,
        "risk_percent_applied": risk_percent,
        "lot_size": lot_size,
        "rr_ratio": rr_ratio,
        "reasons": reasons or ["Insufficient data for valid technical scan."],
        "actionable": True, # ALWAYS ALLOW USER TO DECIDE
        "market_snapshot": market_snapshot,
        "summary": summary,
    }


async def generate_trading_signal(
    *,
    user_id: str,
    session_id: str,
    pair: str | None = None,
    timeframe: str | None = None,
    balance: float | None = None,
    message: str = "",
) -> dict:
    profile = await _ensure_profile(user_id)
    resolved_pair = pair or profile["preferred_pair"]
    resolved_timeframe = timeframe or profile["preferred_timeframe"]
    resolved_balance = float(balance if balance is not None else profile["balance"])
    trading_session_id = _trading_session_id(session_id)

    user_text = message or f"Generate a trading setup for {resolved_pair} on {resolved_timeframe}."

    await save_message("user", user_text, session_id=trading_session_id)
    await save_chat_message(trading_session_id, "user", user_text)
    await append_turn(trading_session_id, "user", user_text)

    candles, raw_payload = await fetch_market_data(resolved_pair, resolved_timeframe)
    signal = _deterministic_signal(resolved_pair, resolved_timeframe, candles, profile, resolved_balance)


    semantic_context = await retrieve_context(user_text, session_id=trading_session_id, limit=8)
    strategy_context = await retrieve_document_context(
        user_text,
        session_id=trading_session_id,
        limit=8,
        collection_name=TRADING_STRATEGY_COLLECTION_NAME,
        source_type="trading_strategy",
    )
    summary_context = await get_summary(trading_session_id)
    recent_turns = await get_recent_turns(trading_session_id, limit=8)
    recent_turn_text = "\n".join(f"  {turn['role']}: {turn['content']}" for turn in recent_turns)
    recent_trade_text = await get_recent_trades_text(user_id, limit=5)

    profile_text = "\n".join(
        [
            f"  user_id: {profile['user_id']}",
            f"  balance: {profile['balance']}",
            f"  risk_percent: {profile['risk_percent']}",
            f"  preferred_pair: {profile['preferred_pair']}",
            f"  preferred_timeframe: {profile['preferred_timeframe']}",
            f"  style: {profile['style']}",
            f"  max_daily_loss: {profile['max_daily_loss']}",
            f"  max_open_trades: {profile['max_open_trades']}",
            f"  preferred_sessions: {profile['preferred_sessions']}",
        ]
    )

    market_snapshot_text = "\n".join(
        [
            f"  symbol: {resolved_pair}",
            f"  timeframe: {resolved_timeframe}",
            f"  latest_close: {signal['market_snapshot']['latest_close']}",
            f"  ema20: {signal['market_snapshot']['ema20']}",
            f"  ema50: {signal['market_snapshot']['ema50']}",
            f"  rsi: {signal['market_snapshot']['rsi']}",
            f"  macd_histogram: {signal['market_snapshot']['macd_histogram']}",
            f"  atr: {signal['market_snapshot']['atr']}",
            f"  support: {signal['market_snapshot']['support']}",
            f"  resistance: {signal['market_snapshot']['resistance']}",
            f"  structure: {signal['market_snapshot']['market_structure']}",
        ]
    )

    risk_text = "\n".join(
        [
            f"  risk_amount: ${signal['risk_amount']}",
            f"  risk_percent_applied: {signal['risk_percent_applied']}%",
            f"  lot_size: {signal['lot_size']}",
            f"  rr_ratio: {signal['rr_ratio']}",
            f"  max_daily_loss: {profile['max_daily_loss']}%",
            f"  max_open_trades: {profile['max_open_trades']}",
        ]
    )

    deterministic_text = "\n".join(
        [
            f"  direction: {signal['direction']}",
            f"  confidence: {signal['confidence']}%",
            f"  actionable: {signal['actionable']}",
            f"  entry: {signal['entry']}",
            f"  stop_loss: {signal['stop_loss']}",
            f"  take_profit: {signal['take_profit']}",
            f"  reasons: {', '.join(signal['reasons'])}",
        ]
    )

    prompt = build_trading_prompt(
        user_message=user_text,
        user_profile=profile_text,
        market_snapshot=market_snapshot_text,
        deterministic_signal=deterministic_text,
        risk_block=risk_text,
        rag_memory=semantic_context,
        strategy_docs=strategy_context,
        recent_trades=recent_trade_text,
        session_context="\n".join(
            block for block in [summary_context, recent_turn_text] if block.strip()
        ),
    )

    explanation = await ask_model(prompt)
    signal_id = str(uuid.uuid4())

    record = {
        "signal_id": signal_id,
        "user_id": user_id,
        "balance": resolved_balance,
        "session_id": trading_session_id,
        "pair": resolved_pair,
        "timeframe": resolved_timeframe,
        "direction": signal["direction"],
        "confidence": signal["confidence"],
        "entry": signal["entry"],
        "stop_loss": signal["stop_loss"],
        "take_profit": signal["take_profit"],
        "risk_amount": signal["risk_amount"],
        "lot_size": signal["lot_size"],
        "rr_ratio": signal["rr_ratio"],
        "reasons": signal["reasons"],
        "actionable": signal["actionable"],
        "market_snapshot": {**signal["market_snapshot"], "raw_payload_keys": list(raw_payload.keys())},
        "summary": explanation.strip() if explanation else signal["summary"],
        "status": "READY",
    }

    await _store_signal(record)
    await save_message("assistant", record["summary"], session_id=trading_session_id)
    await save_chat_message(trading_session_id, "assistant", record["summary"], metadata=record)
    await append_turn(trading_session_id, "assistant", record["summary"])
    await refresh_summary(trading_session_id, user_text, record["summary"])

    return record
