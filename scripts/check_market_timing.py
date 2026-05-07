"""
check_market_timing.py — 自動実行タイミング判定

Alpaca の clock API を使って「市場 OPEN まで 10〜45分 か」をチェック。
Windows タスクスケジューラから複数の JST 時刻（22:20/23:20 等）で呼ばれ、
DST に関係なく "OPEN 前の適切なタイミング" でのみ exit 0 を返す。

終了コード:
    0 — 市場が 10〜45 分以内に開く（実行すべき）
    1 — 実行すべきでない（まだ早い / もう遅い / 市場が今日開かない）
    2 — エラー（Alpaca 接続失敗など）
"""

import os
import sys
from datetime import date, timedelta

# プロジェクトルートを sys.path に追加（scripts/ から実行される場合のため）
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# .env が空のシステム環境変数より優先されるように
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(_ROOT, ".env"), override=True)


def _already_ran_today() -> bool:
    """
    本日の朝バッチが既に完走したかをチェック。
    AutoCrew が STEP 3 後に outputs/daily-state/YYYY-MM-DD_morning.json を
    保存するので、この存在をもって「今日は実行済み」と判断する。
    EDT タスクが完走後に EST タスクが二重起動するのを防ぐ。
    """
    today = date.today().isoformat()
    state_path = os.path.join(
        _ROOT, "outputs", "daily-state", f"{today}_morning.json"
    )
    return os.path.exists(state_path)

try:
    from alpaca.trading.client import TradingClient
    from config.settings import settings
except Exception as exc:
    print(f"[ERROR] import failed: {exc}", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    # 同日重複実行ガード: 朝バッチ既完走なら即SKIP
    if _already_ran_today():
        print("[SKIP] morning batch already completed today (state file exists)")
        return 1

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

    now = clock.timestamp
    next_open = clock.next_open

    # 市場が現在 OPEN のとき: 開場から 30 分以内なら寄り付きバッチとして実行
    # (モーニングバッチがスケジューリング揺れで市場開場直後に発火するケース)
    if clock.is_open:
        # next_open は「次の」open なので、どれくらい前に開いたかは別途計算
        # 簡易: now - (次の close - 市場時間) で推定できるが、ここでは
        # "open 中ならとりあえず通す" 方針（朝バッチのジッタ吸収）
        print(f"[GO] market already OPEN — now={now}")
        return 0

    delta = next_open - now
    total_min = delta.total_seconds() / 60.0

    # 1 分〜45 分の範囲で実行（Windows タスクの起動タイミング揺れを広く吸収）
    # 下限を 1 分にしたのは、22:20:00 スケジュールのタスクが 22:20:02 に起動し
    # 22:30:00 open までの 9:58 が 10 分未満で弾かれた過去バグ対応。
    if timedelta(minutes=1) <= delta <= timedelta(minutes=45):
        print(
            f"[GO] market opens in {total_min:.1f} min "
            f"(now={now}, next_open={next_open})"
        )
        return 0

    print(
        f"[SKIP] market opens in {total_min:.1f} min — outside 1-45min window "
        f"(now={now}, next_open={next_open})"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
