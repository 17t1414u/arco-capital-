"""
ResearchCrew — リサーチクルー（弁証法的推論）

Bull/BearリサーチャーがアナリストレポートをもとにDebateを行い、
バランスのとれた投資見解を形成する。
TradingAgentsフレームワーク第2層。

フロー:
  BullResearcher → 強気論拠構築
  BearResearcher → 弱気論拠構築 + Bull論への反論
  → 統合された投資見解レポート

使用例:
    crew = ResearchCrew(ticker="NVDA", analyst_reports="[アナリストレポート]")
    debate_result = crew.run()
"""

from crewai import Crew, Process, Task

from agents.trading.bull_researcher import BullResearcherAgent
from agents.trading.bear_researcher import BearResearcherAgent
from crews.base_crew import BaseCrew


class ResearchCrew(BaseCrew):
    """
    Bull/Bearの弁証法的議論クルー。

    Args:
        ticker:          分析対象の銘柄ティッカー
        analyst_reports: AnalystCrewの出力テキスト
    """

    def __init__(self, ticker: str, analyst_reports: str):
        self.ticker = ticker.upper()
        self.analyst_reports = analyst_reports

    def build(self):
        bull = BullResearcherAgent.build()
        bear = BearResearcherAgent.build()

        bull_task = Task(
            description=f"""
以下のアナリストレポートをもとに、{self.ticker} の強気（BUY）シナリオを構築してください。

【アナリストレポート】
{self.analyst_reports}

【あなたの役割】
- BULLシナリオを支持するすべての根拠を論理的に構築する
- 上昇余地の定量的な推定（価格目標）
- 主要カタリスト（上昇の触媒）を特定する
- ベアリサーチャーが提示するであろう反論への先回り対応
- 根拠のない楽観論は禁止 — データに基づく論拠のみ

【禁止事項】
- 「なんとなく上がりそう」などの感覚的な表現
- ベア論拠を完全に無視した一方的な楽観論
            """,
            expected_output=(
                f"## Bull論拠: ${self.ticker}\n\n"
                "### 強気シナリオ概要\n[1〜2文で要約]\n\n"
                "### 主要上昇根拠（データ付き）\n"
                "1. [根拠1 + 数値]\n2. [根拠2 + 数値]\n3. [根拠3 + 数値]\n\n"
                "### 主要カタリスト\n- [カタリスト1]\n- [カタリスト2]\n\n"
                "### 価格目標（12ヶ月）\n$[値] （上昇余地: +[%]）\n\n"
                "### ベア論への先回り反論\n[予想されるベア論拠への反論]"
            ),
            agent=bull,
        )

        bear_task = Task(
            description=f"""
以下のアナリストレポートとBull論拠をもとに、{self.ticker} の弱気（SELL/HOLD）シナリオを構築してください。

【アナリストレポート】
{self.analyst_reports}

【あなたの役割】
- BEARシナリオを支持するすべてのリスク・脆弱性を論理的に構築する
- Bull論拠の各項目に対する具体的な反論を提示する
- 下落リスクの定量的な推定（下落目標価格）
- 過度な悲観論は禁止 — データに基づくリスク評価のみ

【特に重視すること】
- バリュエーションリスク（割高感）
- 競争環境の悪化リスク
- マクロ逆風の影響
- 過去の類似ケースからの教訓
            """,
            expected_output=(
                f"## Bear論拠: ${self.ticker}\n\n"
                "### 弱気シナリオ概要\n[1〜2文で要約]\n\n"
                "### 主要下落リスク（データ付き）\n"
                "1. [リスク1 + 根拠]\n2. [リスク2 + 根拠]\n3. [リスク3 + 根拠]\n\n"
                "### Bull論拠への反論\n"
                "- Bull論拠1への反論: [内容]\n"
                "- Bull論拠2への反論: [内容]\n\n"
                "### 下落目標価格（最悪シナリオ）\n$[値] （下落幅: -[%]）\n\n"
                "### 総合リスク評価\nHIGH / MEDIUM / LOW"
            ),
            agent=bear,
            context=[bull_task],  # Bull論拠を参照して反論を構築
        )

        return Crew(
            agents=[bull, bear],
            tasks=[bull_task, bear_task],
            process=Process.sequential,
            verbose=True,
        )

    def run(self) -> str:
        print(f"\n{'='*50}")
        print(f"  ResearchCrew 起動: {self.ticker}")
        print(f"  【Bull vs Bear 弁証法的議論】")
        print(f"{'='*50}\n")
        result = super().run()
        return result
