"""
investment_main.py — 資産運用事業部 メインエントリーポイント

TradingAgentsフレームワーク（自己進化型マルチエージェント）対応版。

【モード一覧】

─── 全自動モード（推奨）────────────────────────────────────────
  # S&P500全銘柄スクリーニング → 分析 → 執行（ドライラン）
  python investment_main.py --mode auto

  # S&P500全銘柄スクリーニング → 分析 → 実注文
  python investment_main.py --mode auto --live

─── TradingAgentsフルパイプライン（銘柄指定）──────────────────
  # フル自動分析（注文なし・安全）
  python investment_main.py --mode full --ticker NVDA

  # フル自動売買（注文あり）
  python investment_main.py --mode full --ticker NVDA --live

─── 個別モード ──────────────────────────────────────────────────
  # アナリストチームのみ（4軸分析）
  python investment_main.py --mode analyse --ticker AAPL

  # 価格モニタリング
  python investment_main.py --mode monitor

─── 自己改善ループ ───────────────────────────────────────────────
  # 戦略オプティマイザー（strategy.md 改訂案生成）
  python investment_main.py --mode optimize --period "2026年4月"

─── SNS運用 ─────────────────────────────────────────────────────
  python investment_main.py --mode sns --type market_news
  python investment_main.py --mode sns --type trade_result --ticker AAPL
  python investment_main.py --mode sns --type monthly_summary

─── X投資スレッド（毎朝7:30 JST 自動投稿） ──────────────────────
  # ドライラン（投稿なし・内容確認）
  python investment_main.py --mode x-thread

  # 本番投稿
  python investment_main.py --mode x-thread --live

  # テーマを手動指定
  python investment_main.py --mode x-thread --topic "FRB利上げ停止観測"
"""

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# .env を最初にロード（settings.py より前に必須）
load_dotenv()

from config.settings import settings


# ── モード別実行関数 ───────────────────────────────────────────────────────────

def run_auto(live: bool = False) -> None:
    """S&P500全銘柄スクリーニング → 分析 → 執行の全自動パイプライン"""
    from crews.trading.auto_crew import AutoCrew

    print(f"\n🤖 全自動モード起動")
    print(f"   S&P500 ~500銘柄をスキャン → Top10をスクリーニング → Top3を深層分析")
    crew = AutoCrew(live=live)
    result = crew.run()
    print("\n📋 本日の運用レポート:")
    print(result[:3000] + "..." if len(result) > 3000 else result)


def run_full(ticker: str, live: bool = False) -> None:
    """TradingAgentsフルパイプライン（推奨）"""
    from crews.trading.full_trading_crew import FullTradingCrew

    dry_run = not live
    mode_str = "⚠️ 実注文モード" if live else "ドライラン（注文なし）"
    print(f"\n🚀 TradingAgentsフルパイプライン: {ticker}")
    print(f"   モード: {mode_str}")
    print(f"   ブローカー: {settings.broker.upper()}")
    print(f"   環境: {'ペーパー' if settings.is_paper_trading else '⚠️ 本番'}\n")

    crew = FullTradingCrew(ticker=ticker, dry_run=dry_run)
    result = crew.run()
    print("\n📋 最終結果:")
    print(result)


def run_trade(ticker: str) -> None:
    """後方互換: フルパイプラインのドライランを実行"""
    run_full(ticker=ticker, live=False)


def run_analyse(ticker: str) -> None:
    """アナリストチームのみ実行（4軸分析、注文なし）"""
    from crews.trading.analyst_crew import AnalystCrew

    print(f"\n🔍 アナリストチーム分析: {ticker}\n")
    crew = AnalystCrew(ticker=ticker)
    result = crew.run()
    print("\n📊 4軸分析結果:")
    print(result)


def run_monitor() -> None:
    """価格監視モード（既存の MonitorCrew を呼び出す）"""
    from trading.crews.monitor_crew import MonitorCrew

    print("\n📡 価格監視モード起動（Ctrl+C で停止）\n")
    crew = MonitorCrew()
    asyncio.run(crew.run())


def run_optimize(period: str) -> None:
    """自己改善ループ: OptimizerCrewで strategy.md 改訂案を生成"""
    from crews.trading.optimizer_crew import OptimizerCrew

    print(f"\n🔧 オプティマイザーループ: {period}\n")
    crew = OptimizerCrew(period=period)
    result = crew.run()
    print("\n📋 改訂案（要バックテスト検証 + 人間承認）:")
    print(result[:2000] + "..." if len(result) > 2000 else result)


def run_strategy_review(period: str) -> None:
    """後方互換: optimize モードを呼び出す"""
    run_optimize(period=period)


