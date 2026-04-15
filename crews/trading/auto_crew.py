"""
AutoCrew — 全自動売買パイプライン

S&P500全銘柄のスクリーニングから分析・執行まで完全自動化。

フロー:
  1. S&P500 ~500銘柄を取得
  2. Phase1〜3スクリーニング → Top10候補を選出
  3. 各候補にFullTradingCrewを実行（分析→判断→承認→執行）
  4. 結果を構造化ログに記録
  5. SNS投稿テキストを生成

使用例:
    # ドライラン（注文なし・推奨）
    crew = AutoCrew()
    result = crew.run()

    # 実注文モード
    crew = AutoCrew(live=True)
    result = crew.run()
"""

import asyncio
from datetime import date

from trading.tools.sp500_universe import get_sp500_tickers
from trading.tools.screener_tools import run_sp500_screening, format_screening_results
from trading.harness.guardrails import load_current_strategy, run_pre_trade_checks
from trading.harness.trade_log import get_performance_summary
from crews.trading.full_trading_crew import FullTradingCrew
from crews.trading.sns_crew import SNSCrew
from config.settings import settings


class AutoCrew:
    """
    S&P500全自動スクリーニング → 分析 → 執行パイプライン。

    Args:
        top_n:         スクリーニングで選出する候補銘柄数（デフォルト: 10）
        analyze_top:   深層分析を行う銘柄数（デフォルト: 3）
        live:          True で実注文モード（デフォルト: False = ドライラン）
        generate_sns:  SNS投稿テキストを生成するか（デフォルト: True）
    """

    def __init__(
        self,
        top_n: int = 10,
        analyze_top: int = 3,
        live: bool = False,
        generate_sns: bool = True,
    ):
        self.top_n = top_n
        self.analyze_top = analyze_top
        self.live = live
        self.generate_sns = generate_sns

    def run(self) -> str:
        """全自動パイプラインを実行する"""

        today = date.today().strftime("%Y年%m月%d日")
        mode_str = "⚠️ 実注文モード" if self.live else "ドライラン（注文なし）"

        print(f"\n{'='*65}")
        print(f"  AutoCrew 起動 — {today}")
        print(f"  対象: S&P500全銘柄 | モード: {mode_str}")
        print(f"  環境: {'ペーパー' if settings.is_paper_trading else '⚠️ 本番'}")
        print(f"{'='*65}\n")

        # ── STEP 1: S&P500銘柄リスト取得 ─────────────────────────────
        print("📋 STEP 1/4: S&P500銘柄リストを取得中...\n")
        tickers = get_sp500_tickers()
        print(f"   → {len(tickers)}銘柄を取得\n")

        # ── STEP 2: バッチスクリーニング ──────────────────────────────
        print("🔍 STEP 2/4: バッチスクリーニング実行中...\n")
        screening_results = asyncio.run(
            run_sp500_screening(tickers, top_n=self.top_n)
        )

        if not screening_results:
            msg = (
                f"## AutoCrew 完了 — {today}\n\n"
                "### スクリーニング結果\n"
                "**エントリー候補なし**: 現在の市場環境では条件を満たす銘柄がありません。\n\n"
                "次回のスクリーニングをお待ちください。"
            )
            print(msg)
            return msg

        screening_text = format_screening_results(screening_results)

        # ── STEP 3: Top N銘柄の深層分析 ──────────────────────────────
        targets = screening_results[:self.analyze_top]
        print(f"\n🎯 STEP 3/4: Top{self.analyze_top}銘柄の深層分析開始...\n")
        print(f"   対象: {[r.ticker for r in targets]}\n")

        analysis_results = []
        executed_tickers = []

        for rank, candidate in enumerate(targets, 1):
            ticker = candidate.ticker
            print(f"\n--- {rank}/{self.analyze_top}: {ticker} 分析中 ---\n")

            try:
                crew = FullTradingCrew(
                    ticker=ticker,
                    context=(
                        f"スクリーニングスコア: {candidate.score:.1f}/100 | "
                        f"RSI: {candidate.rsi_value:.1f} | "
                        f"条件: {', '.join(candidate.reasons)}"
                    ),
                    dry_run=not self.live,
                )
                result = crew.run()
                analysis_results.append({
                    "ticker": ticker,
                    "score": candidate.score,
                    "result": result,
                })

                # BUYシグナルで承認済みなら記録
                if "APPROVED" in result and "BUY" in result:
                    executed_tickers.append(ticker)

            except Exception as e:
                print(f"   ⚠️ {ticker} 分析エラー: {e}")
                analysis_results.append({
                    "ticker": ticker,
                    "score": candidate.score,
                    "result": f"エラー: {e}",
                })

        # ── STEP 4: SNS投稿生成 ───────────────────────────────────────
        sns_post = ""
        if self.generate_sns:
            print(f"\n📱 STEP 4/4: SNS投稿テキスト生成中...\n")
            try:
                # 今日のスクリーニング結果をマーケット情報として投稿
                perf = get_performance_summary(50)
                market_context = (
                    f"【{today} 自動スクリーニング結果】\n"
                    f"S&P500 {len(tickers)}銘柄をスキャン → {len(screening_results)}銘柄が候補\n"
                    f"Top候補: {', '.join([r.ticker for r in screening_results[:5]])}\n"
                    f"注目銘柄の特徴:\n{screening_text[:500]}"
                )
                sns_crew = SNSCrew(post_type="market_news", context=market_context)
                sns_post = sns_crew.run()
            except Exception as e:
                sns_post = f"SNS投稿生成エラー: {e}"

        # ── 最終レポート生成 ──────────────────────────────────────────
        final_report = _build_final_report(
            today=today,
            total_scanned=len(tickers),
            screening_results=screening_results,
            analysis_results=analysis_results,
            executed_tickers=executed_tickers,
            sns_post=sns_post,
            mode=mode_str,
        )

        print(f"\n{'='*65}")
        print(f"  AutoCrew 完了")
        print(f"  スキャン: {len(tickers)}銘柄 → 候補: {len(screening_results)}銘柄")
        print(f"  分析: {len(analysis_results)}銘柄 → 執行: {len(executed_tickers)}銘柄")
        print(f"{'='*65}\n")

        # レポートをArcoCapital/資産運用事業部/実績/に保存
        _save_daily_report(final_report, today)

        return final_report


