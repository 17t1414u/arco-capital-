"""
SNSCrew — SNSコンテンツ生成クルー

SNSReporterAgent がマーケット情報またはトレード結果を
X(Twitter)用投稿テキストに変換する。

使用例:
    # マーケット情報投稿
    crew = SNSCrew(
        post_type="market_news",
        context="本日のNASDAQは+1.2%上昇。NVDAが半導体セクターを牽引...",
    )
    result = crew.run()

    # トレード結果投稿
    crew = SNSCrew(
        post_type="trade_result",
        trade_data={
            "ticker": "AAPL",
            "action": "BUY→SELL",
            "entry_price": 195.50,
            "exit_price": 214.80,
            "pnl_pct": "+9.9%",
            "pnl_usd": "+$193",
            "comment": "RSI過売りからの反発を的中",
        },
    )
    result = crew.run()
"""

from crewai import Crew, Process

from agents.trading.sns_reporter import SNSReporterAgent
from tasks.trading.sns_tasks import (
    make_market_news_post_task,
    make_trade_result_post_task,
    make_monthly_summary_post_task,
)
from crews.base_crew import BaseCrew


class SNSCrew(BaseCrew):
    """
    SNSコンテンツ生成クルー。

    Args:
        post_type:     投稿種別 "market_news" | "trade_result" | "monthly_summary"
        context:       マーケット情報テキスト（market_news 用）
        trade_data:    取引データ辞書（trade_result 用）
        monthly_stats: 月次統計辞書（monthly_summary 用）
    """

    def __init__(
        self,
        post_type: str,
        context: str = "",
        trade_data: dict | None = None,
        monthly_stats: dict | None = None,
    ):
        valid_types = {"market_news", "trade_result", "monthly_summary"}
        if post_type not in valid_types:
            raise ValueError(
                f"post_type は {valid_types} のいずれかを指定してください。"
            )
        self.post_type = post_type
        self.context = context
        self.trade_data = trade_data or {}
        self.monthly_stats = monthly_stats or {}

    def build(self):
        reporter = SNSReporterAgent.build()

        if self.post_type == "market_news":
            task = make_market_news_post_task(
                market_context=self.context,
                agent=reporter,
            )
        elif self.post_type == "trade_result":
            task = make_trade_result_post_task(
                trade_data=self.trade_data,
                agent=reporter,
            )
        else:  # monthly_summary
            task = make_monthly_summary_post_task(
                monthly_stats=self.monthly_stats,
                agent=reporter,
            )

        return Crew(
            agents=[reporter],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )

    def run(self) -> str:
        """
        SNSコンテンツを生成し、投稿テキストを返す。

        Returns:
            X(Twitter)投稿テキスト（日本語）
        """
        print(f"\n{'='*50}")
        print(f"  SNSCrew 起動: {self.post_type}")
        print(f"{'='*50}\n")
        result = super().run()
        print(f"\n{'='*50}")
        print(f"  SNSCrew 完了")
        print(f"  → outputs/ に投稿テキストを保存しました")
        print(f"{'='*50}\n")
        return result
