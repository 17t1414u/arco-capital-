"""
FullTradingCrew — フル自動売買パイプライン

TradingAgentsフレームワークの完全実装。
アナリスト → リサーチ → FundManager → RiskManager → 執行
の全5段階を自動実行する。

フロー:
  1. AnalystCrew   → 4軸分析レポート
  2. ResearchCrew  → Bull/Bear弁証法的議論
  3. FundManager   → 最終取引判断 + 執行計画
  4. RiskManager   → 承認ゲート
  5. Trader        → 注文執行（承認済みのみ）
  6. trade_log     → 構造化ログ記録

使用例:
    crew = FullTradingCrew(ticker="NVDA")
    result = crew.run()
"""

from crewai import Crew, Process, Task

from agents.trading.fund_manager import FundManagerAgent
from agents.trading.risk_manager import RiskManagerAgent
from trading.agents.trader import make_trader_agent
from trading.tools.alpaca_tools import PHASE2_TOOLS
from trading.harness.guardrails import load_current_strategy, run_pre_trade_checks
from trading.harness.trade_log import log_trade_decision
from crews.trading.analyst_crew import AnalystCrew
from crews.trading.research_crew import ResearchCrew
from crews.base_crew import BaseCrew


class FullTradingCrew(BaseCrew):
    """
    TradingAgentsフレームワーク完全実装クルー。

    Args:
        ticker:  分析・取引対象の銘柄ティッカー
        context: 追加コンテキスト（ニュース・イベント等）
        dry_run: True の場合、分析のみ行い注文は執行しない
    """

    def __init__(self, ticker: str, context: str = "", dry_run: bool = True):
        self.ticker = ticker.upper()
        self.context = context
        self.dry_run = dry_run

    def run(self) -> str:
        """
        5段階パイプラインを順次実行する。
        BaseCrew.run()をオーバーライドして段階的に実行する。
        """
        print(f"\n{'='*60}")
        print(f"  FullTradingCrew 起動: {self.ticker}")
        print(f"  モード: {'ドライラン（注文なし）' if self.dry_run else '⚠️ 実注文モード'}")
        print(f"{'='*60}\n")

        strategy = load_current_strategy()

        # ── STEP 1: アナリストクルー ───────────────────────────────────────
        print("\n📊 STEP 1/4: アナリストチーム分析開始...\n")
        analyst_crew = AnalystCrew(ticker=self.ticker, context=self.context)
        analyst_reports = analyst_crew.run()

        # ── STEP 2: リサーチクルー（Bull/Bear議論）───────────────────────
        print("\n⚔️  STEP 2/4: Bull/Bear弁証法的議論開始...\n")
        research_crew = ResearchCrew(
            ticker=self.ticker,
            analyst_reports=analyst_reports,
        )
        debate_result = research_crew.run()

        # ── STEP 3: FundManager判断 ───────────────────────────────────────
        print("\n🎯 STEP 3/4: FundManager最終判断...\n")
        fund_manager = FundManagerAgent.build()
        risk_manager = RiskManagerAgent.build()

        fund_decision_task = Task(
            description=f"""
以下のアナリストレポートとBull/Bear議論を統合し、{self.ticker} の最終取引判断を下してください。

【アナリストレポート】
{analyst_reports}

【Bull/Bear議論結果】
{debate_result}

【現行戦略（strategy.md）】
{strategy}

【判断手順】
1. 4つのアナリストシグナルを確認する（ファンダ/センチメント/ニュース/テクニカル）
2. Bull論拠とBear論拠のどちらが優勢かを評価する
3. strategy.md のエントリー条件をすべて満たしているか確認する
4. BUY/SELL/HOLDの判断を下す
5. 執行計画（エントリー価格・ストップロス・利確目標・ポジションサイズ）を策定する
6. RiskManagerへの承認申請書を作成する

【重要】
- strategy.md の条件を満たさない場合は必ずHOLDを選択する
- 判断根拠に用いた主要シグナルを箇条書きで明示する
            """,
            expected_output=(
                f"## FundManager最終判断: ${self.ticker}\n\n"
                "### 判断: BUY / SELL / HOLD\n\n"
                "### 判断根拠（主要シグナル）\n"
                "- ファンダメンタルズ: [BULLISH/BEARISH/NEUTRAL]\n"
                "- センチメント: [評価]\n"
                "- ニュース: [評価]\n"
                "- テクニカル: [BUY/SELL/HOLD]\n"
                "- Bull/Bear: [優勢な方の要約]\n\n"
                "### 執行計画（BUY/SELLの場合）\n"
                "- 注文種別: 成行 / 指値\n"
                "- エントリー価格: $[値]\n"
                "- ストップロス: $[値] (-[%])\n"
                "- 利確目標: $[値] (+[%])\n"
                "- ポジションサイズ: 総資産の[%]\n\n"
                "### RiskManagerへの承認申請\n"
                "[リスク評価に必要な情報の要約]"
            ),
            agent=fund_manager,
        )

        risk_approval_task = Task(
            description=f"""
FundManagerの取引計画を評価し、承認/否認の判定を行ってください。

【FundManagerの判断】
（上記タスクの結果を参照）

【評価基準（すべて満たす必要あり）】
1. ポジションサイズ ≤ 総資産の10%
2. ストップロスが設定されている
3. 同時保有銘柄数 ≤ 5銘柄
4. ポートフォリオドローダウン > -10%
5. strategy.md のエントリー条件を満たしている

【出力フォーマット】
APPROVED（承認）/ REJECTED（否認）/ REDUCE_SIZE（サイズ縮小して承認）
+ 詳細な理由
            """,
            expected_output=(
                "## RiskManager承認判定\n\n"
                "### 判定: APPROVED / REJECTED / REDUCE_SIZE\n\n"
                "### チェック結果\n"
                "- [ ] ポジションサイズ: [OK/NG]\n"
                "- [ ] ストップロス設定: [OK/NG]\n"
                "- [ ] 銘柄数制限: [OK/NG]\n"
                "- [ ] ドローダウン制限: [OK/NG]\n"
                "- [ ] strategy.md整合性: [OK/NG]\n\n"
                "### 判定理由\n[詳細な理由]\n\n"
                "### 修正推奨（REDUCE_SIZEの場合）\n[推奨ポジションサイズ]"
            ),
            agent=risk_manager,
            context=[fund_decision_task],
        )

        decision_crew = Crew(
            agents=[fund_manager, risk_manager],
            tasks=[fund_decision_task, risk_approval_task],
            process=Process.sequential,
            verbose=True,
        )
        decision_result = decision_crew.kickoff().raw

        # ── STEP 4: 注文執行（承認済みかつ非ドライランのみ）────────────────
        if self.dry_run:
            print(f"\n✅ ドライラン完了: 注文は執行されません")
            final_result = (
                f"## FullTradingCrew 分析完了（ドライラン）\n\n"
                f"### 銘柄: {self.ticker}\n\n"
                f"### アナリスト分析\n{analyst_reports}\n\n"
                f"### Bull/Bear議論\n{debate_result}\n\n"
                f"### FundManager判断 + RiskManager承認\n{decision_result}"
            )
        elif "APPROVED" in decision_result or "REDUCE_SIZE" in decision_result:
            print(f"\n⚡ STEP 4/4: 注文執行中...\n")
            trader = make_trader_agent()
            execution_task = Task(
                description=(
                    f"以下の承認済み取引計画を執行してください。\n\n"
                    f"【承認済み計画】\n{decision_result}\n\n"
                    f"【実行ルール】\n"
                    f"- ペーパートレード環境では必ずペーパー注文\n"
                    f"- ストップロスと同時に発注する\n"
                    f"- 執行後に注文IDと約定価格を報告する"
                ),
                expected_output=(
                    "## 注文執行レポート\n\n"
                    "- 注文ID: [ID]\n"
                    "- 執行価格: $[値]\n"
                    "- 注文状態: [状態]\n"
                    "- ストップロス: $[値]"
                ),
                agent=trader,
            )
            exec_crew = Crew(agents=[trader], tasks=[execution_task], process=Process.sequential, verbose=True)
            execution_result = exec_crew.kickoff().raw

            final_result = (
                f"## FullTradingCrew 実行完了\n\n"
                f"### 注文執行結果\n{execution_result}\n\n"
                f"### 判断根拠\n{decision_result}"
            )
        else:
            print(f"\n🚫 RiskManagerにより注文が否認されました")
            final_result = (
                f"## FullTradingCrew — 注文否認\n\n"
                f"### RiskManager判定\n{decision_result}"
            )

        # ── ログ記録 ──────────────────────────────────────────────────────
        print(f"\n📝 取引ログを記録中...")
        action = "HOLD"
        if "BUY" in decision_result and "APPROVED" in decision_result:
            action = "BUY"
        elif "SELL" in decision_result and "APPROVED" in decision_result:
            action = "SELL"

        log_trade_decision(
            ticker=self.ticker,
            action=action,
            entry_price=None,  # 実際の価格はTraderから取得
            position_size_pct=0.05,  # デフォルト
            signals={
                "fundamentals": "解析済み",
                "sentiment": "解析済み",
                "news": "解析済み",
                "technical": "解析済み",
            },
            bull_thesis=debate_result[:500],
            bear_thesis=debate_result[-500:],
            risk_approved="APPROVED" in decision_result,
            fund_manager_reasoning=decision_result[:1000],
        )

        print(f"\n{'='*60}")
        print(f"  FullTradingCrew 完了: {self.ticker} → {action}")
        print(f"{'='*60}\n")

        return final_result

    def build(self):
        # FullTradingCrewはrun()を直接オーバーライドするためbuild()は使用しない
        raise NotImplementedError("FullTradingCrew は run() を直接使用してください")
