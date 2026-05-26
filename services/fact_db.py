import asyncio
import os
import asyncpg

DB_CONFIG = {
    "user":     os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "database": os.getenv("POSTGRES_DB"),
    "host":     os.getenv("POSTGRES_HOST", "postgres"),
    "port":     int(os.getenv("POSTGRES_PORT", 5432))
}

pool = None


# -------------------------
# INIT CONNECTION POOL
# -------------------------
async def init_db():
    global pool

    retries = 10
    delay = 2
    for attempt in range(1, retries + 1):
        try:
            pool = await asyncpg.create_pool(**DB_CONFIG)
            print("[DB CONNECT] Successfully connected to Postgres database.")
            break
        except Exception as e:
            if attempt == retries:
                print(f"[DB ERROR] Final connection attempt {attempt} failed: {e}")
                raise e
            print(f"[DB CONNECT] Attempt {attempt} failed: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)

    async with pool.acquire() as conn:
        # Existing user_facts table...
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_facts (
                key          TEXT PRIMARY KEY,
                value        TEXT NOT NULL,
                memory_type  TEXT NOT NULL DEFAULT 'general',
                confidence   FLOAT NOT NULL DEFAULT 1.0,
                source       TEXT NOT NULL DEFAULT 'user',
                updated_at   TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Chat Sessions Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id           TEXT PRIMARY KEY,
                title        TEXT NOT NULL,
                created_at   TIMESTAMPTZ DEFAULT NOW(),
                updated_at   TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Chat Messages Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id           SERIAL PRIMARY KEY,
                session_id   TEXT REFERENCES chat_sessions(id) ON DELETE CASCADE,
                role         TEXT NOT NULL,
                content      TEXT NOT NULL,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Migration for existing user_facts...
        for col, definition in [
            ("memory_type", "TEXT NOT NULL DEFAULT 'general'"),
            ("confidence",  "FLOAT NOT NULL DEFAULT '1.0'"),
            ("source",      "TEXT NOT NULL DEFAULT 'user'"),
            ("updated_at",  "TIMESTAMPTZ DEFAULT NOW()"),
        ]:
            await conn.execute(f"ALTER TABLE user_facts ADD COLUMN IF NOT EXISTS {col} {definition};")

# -------------------------
# CHAT SESSIONS & MESSAGES
# -------------------------
async def create_session(session_id: str, title: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO chat_sessions (id, title, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                updated_at = NOW();
        """, session_id, title)

async def get_sessions():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM chat_sessions ORDER BY updated_at DESC;")
        return [dict(row) for row in rows]

async def delete_session(session_id: str):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM chat_sessions WHERE id = $1;", session_id)

async def save_chat_message(session_id: str, role: str, content: str):
    async with pool.acquire() as conn:
        # Ensure session exists first
        exists = await conn.fetchval("SELECT 1 FROM chat_sessions WHERE id = $1", session_id)
        if not exists:
            await create_session(session_id, content[:50] if role == 'user' else "New Chat")
        
        await conn.execute("""
            INSERT INTO chat_messages (session_id, role, content, created_at)
            VALUES ($1, $2, $3, NOW());
        """, session_id, role, content)
        
        # Update session timestamp
        await conn.execute("UPDATE chat_sessions SET updated_at = NOW() WHERE id = $1", session_id)

async def get_session_history(session_id: str):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT role, content, created_at FROM chat_messages
            WHERE session_id = $1
            ORDER BY created_at ASC;
        """, session_id)
        return [dict(row) for row in rows]


# -------------------------
# SAVE FACT (TYPED UPSERT)
# -------------------------
async def save_fact(
    key: str,
    value: str,
    memory_type: str = "general",
    confidence: float = 1.0,
    source: str = "user"
):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO user_facts (key, value, memory_type, confidence, source, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (key)
            DO UPDATE SET
                value       = EXCLUDED.value,
                memory_type = EXCLUDED.memory_type,
                confidence  = EXCLUDED.confidence,
                source      = EXCLUDED.source,
                updated_at  = NOW();
        """, key, value, memory_type, confidence, source)


# -------------------------
# GET IDENTITY FACTS (highest trust — always injected)
# -------------------------
async def get_identity_facts() -> dict:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT key, value FROM user_facts
            WHERE memory_type = 'identity'
            ORDER BY updated_at DESC;
        """)
        return {row["key"]: row["value"] for row in rows}


# -------------------------
# GET ALL FACTS (sorted by confidence DESC)
# -------------------------
async def get_facts() -> dict:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT key, value, memory_type, confidence
            FROM user_facts
            ORDER BY confidence DESC, updated_at DESC;
        """)
        return {row["key"]: row["value"] for row in rows}


# -------------------------
# GET FULL FACT RECORDS (for contradiction detection)
# -------------------------
async def get_fact_records() -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT key, value, memory_type, confidence, source
            FROM user_facts
            ORDER BY confidence DESC;
        """)
        return [dict(row) for row in rows]


# -------------------------
# DELETE FACT (used by contradiction resolver)
# -------------------------
async def delete_fact(key: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM user_facts WHERE key = $1;", key
        )