def run_x_thread(live: bool = False, topic: str = "") -> None:
    """X投資スレッドを生成・投稿する（5投稿リプライチェーン）"""
    from crews.trading.x_thread_crew import XInvestmentThreadCrew

    dry_run = not live
    mode_str = "⚠️ 本番投稿モード" if live else "ドライラン（投稿なし）"
    print(f"\n🐦 X投資スレッドクルー: {mode_str}")
    if topic:
        print(f"   テーマ: {topic}")

    crew = XInvestmentThreadCrew(dry_run=dry_run, topic=topic)
    result = crew.run()
    print("\n📋 実行結果:")
    print(result[:2000] + "..." if len(result) > 2000 else result)


def run_sns(post_type: str, ticker: str = "", month: str = "") -> None:
    """SNSコンテンツを生成する（SNSCrew）"""
    from crews.trading.sns_crew import SNSCrew

    print(f"\n📱 SNS投稿生成: {post_type}\n")

    if post_type == "market_news":
        # マーケット情報を自動収集（簡易版：Alpacaから主要指標を取得）
        market_context = _get_market_context()
        crew = SNSCrew(post_type="market_news", context=market_context)

    elif post_type == "trade_result":
        if not ticker:
            print("❌ --ticker オプションが必要です")
            sys.exit(1)
        trade_data = _get_latest_trade(ticker)
        crew = SNSCrew(post_type="trade_result", trade_data=trade_data)

    elif post_type == "monthly_summary":
        target_month = month or date.today().strftime("%Y年%m月")
        monthly_stats = _get_monthly_stats(target_month)
        crew = SNSCrew(post_type="monthly_summary", monthly_stats=monthly_stats)

    else:
        print(f"❌ 不明な投稿タイプ: {post_type}")
        print("   使用可能: market_news / trade_result / monthly_summary")
        sys.exit(1)

    result = crew.run()

    # SNS投稿テキストを queue に保存
    queue_dir = settings.investment_division_dir / "SNS投稿" / "queue"
    queue_dir.mkdir(parents=True, exist_ok=True)
    timestamp = date.today().isoformat()
    post_path = queue_dir / f"{timestamp}_{post_type}.md"
    post_path.write_text(result, encoding="utf-8")

    print(f"\n✅ SNS投稿テキストを保存しました: {post_path}")
    print("\n📝 生成された投稿テキスト:")
    print(result)


# ── ヘルパー関数 ──────────────────────────────────────────────────────────────

def _load_trade_history() -> str:
    """
    SQLiteデータベースまたはJSONファイルから取引履歴を読み込む。
    DBがない場合はプレースホルダーテキストを返す。
    """
    db_path = settings.trading_db_path
    if not db_path.exists():
        return (
            "【取引履歴なし】\n"
            "まだ取引データがありません。\n"
            "初期分析として、現行戦略パラメータのみを評価してください。\n"
            "- RSI BUY閾値: 35\n"
            "- RSI SELL閾値: 70\n"
            "- ストップロス: 5%\n"
            "- 利確目標: 10%\n"
        )

    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ticker, side, qty, price, status, created_at "
            "FROM orders ORDER BY created_at DESC LIMIT 50"
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return "取引履歴は空です。"

        lines = ["直近50件の取引履歴:\n"]
        for row in rows:
            ticker, side, qty, price, status, created_at = row
            lines.append(
                f"- {created_at} | {ticker} {side} {qty}株 @ ${price} [{status}]"
            )
        return "\n".join(lines)

    except Exception as e:
        return f"取引履歴の読み込みエラー: {e}"


def _get_market_context() -> str:
    """
    主要市場情報を収集してテキストで返す（簡易版）。
    将来的には外部APIからリアルタイムデータを取得する。
    """
    today = date.today().strftime("%Y年%m月%d日")
    return (
        f"【{today} マーケット情報】\n"
        "以下の情報をもとにSNS投稿を生成してください:\n"
        "- 現在の市場トレンドを分析し、投資家に役立つ情報を提供する\n"
        "- ウォッチリスト銘柄（AAPL, MSFT, NVDA, TSLA, AMZN）の動向\n"
        "- 主要テクニカル指標の解説（RSI・SMAの読み方など）\n"
        "- 投資初心者向けの学びになる情報\n"
        "実際の市場データがない場合は、一般的な投資知識ベースのコンテンツを作成してください。"
    )


