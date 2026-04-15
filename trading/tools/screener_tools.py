"""
screener_tools.py — S&P500全銘柄バッチスクリーニング

strategy.md のスクリーニングルールに従い、500銘柄を高速フィルタリングして
取引候補Top10を選出する。

スクリーニング3フェーズ:
  Phase 1: 流動性フィルター（出来高・価格）
  Phase 2: テクニカルスクリーニング（RSI/SMA/MACD）
  Phase 3: スコアランキング → Top10選出
"""

import asyncio
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from trading.tools.market_data import fetch_bars
from trading.tools.indicators import rsi, sma, macd


@dataclass
class ScreenerResult:
    """スクリーニング結果の1銘柄分"""
    ticker: str
    price: float
    volume_avg: float          # 20日平均出来高
    volume_ratio: float        # 当日出来高/20日平均
    rsi_value: float
    sma20: float
    sma50: float
    macd_hist: float           # MACDヒストグラム値
    macd_crossed: bool         # 直近5日でMACDが正転換したか
    score: float = 0.0         # フェーズ3のスコア
    phase1_pass: bool = False
    phase2_score: int = 0      # フェーズ2の条件を満たした数（0〜3）
    reasons: list[str] = field(default_factory=list)


async def _screen_single_ticker(ticker: str) -> Optional[ScreenerResult]:
    """
    1銘柄をスクリーニングする非同期関数。
    エラー時は None を返す（ログなしでスキップ）。
    """
    try:
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=80)  # MACD(26)計算に十分な日数

        df = await fetch_bars(ticker, start, end)
        if df.empty or len(df) < 30:
            return None

        # 基本指標計算
        latest_close = float(df["close"].iloc[-1])
        latest_volume = float(df["volume"].iloc[-1])
        avg_volume = float(df["volume"].tail(20).mean())

        # ── Phase 1: 流動性フィルター ──────────────────────────────────
        if avg_volume < 1_000_000 or latest_close < 10.0:
            return None

        # ── テクニカル指標計算 ────────────────────────────────────────
        rsi_val = float(rsi(df)) if len(df) >= 15 else float("nan")
        sma20_val = float(sma(df, 20)) if len(df) >= 20 else float("nan")
        sma50_val = float(sma(df, 50)) if len(df) >= 50 else float("nan")

        macd_data = macd(df) if len(df) >= 26 else {}
        macd_hist = float(macd_data.get("histogram", 0))

        # MACDが直近5日で正転換したか確認
        macd_crossed = False
        if len(df) >= 31:
            df_prev = df.iloc[:-1]
            prev_macd = macd(df_prev)
            if prev_macd:
                prev_hist = float(prev_macd.get("histogram", 0))
                macd_crossed = (prev_hist < 0 and macd_hist > 0)

        volume_ratio = latest_volume / avg_volume if avg_volume > 0 else 0

        # ── Phase 2: テクニカルスクリーニング ────────────────────────
        phase2_score = 0
        reasons = []

        # 条件A: RSI < 38
        if not (rsi_val != rsi_val) and rsi_val < 38:  # NaN チェック
            phase2_score += 1
            reasons.append(f"RSI={rsi_val:.1f}<38")

        # 条件B: 価格 > SMA(50)
        if not (sma50_val != sma50_val) and latest_close > sma50_val:
            phase2_score += 1
            reasons.append(f"P>{sma50_val:.1f}(SMA50)")

        # 条件C: MACDヒストグラムが正 または 正転換
        if macd_hist > 0 or macd_crossed:
            phase2_score += 1
            reasons.append(f"MACD={'転換' if macd_crossed else f'{macd_hist:.4f}'}")

        if phase2_score < 2:
            return None  # 2条件未満はスキップ

        # ── Phase 3: スコア計算 ──────────────────────────────────────
        # RSIスコア（最大40点）: RSIが低いほど高スコア
        rsi_score = max(0, (38 - rsi_val) / 38 * 40) if rsi_val < 38 else 0

        # ボリュームスコア（最大30点）
        volume_score = min(30, volume_ratio * 15)

        # モメンタムスコア（最大30点）
        momentum_score = 20 if macd_crossed else (10 if macd_hist > 0 else 0)

        total_score = rsi_score + volume_score + momentum_score

        return ScreenerResult(
            ticker=ticker,
            price=latest_close,
            volume_avg=avg_volume,
            volume_ratio=volume_ratio,
            rsi_value=rsi_val,
            sma20=sma20_val,
            sma50=sma50_val,
            macd_hist=macd_hist,
            macd_crossed=macd_crossed,
            score=total_score,
            phase1_pass=True,
            phase2_score=phase2_score,
            reasons=reasons,
        )

    except Exception:
        return None


