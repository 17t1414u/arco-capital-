"""
SQLite database manager for the trading module.

Tables:
  ohlcv   — daily OHLCV bars cached from Alpaca
  alerts  — price/indicator conditions set by the user
  orders  — paper/live order history
"""

import asyncio
import aiosqlite
from pathlib import Path
from config.settings import settings

_DDL = """
CREATE TABLE IF NOT EXISTS ohlcv (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker    TEXT    NOT NULL,
    date      TEXT    NOT NULL,   -- ISO-8601 YYYY-MM-DD
    open      REAL    NOT NULL,
    high      REAL    NOT NULL,
    low       REAL    NOT NULL,
    close     REAL    NOT NULL,
    volume    INTEGER NOT NULL,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS alerts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker         TEXT    NOT NULL,
    condition_type TEXT    NOT NULL,  -- 'price_below', 'price_above', 'rsi_below', 'rsi_above'
    threshold      REAL    NOT NULL,
    active         INTEGER NOT NULL DEFAULT 1,  -- 1=active, 0=triggered/cancelled
    created_at     TEXT    NOT NULL,
    triggered_at   TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    TEXT    NOT NULL UNIQUE,
    ticker      TEXT    NOT NULL,
    side        TEXT    NOT NULL,  -- 'buy' or 'sell'
    qty         REAL    NOT NULL,
    order_type  TEXT    NOT NULL DEFAULT 'market',
    status      TEXT    NOT NULL,
    filled_at   TEXT,
    filled_avg_price REAL,
    created_at  TEXT    NOT NULL
);
"""


async def init_db() -> None:
    """Create tables if they don't exist."""
    db_path = settings.trading_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(_DDL)
        await db.commit()


async def get_db() -> aiosqlite.Connection:
    """Return an open connection. Caller is responsible for closing."""
    db_path = settings.trading_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return await aiosqlite.connect(db_path)


if __name__ == "__main__":
    asyncio.run(init_db())
    print(f"[OK] Database initialised at {settings.trading_db_path}")
