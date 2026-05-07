"""
check_market_open.py — 米国市場が現在 OPEN か判定

IntradayScanCrew の起動前チェック。DST 切替で EDT/EST タスクが
両方発火する可能性に対し、片方だけを走らせるためのガード。

終了コード:
    0 — 市場は現在 OPEN（スキャン実行すべき）
    1 — 市場は CLOSED
    2 — エラー（Alpaca 接続失敗など）
"""

import os
import sys

# プロジェクトルートを sys.path に追加
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(_ROOT, ".env"), override=True)

try:
    from alpaca.trading.client import TradingClient
    from config.settings import settings
except Exception as exc:
    print(f"[ERROR] import failed: {exc}", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    try:
        client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=settings.is_paper_trading,
        )
        clock = client.get_clock()
    except Exception as exc:
        print(f"[ERROR] Alpaca clock fetch failed: {exc}", file=sys.stderr)
        return 2

    if clock.is_open:
        print(f"[OPEN] market is currently open (now={clock.timestamp})")
        return 0

    print(f"[CLOSED] market is closed — next_open={clock.next_open}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