def _get_latest_trade(ticker: str) -> dict:
    """直近の取引データを取得する（DBがない場合はサンプルデータ）"""
    db_path = settings.trading_db_path
    if not db_path.exists():
        return {
            "ticker": ticker,
            "action": "BUY（ペーパートレード）",
            "entry_price": "N/A",
            "exit_price": "N/A",
            "pnl_pct": "N/A",
            "pnl_usd": "N/A",
            "comment": "取引データがありません。実際のトレード後にご利用ください。",
        }

    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ticker, side, qty, price, status, created_at "
            "FROM orders WHERE ticker = ? ORDER BY created_at DESC LIMIT 2",
            (ticker.upper(),),
        )
        rows = cursor.fetchall()
        conn.close()

        if len(rows) >= 2:
            buy_row = next((r for r in rows if r[1].lower() == "buy"), rows[0])
            sell_row = next((r for r in rows if r[1].lower() == "sell"), rows[-1])
            entry = float(buy_row[3])
            exit_p = float(sell_row[3])
            pnl_pct = (exit_p - entry) / entry * 100
            pnl_usd = (exit_p - entry) * float(buy_row[2])
            return {
                "ticker": ticker.upper(),
                "action": "BUY → SELL",
                "entry_price": f"${entry:.2f}",
                "exit_price": f"${exit_p:.2f}",
                "pnl_pct": f"{pnl_pct:+.1f}%",
                "pnl_usd": f"${pnl_usd:+.0f}",
                "comment": f"{'ペーパートレード' if settings.is_paper_trading else '本番取引'}",
            }

        return {"ticker": ticker, "comment": "取引データが不足しています。"}

    except Exception as e:
        return {"ticker": ticker, "comment": f"データ取得エラー: {e}"}


def _get_monthly_stats(month: str) -> dict:
    """月次統計を取得する（DBがない場合はプレースホルダー）"""
    return {
        "month": month,
        "trade_count": "集計中",
        "win_rate": "集計中",
        "monthly_pnl_pct": "集計中",
        "best_trade": "集計中",
        "worst_trade": "集計中",
        "total_pnl_usd": "集計中",
        "note": "ペーパートレード",
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="investment_main",
        description="資産運用事業部 — 自動売買・戦略改善・SNS発信",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
モード別使用例:
  python investment_main.py --mode trade --ticker NVDA
  python investment_main.py --mode analyse --ticker AAPL
  python investment_main.py --mode monitor
  python investment_main.py --mode strategy-review --period "2026年4月"
  python investment_main.py --mode sns --type market_news
  python investment_main.py --mode sns --type trade_result --ticker AAPL
  python investment_main.py --mode sns --type monthly_summary --month "2026年4月"
        """,
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["auto", "full", "trade", "analyse", "monitor", "optimize", "strategy-review", "sns", "x-thread"],
        help="実行モード",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="実注文モード（デフォルト: ドライラン）",
    )
    parser.add_argument(
        "--ticker",
        default="",
        help="銘柄ティッカー（trade/analyse/sns trade_result モード用）",
    )
    parser.add_argument(
        "--type",
        dest="sns_type",
        default="market_news",
        choices=["market_news", "trade_result", "monthly_summary"],
        help="SNS投稿種別（sns モード用）",
    )
    parser.add_argument(
        "--period",
        default="",
        help="評価期間（strategy-review モード用）例: '2026年4月'",
    )
    parser.add_argument(
        "--month",
        default="",
        help="対象月（sns monthly_summary モード用）例: '2026年4月'",
    )
    parser.add_argument(
        "--topic",
        default="",
        help="投稿テーマを手動指定（x-thread モード用）例: 'FRB利上げ停止観測'",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    print("\n" + "="*60)
    print("  Arco Capital — 資産運用事業部")
    print(f"  モード: {args.mode}")
    print("="*60)

    if args.mode == "auto":
        run_auto(live=args.live)

    elif args.mode == "full":
        if not args.ticker:
            parser.error("--mode full には --ticker が必要です")
        run_full(ticker=args.ticker, live=args.live)

    elif args.mode == "trade":
        if not args.ticker:
            parser.error("--mode trade には --ticker が必要です")
        run_trade(args.ticker)

    elif args.mode == "analyse":
        if not args.ticker:
            parser.error("--mode analyse には --ticker が必要です")
        run_analyse(args.ticker)

    elif args.mode == "monitor":
        run_monitor()

    elif args.mode in ("optimize", "strategy-review"):
        period = args.period or date.today().strftime("%Y年%m月")
        run_optimize(period)

    elif args.mode == "sns":
        run_sns(
            post_type=args.sns_type,
            ticker=args.ticker,
            month=args.month,
        )

    elif args.mode == "x-thread":
        run_x_thread(live=args.live, topic=args.topic)


if __name__ == "__main__":
    main()