def _build_final_report(
    today: str,
    total_scanned: int,
    screening_results,
    analysis_results: list[dict],
    executed_tickers: list[str],
    sns_post: str,
    mode: str,
) -> str:
    """日次レポートを生成する"""
    lines = [
        f"# AutoCrew 日次レポート — {today}",
        f"**モード**: {mode}",
        f"",
        f"## サマリー",
        f"| 項目 | 件数 |",
        f"|------|------|",
        f"| スキャン銘柄数 | {total_scanned}銘柄 |",
        f"| スクリーニング通過 | {len(screening_results)}銘柄 |",
        f"| 深層分析実施 | {len(analysis_results)}銘柄 |",
        f"| 注文執行 | {len(executed_tickers)}銘柄 ({', '.join(executed_tickers) if executed_tickers else 'なし'}) |",
        f"",
        f"## スクリーニング結果 Top{min(5, len(screening_results))}",
    ]

    for rank, r in enumerate(screening_results[:5], 1):
        lines.append(f"{rank}. **{r.ticker}** — スコア{r.score:.1f} | RSI:{r.rsi_value:.1f} | ${r.price:.2f}")

    lines += [
        f"",
        f"## 深層分析結果",
    ]
    for ar in analysis_results:
        lines.append(f"### {ar['ticker']} (スコア: {ar['score']:.1f})")
        lines.append(ar["result"][:800] + "..." if len(ar["result"]) > 800 else ar["result"])
        lines.append("")

    if sns_post:
        lines += [f"## 生成されたSNS投稿", sns_post]

    return "\n".join(lines)


def _save_daily_report(report: str, today: str) -> None:
    """日次レポートをArcoCapital/資産運用事業部/実績/に保存する"""
    from pathlib import Path
    save_dir = settings.investment_division_dir / "実績" / today[:7]  # YYYY-MM
    save_dir.mkdir(parents=True, exist_ok=True)
    report_path = save_dir / f"daily_report_{today.replace('年', '-').replace('月', '-').replace('日', '')}.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"📄 日次レポート保存: {report_path}")
