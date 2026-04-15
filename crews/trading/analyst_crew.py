"""
AnalystCrew — アナリストクルー（並列情報収集）

4つのアナリストが並列で市場情報を収集・分析する。
TradingAgentsフレームワーク第1層。

フロー:
  FundamentalsAnalyst ┐
  SentimentAnalyst    ├─→ 4つの独立レポートを生成
  NewsAnalyst         │
  TechnicalAnalyst    ┘

使用例:
    crew = AnalystCrew(ticker="NVDA", context="本日NVDA決算発表予定")
    reports = crew.run()
"""

from crewai import Crew, Process, Task

from agents.trading.fundamentals_analyst import FundamentalsAnalystAgent
from agents.trading.sentiment_analyst import SentimentAnalystAgent
from agents.trading.news_analyst import NewsAnalystAgent
from agents.trading.technical_analyst import TechnicalAnalystAgent
from trading.tools.alpaca_tools import PHASE2_TOOLS
from trading.harness.guardrails import load_current_strategy
from crews.base_crew import BaseCrew


class AnalystCrew(BaseCrew):
    """
    4アナリストが並列で分析を行うクルー。

    Args:
        ticker:  分析対象の銘柄ティッカー
        context: 追加コンテキスト（ニュース・イベント等）
    """

    def __init__(self, ticker: str, context: str = ""):
        self.ticker = ticker.upper()
        self.context = context

    def build(self):
        strategy = load_current_strategy()

        # エージェント生成（ツール付き）
        fundamentals = FundamentalsAnalystAgent.build()
        sentiment = SentimentAnalystAgent.build()
        news = NewsAnalystAgent.build()
        technical = TechnicalAnalystAgent.build()
        technical.tools = PHASE2_TOOLS  # テクニカルはAlpacaデータ取得が必要

        # 現行戦略コンテキスト
        strategy_summary = (
            f"【現行戦略 strategy.md より】\n"
            f"- RSI BUY閾値: 35以下\n"
            f"- ストップロス: -5%\n"
            f"- 利確目標: +10%\n"
        )

        ctx = f"追加コンテキスト: {self.context}" if self.context else ""

        # タスク定義（並列実行）
        fundamentals_task = Task(
            description=f"""
{self.ticker} のファンダメンタルズ分析を行ってください。
{ctx}

【分析項目】
- 利用可能な財務情報（PER・EPS成長率・売上成長率・ROE）を評価
- 同業他社と比較した相対的バリュエーション
- 直近の業績トレンドと将来の成長見通し

【出力】BULLISH / BEARISH / NEUTRAL の判定と数値根拠
            """,
            expected_output=(
                "## ファンダメンタルズ分析: ${ticker}\n"
                "### 判定: BULLISH / BEARISH / NEUTRAL\n"
                "### 主要指標\n- PER: [値]\n- EPS成長率: [%]\n- ROE: [%]\n"
                "### 総合評価\n[200字以内のコメント]\n"
                "### リスク\n- [主要リスク1〜3個]"
            ).replace("${ticker}", self.ticker),
            agent=fundamentals,
        )

        sentiment_task = Task(
            description=f"""
{self.ticker} および市場全体のセンチメントを分析してください。
{ctx}

【分析項目】
- 現在の市場全体のセンチメント（恐怖/貪欲指数）
- {self.ticker} 固有のSNS・投資家センチメント
- オプション市場のPut/Callレシオ（利用可能であれば）
- 機関投資家の動向（利用可能であれば）

【出力】EXTREME_FEAR / FEAR / NEUTRAL / GREED / EXTREME_GREED の判定と根拠
            """,
            expected_output=(
                "## センチメント分析: ${ticker}\n"
                "### 判定: EXTREME_FEAR / FEAR / NEUTRAL / GREED / EXTREME_GREED\n"
                "### 市場センチメント\n[市場全体の状況]\n"
                "### 銘柄固有センチメント\n[${ticker}固有の状況]\n"
                "### 逆張りシグナル\n[過熱/冷却の兆候]"
            ).replace("${ticker}", self.ticker),
            agent=sentiment,
        )

        news_task = Task(
            description=f"""
{self.ticker} に関連するニュースとマクロ経済イベントを分析してください。
{ctx}

【分析項目】
- 企業固有のニュース（決算・製品発表・経営陣変更・規制）
- セクター全体に影響するニュース
- マクロ経済イベント（FOMC・経済指標・地政学リスク）
- 市場に既に価格織り込み済みかの判断（Price-in分析）

【出力】POSITIVE_HIGH / POSITIVE_LOW / NEUTRAL / NEGATIVE_LOW / NEGATIVE_HIGH の判定
            """,
            expected_output=(
                "## ニュース・マクロ分析: ${ticker}\n"
                "### 判定: POSITIVE_HIGH / POSITIVE_LOW / NEUTRAL / NEGATIVE_LOW / NEGATIVE_HIGH\n"
                "### 主要ニュース\n[上位3件のニュースと影響評価]\n"
                "### マクロ環境\n[関連するマクロ要因]\n"
                "### Price-in分析\n[市場の織り込み状況]"
            ).replace("${ticker}", self.ticker),
            agent=news,
        )

        technical_task = Task(
            description=f"""
{self.ticker} のテクニカル分析を行ってください。
{strategy_summary}
{ctx}

【手順】
1. get_indicators ツールで RSI(14)・SMA(20)・MACD を取得する
2. get_bars ツールで直近30日のOHLCVを取得してトレンドを確認する
3. 各指標をstrategy.mdのパラメータ（RSI<35=BUY候補等）と照合する
4. エントリー価格・ストップロス・利確目標を計算する

【出力】BUY / SELL / HOLD シグナルと具体的な価格水準
            """,
            expected_output=(
                "## テクニカル分析: ${ticker}\n"
                "### シグナル: BUY / SELL / HOLD\n"
                "### 指標値\n"
                "- RSI(14): [値] → [判定]\n"
                "- SMA(20): $[値] → [トレンド]\n"
                "- MACD: [値] → [判定]\n"
                "### 推奨価格水準\n"
                "- エントリー: $[値]\n"
                "- ストップロス: $[値] (-[%])\n"
                "- 利確目標: $[値] (+[%])"
            ).replace("${ticker}", self.ticker),
            agent=technical,
        )

        return Crew(
            agents=[fundamentals, sentiment, news, technical],
            tasks=[fundamentals_task, sentiment_task, news_task, technical_task],
            process=Process.sequential,  # CrewAIの並列はProが必要なため順次実行
            verbose=True,
        )

    def run(self) -> str:
        print(f"\n{'='*50}")
        print(f"  AnalystCrew 起動: {self.ticker}")
        print(f"  【ファンダメンタルズ/センチメント/ニュース/テクニカル】")
        print(f"{'='*50}\n")
        result = super().run()
        return result
