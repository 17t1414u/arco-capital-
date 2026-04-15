"""
Alpaca API wrappers exposed as CrewAI Tools.

Phase 1: read-only tools (price, bars, account info).
Phase 2: order execution tools are added here.
"""

import asyncio
from datetime import date, timedelta
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config.settings import settings
from trading.tools.market_data import fetch_bars, get_latest_price
from trading.tools.indicators import rsi, sma, macd


# ── Input schemas ──────────────────────────────────────────────────────────────

class TickerInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol, e.g. 'AAPL'")


class BarsInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    days: int = Field(default=30, description="Number of calendar days of history to fetch")


class OrderInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    side: str = Field(..., description="'buy' or 'sell'")
    qty: float = Field(..., description="Number of shares")
    order_type: str = Field(default="market", description="'market' or 'limit'")
    limit_price: Optional[float] = Field(default=None, description="Required for limit orders")


# ── Tools ──────────────────────────────────────────────────────────────────────

class GetLatestPriceTool(BaseTool):
    name: str = "get_latest_price"
    description: str = (
        "Fetch the latest closing price for a stock ticker. "
        "Returns the price as a float or an error message."
    )
    args_schema: Type[BaseModel] = TickerInput

    def _run(self, ticker: str) -> str:
        price = asyncio.get_event_loop().run_until_complete(get_latest_price(ticker.upper()))
        if price is None:
            return f"Could not retrieve price for {ticker}."
        return f"{ticker.upper()} latest close: ${price:.2f}"


class GetBarsTool(BaseTool):
    name: str = "get_bars"
    description: str = (
        "Fetch daily OHLCV bars for a stock over the past N days. "
        "Returns a summary of open, high, low, close, volume data."
    )
    args_schema: Type[BaseModel] = BarsInput

    def _run(self, ticker: str, days: int = 30) -> str:
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=days)
        df = asyncio.get_event_loop().run_until_complete(
            fetch_bars(ticker.upper(), start, end)
        )
        if df.empty:
            return f"No data found for {ticker} in the last {days} days."
        return (
            f"{ticker.upper()} ({days}d) — "
            f"High: ${df['high'].max():.2f}, "
            f"Low: ${df['low'].min():.2f}, "
            f"Last close: ${df['close'].iloc[-1]:.2f}, "
            f"Avg volume: {int(df['volume'].mean()):,}"
        )


class GetIndicatorsTool(BaseTool):
    name: str = "get_indicators"
    description: str = (
        "Calculate technical indicators (RSI-14, SMA-20, MACD) for a stock. "
        "Requires at least 30 days of history."
    )
    args_schema: Type[BaseModel] = TickerInput

    def _run(self, ticker: str) -> str:
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=60)
        df = asyncio.get_event_loop().run_until_complete(
            fetch_bars(ticker.upper(), start, end)
        )
        if df.empty or len(df) < 15:
            return f"Not enough data to compute indicators for {ticker}."

        rsi_val = rsi(df) if len(df) >= 15 else float("nan")
        sma_val = sma(df, 20) if len(df) >= 20 else float("nan")
        macd_vals = macd(df) if len(df) >= 26 else {}

        lines = [f"{ticker.upper()} Technical Indicators:"]
        lines.append(f"  RSI(14):  {rsi_val:.1f}")
        lines.append(f"  SMA(20):  ${sma_val:.2f}")
        if macd_vals:
            lines.append(f"  MACD:     {macd_vals['macd']:.4f}")
            lines.append(f"  Signal:   {macd_vals['signal']:.4f}")
            lines.append(f"  Hist:     {macd_vals['histogram']:.4f}")
        return "\n".join(lines)


class PlaceOrderTool(BaseTool):
    """Phase 2 tool — executes against Alpaca paper/live trading."""

    name: str = "place_order"
    description: str = (
        "Place a stock order via Alpaca. "
        "IMPORTANT: Only use in Paper Trading mode unless explicitly authorised for live trading. "
        "Supports market and limit orders."
    )
    args_schema: Type[BaseModel] = OrderInput

    def _run(
        self,
        ticker: str,
        side: str,
        qty: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ) -> str:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        from datetime import datetime

        client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=settings.is_paper_trading,
        )
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

        if order_type == "market":
            req = MarketOrderRequest(
                symbol=ticker.upper(),
                qty=qty,
                side=order_side,
                time_in_force=TimeInForce.DAY,
            )
        elif order_type == "limit" and limit_price is not None:
            req = LimitOrderRequest(
                symbol=ticker.upper(),
                qty=qty,
                side=order_side,
                time_in_force=TimeInForce.DAY,
                limit_price=limit_price,
            )
        else:
            return "Invalid order type or missing limit_price for limit order."

        try:
            order = client.submit_order(req)
            mode = "PAPER" if settings.is_paper_trading else "LIVE"
            return (
                f"[{mode}] Order submitted: {side.upper()} {qty} {ticker.upper()} "
                f"@ {order_type} | ID: {order.id} | Status: {order.status}"
            )
        except Exception as exc:
            return f"Order failed: {exc}"


# ── Convenience export ─────────────────────────────────────────────────────────

PHASE1_TOOLS = [GetLatestPriceTool(), GetBarsTool(), GetIndicatorsTool()]
PHASE2_TOOLS = PHASE1_TOOLS + [PlaceOrderTool()]
