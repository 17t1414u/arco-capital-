"""
MonitorCrew — Phase 1.

Runs a polling loop that:
  1. Loads active alerts from SQLite.
  2. Fetches latest price/indicator data for each unique ticker.
  3. Evaluates conditions via the MarketMonitorAgent.
  4. Sends Telegram alerts for any triggered conditions.
  5. Deactivates triggered alerts in SQLite.

The crew also spawns the Telegram bot in a background thread so that
users can add/cancel alerts while monitoring is running.
"""

import asyncio
import logging
import threading
from datetime import date, timedelta
from typing import Optional

from crewai import Crew, Task, Process

from config.settings import settings
from trading.agents.market_monitor import make_market_monitor_agent
from trading.cache.ohlcv import get_active_alerts, deactivate_alert
from trading.tools.market_data import fetch_bars
from trading.tools.indicators import check_condition
from trading.interface.telegram_bot import build_application, send_alert

logger = logging.getLogger(__name__)


class MonitorCrew:
    """Phase 1: price/indicator alert monitoring with Telegram notification."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self._agent = make_market_monitor_agent()
        self._bot_app: Optional[object] = None

    # ── Telegram bot (background thread) ──────────────────────────────────────

    def _start_telegram_bot(self) -> None:
        if not settings.telegram_bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled.")
            return
        self._bot_app = build_application()

        def _run() -> None:
            self._bot_app.run_polling()

        t = threading.Thread(target=_run, daemon=True, name="telegram-bot")
        t.start()
        logger.info("Telegram bot started in background thread.")

    # ── Core polling loop ──────────────────────────────────────────────────────

    async def _poll_once(self) -> list[str]:
        """Check all active alerts once. Returns list of triggered messages."""
        alerts = await get_active_alerts()
        if not alerts:
            logger.debug("No active alerts.")
            return []

        # Batch-fetch bars for unique tickers
        tickers = list({a["ticker"] for a in alerts})
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=60)  # enough for RSI/MACD
        bars = {}
        for ticker in tickers:
            df = await fetch_bars(ticker, start, end)
            if not df.empty:
                bars[ticker] = df

        triggered_messages = []
        for alert in alerts:
            ticker = alert["ticker"]
            if ticker not in bars:
                logger.warning("No price data for %s — skipping alert #%d", ticker, alert["id"])
                continue

            df = bars[ticker]
            if check_condition(alert["condition_type"], alert["threshold"], df):
                latest = float(df["close"].iloc[-1])
                cond = alert["condition_type"].replace("_", " ")
                msg = (
                    f"ALERT #{alert['id']} — {ticker}\n"
                    f"Condition: {cond} {alert['threshold']}\n"
                    f"Current price: ${latest:.2f}"
                )
                triggered_messages.append(msg)
                if not self.dry_run:
                    await deactivate_alert(alert["id"])
                    await send_alert(msg, self._bot_app)
                else:
                    logger.info("[DRY RUN] %s", msg)

        return triggered_messages

    async def _run_loop(self) -> None:
        logger.info(
            "MonitorCrew polling loop started. Interval: %ds | Mode: %s",
            settings.poll_interval_seconds,
            "DRY RUN" if self.dry_run else ("PAPER" if settings.is_paper_trading else "LIVE"),
        )
        while True:
            try:
                triggered = await self._poll_once()
                if triggered:
                    logger.info("Triggered alerts: %d", len(triggered))
            except Exception as exc:
                logger.error("Poll error: %s", exc, exc_info=True)
            await asyncio.sleep(settings.poll_interval_seconds)

    def run(self, with_telegram: bool = True) -> None:
        """Start the monitoring loop (blocking)."""
        from trading.cache.database import init_db
        asyncio.run(init_db())

        if with_telegram and not self.dry_run:
            self._start_telegram_bot()

        asyncio.run(self._run_loop())

    # ── One-shot CrewAI analysis (optional LLM analysis on demand) ────────────

    def analyse_ticker(self, ticker: str) -> str:
        """
        Ask the MarketMonitorAgent to produce a narrative analysis for *ticker*.
        Returns the agent's output string.
        """
        task = Task(
            description=(
                f"Fetch the latest price and compute technical indicators for {ticker}. "
                f"Summarise whether any notable conditions are present "
                f"(e.g., oversold RSI, price near support/resistance, MACD crossover). "
                f"Keep the output to 3-5 bullet points."
            ),
            expected_output="A 3-5 bullet point technical summary for the ticker.",
            agent=self._agent,
        )
        crew = Crew(
            agents=[self._agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )
        return crew.kickoff()
