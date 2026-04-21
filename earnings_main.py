"""
earnings_main.py — XEarningsThreadCrew 実行用 CLI

使用例:
    # ドライラン（自動選定: 直近7日決算済みの大型株3社）
    python earnings_main.py

    # 本番投稿
    python earnings_main.py --publish

    # 期間と件数を指定
    python earnings_main.py --days 14 --count 5

    # 明示指定
    python earnings_main.py --tickers JPM,NFLX,JNJ --publish
"""

import argparse
import sys

from dotenv import load_dotenv
load_dotenv(override=True)

from crews.trading.x_earnings_crew import XEarningsThreadCrew


def main():
    parser = argparse.ArgumentParser(
        description="XEarningsThreadCrew — 米国決算ふりかえりスレッド生成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--tickers", default="",
                        help="明示指定銘柄カンマ区切り（例: JPM,NFLX,JNJ）。省略時は自動選定。")
    parser.add_argument("--days", type=int, default=7,
                        help="直近N日に決算発表があった銘柄を対象（既定: 7）")
    parser.add_argument("--count", type=int, default=3,
                        help="取り上げる銘柄数（既定: 3）")
    parser.add_argument("--publish", action="store_true",
                        help="X にスレッド投稿（既定はドライラン）")

    args = parser.parse_args()
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()] if args.tickers else None

    crew = XEarningsThreadCrew(
        tickers=tickers,
        days_back=args.days,
        count=args.count,
        dry_run=not args.publish,
    )
    crew.run()


if __name__ == "__main__":
    sys.exit(main())
