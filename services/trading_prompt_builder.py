from services.trading_system_prompt import TRADING_SYSTEM_PROMPT


def build_trading_prompt(
    *,
    user_message: str,
    user_profile: str,
    market_snapshot: str,
    deterministic_signal: str,
    risk_block: str,
    rag_memory: str = "",
    strategy_docs: str = "",
    recent_trades: str = "",
    session_context: str = "",
) -> str:
    profile_block = user_profile.strip() if user_profile.strip() else "No trading profile saved yet."
    market_block = market_snapshot.strip() if market_snapshot.strip() else "No market snapshot available."
    signal_block = deterministic_signal.strip() if deterministic_signal.strip() else "No deterministic signal generated."
    risk_text = risk_block.strip() if risk_block.strip() else "No risk summary available."
    memory_block = rag_memory.strip() if rag_memory.strip() else "No RAG memory retrieved."
    strategy_block = strategy_docs.strip() if strategy_docs.strip() else "No uploaded strategy documents retrieved."
    trades_block = recent_trades.strip() if recent_trades.strip() else "No recent trades available."
    session_block = session_context.strip() if session_context.strip() else "No session context available."

    return f"""{TRADING_SYSTEM_PROMPT}

=== TRADING PROFILE ===
{profile_block}

=== MARKET SNAPSHOT ===
{market_block}

=== DETERMINISTIC SIGNAL ===
{signal_block}

=== RISK SUMMARY ===
{risk_text}

=== RETRIEVED RAG MEMORY ===
{memory_block}

=== UPLOADED STRATEGY DOCUMENTS ===
{strategy_block}

=== RECENT TRADES ===
{trades_block}

=== SESSION CONTEXT ===
{session_block}

=== USER MESSAGE ===
{user_message}

Assistant:
"""
