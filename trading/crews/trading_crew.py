"""
TradingCrew — Phase 2.

Two-agent sequential workflow:
  1. AnalystAgent  → produces a trade signal (BUY/SELL/HOLD + rationale)
  2. TraderAgent   → executes the signal via Alpaca (paper or live)
"""

from crewai import Crew, Task, Process

from trading.agents.market_monitor import make_analyst_agent
from trading.agents.trader import make_trader_agent


class TradingCrew:
    def __init__(self) -> None:
        self._analyst = make_analyst_agent()
        self._trader = make_trader_agent()

    def run_signal(self, ticker: str, context: str = "") -> str:
        """
        Run a full analysis → execution cycle for *ticker*.

        *context* is optional additional context (e.g., "user wants to buy on dip").
        Returns the trader's execution report.
        """
        analyse_task = Task(
            description=(
                f"Analyse {ticker} using recent price data and technical indicators. "
                f"Produce a trade signal: BUY, SELL, or HOLD. "
                f"Include the current price, RSI, SMA-20, and MACD values. "
                f"Justify the signal in 2-3 sentences. "
                + (f"Additional context: {context}" if context else "")
            ),
            expected_output=(
                "A structured signal:\n"
                "Signal: BUY|SELL|HOLD\n"
                "Ticker: <ticker>\n"
                "Price:  $<price>\n"
                "RSI:    <value>\n"
                "Rationale: <2-3 sentences>"
            ),
            agent=self._analyst,
        )

        execute_task = Task(
            description=(
                f"Read the trade signal from the analyst and execute accordingly. "
                f"If signal is BUY or SELL, place a market order for 1 share of {ticker}. "
                f"If signal is HOLD, do not place any order. "
                f"Always confirm the current trading mode (paper/live) before acting. "
                f"Report the order ID and final status."
            ),
            expected_output="Execution report with order ID (or 'No order placed — HOLD signal').",
            agent=self._trader,
            context=[analyse_task],
        )

        crew = Crew(
            agents=[self._analyst, self._trader],
            tasks=[analyse_task, execute_task],
            process=Process.sequential,
            verbose=True,
        )
        return crew.kickoff()
