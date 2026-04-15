"""
StrategyImprovementCrew — 戦略改善クルー（ハーネスエンジニアリング）

StrategyEngineerAgent が過去の取引データを分析し、
パラメータ改善提案と次バージョンの戦略仕様書を生成する。

使用例:
    import json
    from trading.cache.database import init_db
    from trading.cache.ohlcv import get_all_orders

    # 取引履歴を取得（簡略化）
    trade_history = "過去30日の取引: AAPL×3, NVDA×2 ..."
    crew = StrategyImprovementCrew(trade_history=trade_history, period="2026年4月")
    result = crew.run()
    print(result)
"""

from crewai import Crew, Process

from agents.trading.strategy_engineer import StrategyEngineerAgent
from tasks.trading.strategy_tasks import (
    make_strategy_review_task,
    make_backtest_design_task,
)
from crews.base_crew import BaseCrew


class StrategyImprovementCrew(BaseCrew):
    """
    売買戦略の評価・改善提案クルー。

    Args:
        trade_history: 過去の取引履歴テキスト
        period:        評価対象期間（例: "2026年4月", "直近30日"）
    """

    def __init__(self, trade_history: str, period: str = "直近30日"):
        self.trade_history = trade_history
        self.period = period

    def build(self):
        engineer = StrategyEngineerAgent.build()

        review_task = make_strategy_review_task(
            trade_history=self.trade_history,
            period=self.period,
            agent=engineer,
        )
        backtest_task = make_backtest_design_task(
            # デフォルトのパラメータグリッドを渡す（改善提案ベース）
            strategy_params={
                "rsi_buy_threshold": "25〜40（現行: 35）",
                "rsi_sell_threshold": "60〜75（現行: 70）",
                "stop_loss_pct": "3%〜7%（現行: 5%）",
                "take_profit_pct": "8%〜15%（現行: 10%）",
                "sma_period": "10〜30日（現行: 20日）",
            },
            agent=engineer,
        )
        backtest_task.context = [review_task]  # レビュー結果をバックテスト設計に活用

        return Crew(
            agents=[engineer],
            tasks=[review_task, backtest_task],
            process=Process.sequential,
            verbose=True,
        )

    def run(self) -> str:
        """
        戦略評価を実行し、改善提案レポートを返す。

        Returns:
            改善提案レポート + バックテスト設計書（日本語テキスト）
        """
        print(f"\n{'='*50}")
        print(f"  StrategyImprovementCrew 起動: {self.period}")
        print(f"{'='*50}\n")
        result = super().run()
        print(f"\n{'='*50}")
        print(f"  StrategyImprovementCrew 完了")
        print(f"  → outputs/ に評価レポートを保存しました")
        print(f"{'='*50}\n")
        return result
