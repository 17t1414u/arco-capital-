"""
TraderAgent — Phase 2 agent that executes orders via Alpaca.
"""

from crewai import Agent
from config.llm import get_llm
from trading.tools.alpaca_tools import PHASE2_TOOLS


def make_trader_agent() -> Agent:
    return Agent(
        role="Execution Trader",
        goal=(
            "Receive a structured trade signal and execute the corresponding order "
            "via Alpaca. Confirm execution and report the filled order details."
        ),
        backstory=(
            "You are a disciplined execution trader. You never deviate from the signal "
            "you receive. You always confirm whether the system is in paper or live mode "
            "before placing any order, and you report execution details accurately."
        ),
        tools=PHASE2_TOOLS,
        llm=get_llm(),
        verbose=True,
        max_iter=5,
    )
