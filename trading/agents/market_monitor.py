"""
MarketMonitorAgent — CrewAI agent responsible for watching the watchlist,
evaluating alert conditions, and reporting triggered alerts.
"""

from crewai import Agent
from config.settings import settings
from config.llm import get_llm
from trading.tools.alpaca_tools import PHASE1_TOOLS


def make_market_monitor_agent() -> Agent:
    return Agent(
        role="Market Monitor",
        goal=(
            "Continuously check each ticker in the watchlist against the active alert conditions. "
            "For every condition that is met, produce a clear, actionable alert message."
        ),
        backstory=(
            "You are a quantitative analyst specialising in real-time market surveillance. "
            "You have direct access to live and historical price data via Alpaca, and you are "
            "skilled at evaluating technical conditions (price thresholds, RSI, moving averages). "
            "Your output is consumed by a Telegram bot that notifies the trader, so keep messages "
            "concise and precise."
        ),
        tools=PHASE1_TOOLS,
        llm=get_llm(),
        verbose=True,
        max_iter=10,
    )


def make_analyst_agent() -> Agent:
    """Phase 2: deeper analysis before trade execution."""
    return Agent(
        role="Quantitative Analyst",
        goal=(
            "Analyse price action and technical indicators for a given ticker "
            "and produce a structured trade signal (BUY / SELL / HOLD) with supporting rationale."
        ),
        backstory=(
            "You are a senior quant with deep expertise in technical analysis. "
            "You assess RSI, MACD, Bollinger Bands, and recent price momentum to form "
            "a view on the next likely move. Your signal is passed to the Trader agent for execution."
        ),
        tools=PHASE1_TOOLS,
        llm=get_llm(),
        verbose=True,
        max_iter=15,
    )
