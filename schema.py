from pydantic import BaseModel
from pydantic import Field
from datetime import datetime
from typing import List, Optional


class Part(BaseModel):
    type: str
    text: str


class ChatPayload(BaseModel):
    parts: List[Part]
    id: str
    role: str


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


class UploadedDocument(BaseModel):
    filename: str
    file_type: str
    chunks_indexed: int
    characters: int


class DocumentUploadResponse(BaseModel):
    status: str
    session_id: str
    files: list[UploadedDocument]


class TradingProfileRequest(BaseModel):
    user_id: str = "default"
    session_id: str = "default"
    balance: float = 1000.0
    risk_percent: float = 1.0
    preferred_pair: str = "XAUUSD"
    preferred_timeframe: str = "15M"
    style: str = "intraday"
    max_daily_loss: float = 3.0
    max_open_trades: int = 1
    preferred_sessions: list[str] = Field(default_factory=list)


class TradingBalanceUpdateRequest(BaseModel):
    session_id: str
    new_balance: float


class TradingProfileResponse(TradingProfileRequest):
    updated_at: datetime


class TradingSignalRequest(BaseModel):
    user_id: str = "default"
    session_id: str = "default"
    pair: Optional[str] = None
    timeframe: Optional[str] = None
    balance: Optional[float] = None
    message: str = ""


class TradingSignalResponse(BaseModel):
    status: str
    signal_id: str
    user_id: str
    balance: Optional[float] = None
    session_id: str
    pair: str
    timeframe: str
    direction: str
    confidence: float
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_amount: float
    lot_size: float
    rr_ratio: str
    reasons: list[str] = Field(default_factory=list)
    actionable: bool = True
    market_snapshot: dict | None = None
    summary: str = ""


class TradingTradeActionRequest(BaseModel):
    user_id: str = "default"
    signal_id: str


class TradingTradeActionResponse(BaseModel):
    trade_id: str = ""
    signal_id: str
    status: str
    message: str


class TradingTradeCloseRequest(BaseModel):
    outcome: str
    pnl: float = 0.0


class TradingDashboardResponse(BaseModel):
    user_id: str
    balance: float
    todays_pl: float
    win_rate: float
    open_trades: int
    profit_factor: float
    average_rr: str
    best_pair: str
    best_session: str
    best_market_condition: str
    recent_trades: list[dict] = Field(default_factory=list)
