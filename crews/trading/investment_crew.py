"""
InvestmentCrew — 投資クルー

フロー:
  InvestmentAnalystAgent → (BUY/SELLシグナル) → TraderAgent

既存の trading/agents/trader.py の make_trader_agent() を活用し、
新しい InvestmentAnalystAgent と組み合わせてフルパイプラインを構成する。

使用例:
    crew = InvestmentCrew(ticker="NVDA")
    result = crew.run()
    print(result)
"""

from crewai import Crew, Process

from agents.trading.investment_analyst import InvestmentAnalystAgent
from trading.agents.trader import make_trader_agent
from tasks.trading.analysis_tasks import make_analysis_task, make_trade_decision_task
from trading.tools.alpaca_tools import PHASE2_TOOLS
from crews.base_crew import BaseCrew


class InvestmentCrew(BaseCrew):
    """
    銘柄分析から注文執行までの完全自動投資パイプライン。

    Args:
        ticker: 分析・取引対象の銘柄ティッカー（例: "AAPL"）
    """

    def __init__(self, ticker: str):
        self.ticker = ticker.upper()

    def build(self):
        # エージェントをインスタンス化
        analyst = InvestmentAnalystAgent.build()
        analyst.tools = PHASE2_TOOLS  # 価格データ取得ツールを付与

        trader = make_trader_agent()

        # タスクを生成
        analysis_task = make_analysis_task(
            ticker=self.ticker,
            agent=analyst,
        )
        trade_task = make_trade_decision_task(
            ticker=self.ticker,
            analysis_result="{analysis_task_output}",  # CrewAI がパイプライン実行時に補完
            agent=trader,
        )
        trade_task.context = [analysis_task]  # 分析結果をコンテキストとして渡す

        return Crew(
            agents=[analyst, trader],
            tasks=[analysis_task, trade_task],
            process=Process.sequential,  # 分析 → 執行の順番を厳守
            verbose=True,
        )

    def run(self) -> str:
        """
        クルーを実行し、注文実行レポートを返す。

        Returns:
            注文実行レポート（日本語テキスト）
        """
        print(f"\n{'='*50}")
        print(f"  InvestmentCrew 起動: {self.ticker}")
        print(f"{'='*50}\n")
        result = super().run()
        print(f"\n{'='*50}")
        print(f"  InvestmentCrew 完了: {self.ticker}")
        print(f"{'='*50}\n")
        return result
