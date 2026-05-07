"""
OHLCV read/write helpers — all traffic goes through SQLite cache first.
"""

import aiosqlite
from datetime import date, timedelta
from typing import Optional
import pandas as pd

from trading.cache.database import get_db


async def get_cached_bars(ticker: str, start: date, end: date) -> Optional[pd.DataFrame]:
    """Return cached OHLCV rows as a DataFrame, or None if not fully cached."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT date, open, high, low, close, volume FROM ohlcv "
            "WHERE ticker = ? AND date BETWEEN ? AND ? ORDER BY date",
            (ticker, start.isoformat(), end.isoformat()),
        )
        rows = await cursor.fetchall()

    if not rows:
        return None

    df = pd.DataFrame([dict(r) for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df


async def save_bars(ticker: str, df: pd.DataFrame) -> int:
    """Upsert OHLCV rows from a DataFrame (index = date). Returns rows saved."""
    rows = [
        (
            ticker,
            str(idx.date()),
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            int(row["volume"]),
        )
        for idx, row in df.iterrows()
    ]
    async with get_db() as db:
        await db.executemany(
            "INSERT OR REPLACE INTO ohlcv (ticker, date, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        await db.commit()
    return len(rows)


async def save_alert(ticker: str, condition_type: str, threshold: float) -> int:
    """Insert an alert; returns its row id."""
    from datetime import datetime
    async with get_db() as db:
        cursor = await db.execute(
            "INSERT INTO alerts (ticker, condition_type, threshold, created_at) VALUES (?, ?, ?, ?)",
            (ticker, condition_type, threshold, datetime.utcnow().isoformat()),
        )
        await db.commit()
        return cursor.lastrowid


async def get_active_alerts() -> list[dict]:
    """Return all active alert rows."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM alerts WHERE active = 1"
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def deactivate_alert(alert_id: int) -> None:
    """Mark an alert as triggered."""
    from datetime import datetime
    async with get_db() as db:
        await db.execute(
            "UPDATE alerts SET active = 0, triggered_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), alert_id),
        )
        await db.commit()


async def save_order(order_data: dict) -> None:
    """Upsert an order record."""
    async with get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO orders "
            "(order_id, ticker, side, qty, order_type, status, filled_at, filled_avg_price, created_at) "
            "VALUES (:order_id, :ticker, :side, :qty, :order_type, :status, :filled_at, :filled_avg_price, :created_at)",
            order_data,
        )
        await db.commit()
