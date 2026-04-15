"""
OptimizerCrew — 戦略オプティマイザークルー（自己改善ループ）

週次/月次で稼働し、過去の取引ログを分析して
strategy.md の改訂案を生成する。
TradingAgentsフレームワーク 自己改善層。

AGENTS.md: 提案のみ行い、人間の承認後にデプロイする。

使用例:
    crew = OptimizerCrew(period="2026年4月")
    result = crew.run()
    # → outputs/strategy_proposal_v2.md に改訂案を保存
"""

from pathlib import Path
from crewai import Crew, Process, Task

from agents.trading.optimizer import OptimizerAgent
from trading.harness.trade_log import format_logs_for_optimizer, get_performance_summary
from trading.harness.guardrails import load_current_strategy
from crews.base_crew import BaseCrew
from config.settings import settings


class OptimizerCrew(BaseCrew):
    """
    戦略改善提案クルー（オプティマイザループ）。

    Args:
        period: 評価対象期間（例: "2026年4月", "直近30日"）
        log_count: 分析する取引ログの件数
    """

    def __init__(self, period: str = "直近30日", log_count: int = 50):
        self.period = period
        self.log_count = log_count

    def build(self):
        optimizer = OptimizerAgent.build()
        current_strategy = load_current_strategy()
        trade_logs = format_logs_for_optimizer(self.log_count)
        perf_summary = get_performance_summary(self.log_count)

        # パフォーマンスサマリーをテキスト化
        if isinstance(perf_summary, dict) and "win_rate" in perf_summary:
            perf_text = (
                f"勝率: {perf_summary['win_rate']:.1f}% | "
                f"PF: {perf_summary['profit_factor']:.2f} | "
                f"平均品質スコア: {perf_summary['avg_quality_score']:.1f}/5.0"
            )
        else:
            perf_text = "取引データが不足しています（初回実行の場合）"

        performance_review_task = Task(
            description=f"""
{self.period}の取引ログを分析し、現行戦略のパフォーマンス評価を行ってください。

【現行戦略（strategy.md）】
{current_strategy}

【取引ログ（直近{self.log_count}件）】
{trade_logs}

【現行パフォーマンス概要】
{perf_text}

【分析手順】
1. 品質スコアの低い取引（1〜2点）の共通パターンを特定する
2. 品質スコアの高い取引（4〜5点）の共通要因を特定する
3. strategy.md のどのパラメータが最も改善余地があるかを特定する
4. 失敗パターンのTop3を定量的に分析する
5. 現行戦略の強みと弱みをまとめる

【パフォーマンス合否判定基準】
- 勝率 ≥ 50%
- プロフィットファクター ≥ 1.5
- シャープレシオ ≥ 1.0
- 最大ドローダウン ≤ -10%

現在の戦略はこれらの基準を満たしているか評価する。
            """,
            expected_output=(
                f"## パフォーマンス評価レポート: {self.period}\n\n"
                "### 総合評価: PASS / FAIL / WARNING\n\n"
                "### KPI達成状況\n"
                "- 勝率: [%] → [PASS/FAIL]\n"
                "- PF: [値] → [PASS/FAIL]\n"
                "- 最大DD: [%] → [PASS/FAIL]\n\n"
                "### 失敗パターンTop3\n"
                "1. [パターン]: [頻度]回 — [原因]\n"
                "2. [パターン]: [頻度]回 — [原因]\n"
                "3. [パターン]: [頻度]回 — [原因]\n\n"
                "### 成功パターン\n[共通要因]\n\n"
                "### 改善が必要なパラメータ\n[優先度順リスト]"
            ),
            agent=optimizer,
        )

        strategy_proposal_task = Task(
            description=f"""
パフォーマンス評価結果をもとに、次バージョンの strategy.md 改訂案を作成してください。

【重要な制約】
1. 変更は小さく、検証可能なものに限定する（急激な変更は禁止）
2. すべての変更に数値的根拠を添える
3. バックテスト推奨シナリオを必ず提案する
4. 自己判断でのデプロイは行わない — 提案書の作成のみ
5. 変更スコープ: パラメータ調整・プロンプト改善のみ（アーキテクチャ変更は禁止）

【改訂の対象となり得る項目】
- RSI閾値（BUY/SELL）
- ストップロス幅
- 利確目標
- SMA期間
- エントリー条件の組み合わせロジック
- エージェントへの指示（プロンプト）

【出力形式】
次バージョン strategy.md をそのまま使えるMarkdown形式で出力する。
バージョン番号・変更日・変更内容・根拠を必ず含める。
            """,
            expected_output=(
                "# 売買戦略 strategy.md [次バージョン提案]\n"
                "# ⚠️ これは提案書です。人間の承認とバックテスト検証後にデプロイしてください\n\n"
                "## メタ情報\n"
                "- バージョン: v[X.X]-proposal\n"
                "- 提案日: [日付]\n"
                "- 提案者: OptimizerAgent\n"
                "- 前バージョン比の変更点: [箇条書き]\n\n"
                "[以下、完全な strategy.md 内容]\n\n"
                "---\n\n"
                "## バックテスト推奨シナリオ\n"
                "- テスト期間: [推奨期間]\n"
                "- テスト銘柄: [推奨銘柄]\n"
                "- 評価指標: 勝率・PF・最大DD\n"
                "- 合否基準: [明確な数値基準]\n\n"
                "## ロールバック条件\n"
                "- デプロイ後48時間以内にシャープレシオが[X]を下回った場合"
            ),
            agent=optimizer,
            context=[performance_review_task],
        )

        return Crew(
            agents=[optimizer],
            tasks=[performance_review_task, strategy_proposal_task],
            process=Process.sequential,
            verbose=True,
        )

    def run(self) -> str:
        print(f"\n{'='*60}")
        print(f"  OptimizerCrew 起動: {self.period}")
        print(f"  【自己改善ループ — strategy.md 改訂案生成】")
        print(f"{'='*60}\n")

        result = super().run()

        # 改訂案を outputs/ に保存
        output_dir = settings.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        proposal_path = output_dir / f"strategy_proposal_{self.period.replace(' ', '_')}.md"
        proposal_path.write_text(result, encoding="utf-8")

        # ArcoCapitalレポートにも保存
        report_dir = settings.investment_division_dir / "レポート"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"optimizer_{self.period.replace(' ', '_')}.md"
        report_path.write_text(result, encoding="utf-8")

        print(f"\n✅ 改訂案を保存しました:")
        print(f"   → {proposal_path}")
        print(f"   → {report_path}")
        print(f"\n⚠️  デプロイ前にバックテスト検証と人間の承認が必要です")
        print(f"{'='*60}\n")

        return result
