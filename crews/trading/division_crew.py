"""
TradingDivisionCrew — 資産運用事業部の階層型クルー。

Process.hierarchical:
  manager_agent: TradingDirector (allow_delegation=True)
  agents:        [InvestmentAnalyst, StrategyEngineer, SNSReporter]

RULE-01: Paper Trading 固定 (BROKER=alpaca-paper / LIVE_TRADING=false)
RULE-10: trade_log.jsonl への記録必須
"""

from __future__ import annotations

from crewai import Crew, Process

from agents.trading import (
    InvestmentAnalystAgent,
    SNSReporterAgent,
    StrategyEngineerAgent,
)
from agents.trading.director import TradingDirectorAgent
from crews.base_crew import BaseCrew
from operations.guardrails_loader import ModeManager, load_guardrails
from tasks.trading.weekly_tasks import build_trading_week1_tasks


class TradingDivisionCrew(BaseCrew):
    """資産運用事業部 Week1 階層型クルー。

    Parameters
    ----------
    ticker:
        分析対象ティッカー (既定: ``NVDA``)
    weekly_note_price_jpy:
        週報 note の販売価格 (既定 ¥980)
    """

    DIVISION_KEY = "trading"

    def __init__(
        self,
        ticker: str = "NVDA",
        weekly_note_price_jpy: int = 980,
    ) -> None:
        self.ticker = ticker.upper()
        self.weekly_note_price_jpy = weekly_note_price_jpy
        self._guardrails = load_guardrails()
        self._mode_manager = ModeManager(self._guardrails)

        mode = self._mode_manager.division_mode(self.DIVISION_KEY)
        if mode == "A":
            print(
                f"[{self.DIVISION_KEY}] Mode A (Dry-run) — X投稿・note公開は無効化。"
            )
        elif mode == "B":
            print(
                f"[{self.DIVISION_KEY}] Mode B (Semi-live) — "
                "外部送信前にオーナー承認。Paper Trading 固定。"
            )
        elif mode == "C":
            print(
                f"[{self.DIVISION_KEY}] Mode C (Full-live) — "
                "自動実行モード。Paper Trading は変わらず固定。"
            )

    def build(self) -> Crew:
        director = TradingDirectorAgent.build()
        analyst = InvestmentAnalystAgent.build()
        engineer = StrategyEngineerAgent.build()
        reporter = SNSReporterAgent.build()

        api_cfg = self._guardrails.budget("anthropic_api")

        tasks = build_trading_week1_tasks(
            director=director,
            analyst=analyst,
            engineer=engineer,
            reporter=reporter,
            ticker=self.ticker,
            api_daily_cap_jpy=int(api_cfg["daily_limit_jpy"]),
            weekly_note_price_jpy=self.weekly_note_price_jpy,
        )

        return Crew(
            agents=[analyst, engineer, reporter],
            tasks=tasks,
            process=Process.hierarchical,
            manager_agent=director,
            memory=True,
            verbose=True,
        )


if __name__ == "__main__":  # pragma: no cover
    crew = TradingDivisionCrew()
    print(crew.run())
