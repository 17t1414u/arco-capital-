"""
Alpaca API wrappers exposed as CrewAI Tools.

Phase 1: read-only tools (price, bars, account info).
Phase 2: order execution tools are added here.
"""

import asyncio
from datetime import date, timedelta
from typing import Any, Coroutine, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config.settings import settings
from trading.tools.market_data import fetch_bars, get_latest_price
from trading.tools.indicators import rsi, sma, macd


def _run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """
    Run an async coroutine from any thread.

    CrewAI invokes tools on worker threads where no event loop exists.
    ``asyncio.get_event_loop()`` raises "There is no current event loop in
    thread 'MainThread'" in that context on Python 3.10+.

    This helper:
      - tries to use a running loop (unlikely in a sync tool context),
      - else creates a fresh loop, runs the coro, closes it.
    """
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None

    if running is not None:
        # Extremely rare path: called from inside an event loop.
        # asyncio.run() would fail here, so schedule on the running loop.
        return asyncio.run_coroutine_threadsafe(coro, running).result()

    # Normal path: no loop exists in this thread → create one.
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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
    intentional_short: bool = Field(
        default=False,
        description=(
            "Set to True only when explicitly entering a Path C short position "
            "(strategy.md v2.3 過熱反転売り). When False, SELL orders without "
            "existing long position are blocked to prevent accidental shorts."
        ),
    )


# ── Tools ──────────────────────────────────────────────────────────────────────

class GetLatestPriceTool(BaseTool):
    name: str = "get_latest_price"
    description: str = (
        "Fetch the latest closing price for a stock ticker. "
        "Returns the price as a float or an error message."
    )
    args_schema: Type[BaseModel] = TickerInput

    def _run(self, ticker: str) -> str:
        price = _run_async(get_latest_price(ticker.upper()))
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
        df = _run_async(fetch_bars(ticker.upper(), start, end))
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
        df = _run_async(fetch_bars(ticker.upper(), start, end))
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
        intentional_short: bool = False,
    ) -> str:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=settings.is_paper_trading,
        )
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        symbol = ticker.upper()

        # ── 🛡️ ガードレール: 意図しないショート建ての防止 (strategy.md v2.3) ──
        # SELL 注文は3パターンに分岐:
        #   1. LONG クローズ（保有あり）→ 通常通り通過
        #   2. 意図的SHORT (intentional_short=True、Path C 経由) → 通過
        #   3. 上記以外 → ブロック（誤発注によるショート建ての防止）
        if order_side == OrderSide.SELL:
            try:
                positions = client.get_all_positions()
                pos = next((p for p in positions if p.symbol == symbol), None)
                held_qty = float(pos.qty) if pos else 0.0

                if held_qty > 0:
                    # ケース1: LONG クローズ - qty が保有量を超えていなければ通過
                    if qty > held_qty:
                        return (
                            f"[BLOCKED] SELL {symbol} {qty}株 は保有数量({held_qty}株)を超過: "
                            f"部分売却の場合は qty <= 保有数量に調整してください"
                        )
                elif intentional_short:
                    # ケース2: 意図的SHORT 建て (Path C 経由のみ許可)
                    pass  # 通過
                else:
                    # ケース3: 保有なしの誤発注 SELL → ブロック
                    return (
                        f"[BLOCKED] SELL {symbol} {qty}株 はガードレールにより拒否: "
                        f"保有なし、かつ intentional_short=False。"
                        f"意図的にショート建てる場合は intentional_short=True を指定 "
                        f"(Path C 過熱反転シグナル経由のみ)。現在保有: {held_qty}株"
                    )
            except Exception as guard_exc:
                return f"[GUARD-ERROR] 保有確認失敗のため SELL を拒否: {guard_exc}"

        if order_type == "market":
            req = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=TimeInForce.DAY,
            )
        elif order_type == "limit" and limit_price is not None:
            req = LimitOrderRequest(
                symbol=symbol,
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
                f"[{mode}] Order submitted: {side.upper()} {qty} {symbol} "
                f"@ {order_type} | ID: {order.id} | Status: {order.status}"
            )
        except Exception as exc:
            return f"Order failed: {exc}"


# ── Convenience export ─────────────────────────────────────────────────────────

PHASE1_TOOLS = [GetLatestPriceTool(), GetBarsTool(), GetIndicatorsTool()]
PHASE2_TOOLS = PHASE1_TOOLS + [PlaceOrderTool()]