async def run_sp500_screening(
    tickers: list[str],
    top_n: int = 10,
    batch_size: int = 20,
) -> list[ScreenerResult]:
    """
    S&P500全銘柄をバッチスクリーニングしてTop N銘柄を返す。

    Args:
        tickers:    スクリーニング対象のティッカーリスト
        top_n:      返す候補銘柄数（デフォルト: 10）
        batch_size: 1バッチあたりの並列処理数（APIレート制限対策）

    Returns:
        list[ScreenerResult]: スコア順Top N銘柄
    """
    results = []
    total = len(tickers)

    print(f"📡 S&P500スクリーニング開始: {total}銘柄")
    print(f"   バッチサイズ: {batch_size} | Top: {top_n}銘柄を選出\n")

    for i in range(0, total, batch_size):
        batch = tickers[i:i + batch_size]
        batch_results = await asyncio.gather(
            *[_screen_single_ticker(t) for t in batch],
            return_exceptions=False,
        )
        passed = [r for r in batch_results if r is not None]
        results.extend(passed)

        progress = min(i + batch_size, total)
        print(f"   進捗: {progress}/{total} | 通過: {len(results)}銘柄", end="\r")

    print(f"\n\n✅ スクリーニング完了: {total}銘柄 → {len(results)}銘柄通過")

    # スコア順にソートしてTop N を返す
    results.sort(key=lambda r: r.score, reverse=True)
    top = results[:top_n]

    print(f"\n🏆 候補銘柄 Top {top_n}:")
    print(f"{'順位':<4} {'銘柄':<8} {'価格':<10} {'RSI':<8} {'スコア':<8} {'理由'}")
    print("-" * 70)
    for rank, r in enumerate(top, 1):
        print(
            f"{rank:<4} {r.ticker:<8} ${r.price:<9.2f} "
            f"{r.rsi_value:<8.1f} {r.score:<8.1f} "
            f"{', '.join(r.reasons)}"
        )

    return top


def format_screening_results(results: list[ScreenerResult]) -> str:
    """
    スクリーニング結果をエージェントに渡すテキスト形式に変換する。
    """
    if not results:
        return "スクリーニング通過銘柄なし: 現在の市場環境ではエントリー候補がありません。"

    lines = [f"## S&P500スクリーニング結果 — Top{len(results)}銘柄\n"]
    for rank, r in enumerate(results, 1):
        lines.append(
            f"### {rank}位: {r.ticker}\n"
            f"- 株価: ${r.price:.2f}\n"
            f"- RSI(14): {r.rsi_value:.1f}\n"
            f"- SMA(20): ${r.sma20:.2f} | SMA(50): ${r.sma50:.2f}\n"
            f"- MACDヒスト: {r.macd_hist:.4f} {'(正転換✓)' if r.macd_crossed else ''}\n"
            f"- 出来高比: {r.volume_ratio:.1f}x（20日平均比）\n"
            f"- スコア: {r.score:.1f}/100\n"
            f"- 通過条件: {', '.join(r.reasons)}\n"
        )
    return "\n".join(lines)
