"""
Market data fetching via alpaca-py with SQLite cache layer.

Always tries the cache first; falls back to Alpaca API only for missing ranges.
"""

import asyncio
from datetime import date, timedelta
from typing import Optional

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from config.settings import settings
from trading.cache.ohlcv import get_cached_bars, save_bars


def _make_client() -> StockHistoricalDataClient:
    return StockHistoricalDataClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
    )


async def fetch_bars(
    ticker: str,
    start: date,
    end: Optional[date] = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Return daily OHLCV bars for *ticker* between *start* and *end*.
    Reads from cache when available; fetches from Alpaca for missing data.
    """
    if end is None:
        end = date.today() - timedelta(days=1)  # yesterday (market data lag)

    if use_cache:
        cached = await get_cached_bars(ticker, start, end)
        if cached is not None and not cached.empty:
            return cached

    # Fetch from Alpaca (sync SDK wrapped in thread)
    df = await asyncio.to_thread(_fetch_from_alpaca, ticker, start, end)

    if not df.empty and use_cache:
        await save_bars(ticker, df)

    return df


def _fetch_from_alpaca(ticker: str, start: date, end: date) -> pd.DataFrame:
    client = _make_client()
    request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame.Day,
        start=str(start),
        end=str(end),
    )
    bars = client.get_stock_bars(request)
    df = bars.df

    if df.empty:
        return df

    # alpaca-py returns a MultiIndex (symbol, timestamp); flatten it
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(ticker, level=0)

    df.index = pd.to_datetime(df.index).normalize()
    df.index.name = "date"
    return df[["open", "high", "low", "close", "volume"]]


async def get_latest_price(ticker: str) -> Optional[float]:
    """Return the latest available close price for *ticker*."""
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=7)  # look back up to 7 days for latest bar
    df = await fetch_bars(ticker, start, end, use_cache=True)
    if df.empty:
        return None
    return float(df["close"].iloc[-1])
