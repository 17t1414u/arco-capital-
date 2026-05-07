"""
screener_tools.py — S&P500全銘柄バッチスクリーニング (v2.3: Triple Path A/B/C)

strategy.md v2.3 のスクリーニングルールに従い、500銘柄を高速フィルタリングして
取引候補Top10を選出する。

スクリーニング3フェーズ:
  Phase 1: 流動性フィルター（出来高・価格）
  Phase 2: 3経路トリプルパステクニカルスクリーニング
    Path A (逆張り買い):  RSI<50 + 価格>SMA50 + (MACD正 or 直近3日下落-3%以上)
    Path B (順張り買い):  RSI∈[50,75] + パーフェクトオーダー + 価格>SMA20 + 出来高1.2x
    Path C (過熱反転売り): RSI>75 + SMA20乖離+10% + MACD減速 + 出来高萎縮 → 意図的SHORT
  Phase 3: 経路別スコアランキング → Top10選出（LONG/SHORT 混合）
"""

import asyncio
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal, Optional

from trading.tools.market_data import fetch_bars
from trading.tools.indicators import rsi, sma, macd


# ── 戦略パラメータ (strategy.md v2.3 と同期) ──────────────────────────────────

# Path A (逆張り買い)
PATH_A_RSI_MAX = 50.0           # RSI < 50 で押し目候補（v2.2 45→50に拡大）
PATH_A_PULLBACK_DAYS = 3        # 直近3日下落
PATH_A_PULLBACK_PCT = -0.03     # -3% 以上の下落で押し目検知

# Path B (順張り買い)
PATH_B_RSI_MIN = 50.0
PATH_B_RSI_MAX = 75.0           # 上限 v2.2 70→75 に拡大（強気継続中も捕捉）
PATH_B_VOLUME_RATIO_MIN = 1.2   # 出来高条件 v2.2 1.3→1.2 に緩和

# Path C (過熱反転売り、意図的SHORT)
PATH_C_RSI_MIN = 75.0           # 極度の過熱
PATH_C_SMA20_DEVIATION_MIN = 0.10  # +10% 以上の SMA20 乖離
PATH_C_VOLUME_RATIO_MAX = 0.9   # 出来高 ≤ 20日平均 × 0.9（買い疲れ）

# 流動性フィルター
LIQUIDITY_MIN_AVG_VOLUME = 1_000_000
LIQUIDITY_MIN_PRICE = 10.0


@dataclass
class ScreenerResult:
    """スクリーニング結果の1銘柄分 (v2.3: LONG/SHORT 両対応)"""
    ticker: str
    price: float
    volume_avg: float          # 20日平均出来高
    volume_ratio: float        # 当日出来高/20日平均
    rsi_value: float
    sma20: float
    sma50: float
    macd_hist: float           # MACDヒストグラム値
    macd_hist_prev: float      # 前日のヒストグラム（増加判定用）
    macd_crossed: bool         # 直近5日でMACDが正転換したか
    pullback_3d_pct: float = 0.0  # 直近3日の価格変動率（押し目検知用）
    score: float = 0.0         # フェーズ3のスコア
    phase1_pass: bool = False
    path: Literal["A", "B", "C", "AB", "AC", "BC", "ABC", ""] = ""  # 通過経路
    side: Literal["LONG", "SHORT", ""] = ""  # 推奨エントリー方向
    reasons: list[str] = field(default_factory=list)


def _is_nan(x: float) -> bool:
    return x != x  # NaN は自分自身と等しくない


def _evaluate_path_a(
    rsi_val: float,
    latest_close: float,
    sma50_val: float,
    macd_hist: float,
    macd_crossed: bool,
    pullback_3d_pct: float,
) -> tuple[bool, list[str]]:
    """
    Path A: 逆張り買い（押し目買い）の評価 (v2.3 拡張)。
    A1 + A2 + (A3a or A3b) で通過。
    """
    reasons: list[str] = []

    # A1: RSI < 50 (v2.3 拡大)
    if _is_nan(rsi_val) or rsi_val >= PATH_A_RSI_MAX:
        return False, []
    reasons.append(f"A1:RSI={rsi_val:.1f}<{PATH_A_RSI_MAX:.0f}")

    # A2: 価格 > SMA(50)
    if _is_nan(sma50_val) or latest_close <= sma50_val:
        return False, []
    reasons.append(f"A2:P>{sma50_val:.1f}(SMA50)")

    # A3a: MACDヒスト > 0 or 直近5日で正転換
    a3a_ok = macd_hist > 0 or macd_crossed
    # A3b: 直近3日下落-3%以上 (v2.3 新規 押し目検知)
    a3b_ok = pullback_3d_pct <= PATH_A_PULLBACK_PCT
    if not (a3a_ok or a3b_ok):
        return False, []
    if a3a_ok:
        reasons.append(f"A3a:MACD={'転換' if macd_crossed else f'{macd_hist:.3f}'}")
    if a3b_ok:
        reasons.append(f"A3b:3日下落{pullback_3d_pct*100:+.1f}%")

    return True, reasons


def _evaluate_path_b(
    rsi_val: float,
    latest_close: float,
    sma20_val: float,
    sma50_val: float,
    volume_ratio: float,
) -> tuple[bool, list[str]]:
    """
    Path B: 順張り買い（モメンタム）の評価 (v2.3 RSI上限75、出来高1.2x)。
    """
    reasons: list[str] = []

    # B1: RSI ∈ [50, 75] (v2.3 上限拡大)
    if _is_nan(rsi_val) or not (PATH_B_RSI_MIN <= rsi_val <= PATH_B_RSI_MAX):
        return False, []
    reasons.append(f"B1:RSI={rsi_val:.1f}∈[{PATH_B_RSI_MIN:.0f}-{PATH_B_RSI_MAX:.0f}]")

    # B2: SMA(20) > SMA(50) 即ちパーフェクトオーダー
    if _is_nan(sma20_val) or _is_nan(sma50_val) or sma20_val <= sma50_val:
        return False, []
    reasons.append(f"B2:SMA20>{sma50_val:.1f}(SMA50)")

    # B3: 価格 > SMA(20)
    if latest_close <= sma20_val:
        return False, []
    reasons.append(f"B3:P>{sma20_val:.1f}(SMA20)")

    # B4: 出来高 ≥ 20日平均 × 1.2 (v2.3 緩和)
    if volume_ratio < PATH_B_VOLUME_RATIO_MIN:
        return False, []
    reasons.append(f"B4:Vol×{volume_ratio:.2f}≥{PATH_B_VOLUME_RATIO_MIN}")

    return True, reasons


def _evaluate_path_c(
    rsi_val: float,
    latest_close: float,
    sma20_val: float,
    macd_hist: float,
    macd_hist_prev: float,
    volume_ratio: float,
) -> tuple[bool, list[str]]:
    """
    Path C: 過熱反転売り（意図的SHORT）の4条件評価 (v2.3 新規)。
    全条件を満たせば SHORT エントリー候補とする。
    """
    reasons: list[str] = []

    # C1: RSI > 75 (極度の過熱)
    if _is_nan(rsi_val) or rsi_val <= PATH_C_RSI_MIN:
        return False, []
    reasons.append(f"C1:RSI={rsi_val:.1f}>{PATH_C_RSI_MIN:.0f}")

    # C2: 価格 vs SMA20 乖離 ≥ +10%
    if _is_nan(sma20_val) or sma20_val <= 0:
        return False, []
    deviation = (latest_close / sma20_val) - 1.0
    if deviation < PATH_C_SMA20_DEVIATION_MIN:
        return False, []
    reasons.append(f"C2:乖離{deviation*100:+.1f}%≥{PATH_C_SMA20_DEVIATION_MIN*100:.0f}%")

    # C3: MACDヒスト減速中 (前日比で減少)
    if not (macd_hist < macd_hist_prev):
        return False, []
    reasons.append(f"C3:MACD減速{macd_hist_prev:.3f}→{macd_hist:.3f}")

    # C4: 出来高 ≤ 20日平均 × 0.9 (買い疲れ)
    if volume_ratio > PATH_C_VOLUME_RATIO_MAX:
        return False, []
    reasons.append(f"C4:Vol×{volume_ratio:.2f}≤{PATH_C_VOLUME_RATIO_MAX}")

    return True, reasons


def _score_path_a(
    rsi_val: float,
    volume_ratio: float,
    macd_hist: float,
    macd_crossed: bool,
    pullback_3d_pct: float,
) -> float:
    """Path A スコア (最大100点) — v2.3"""
    # RSIスコア (最大35点)
    rsi_score = max(0, (PATH_A_RSI_MAX - rsi_val) / PATH_A_RSI_MAX * 35)
    # 出来高スコア (最大25点)
    volume_score = min(25, volume_ratio / 3.0 * 25) if volume_ratio > 0 else 0
    # モメンタム (最大20点)
    momentum_score = 20 if macd_crossed else (10 if macd_hist > 0 else 0)
    # 押し目強度 (最大20点): 直近3日下落幅
    pullback_score = min(20, max(0, abs(pullback_3d_pct) * 100 * 4))  # -5%で満点
    return rsi_score + volume_score + momentum_score + pullback_score


def _score_path_b(
    rsi_val: float,
    latest_close: float,
    sma50_val: float,
    volume_ratio: float,
    macd_hist: float,
    macd_hist_prev: float,
) -> float:
    """Path B スコア (最大100点) — v2.3"""
    # トレンドスコア (最大35点): 価格が SMA50 をどれだけ上回るか
    if not _is_nan(sma50_val) and sma50_val > 0:
        trend_pct = (latest_close - sma50_val) / sma50_val * 100
        trend_score = min(35, max(0, trend_pct * 3))  # +12%付近で満点
    else:
        trend_score = 0
    # 出来高スコア (最大25点)
    volume_score = min(25, volume_ratio / 3.0 * 25)
    # モメンタム (最大25点): MACDヒスト>0で20点、増加中なら+5
    momentum_score = 0
    if macd_hist > 0:
        momentum_score = 20
        if macd_hist > macd_hist_prev:
            momentum_score += 5
    # RSI健全度 (最大15点)
    rsi_health = max(0, 15 - abs(rsi_val - 60) * 1.5)
    return trend_score + volume_score + momentum_score + rsi_health


def _score_path_c(
    rsi_val: float,
    latest_close: float,
    sma20_val: float,
    volume_ratio: float,
    macd_hist: float,
    macd_hist_prev: float,
) -> float:
    """Path C スコア (最大100点) — v2.3 SHORT 期待値"""
    # 過熱度スコア (最大30点): RSI>75 の超過分
    overheat_score = min(30, max(0, (rsi_val - 75) / 25 * 30))
    # 乖離スコア (最大25点): SMA20から+10%超過分
    if not _is_nan(sma20_val) and sma20_val > 0:
        deviation_pct = (latest_close / sma20_val - 1.0) * 100
        deviation_excess = max(0, deviation_pct - 10)  # 10%超過分
        deviation_score = min(25, deviation_excess * 5)  # +5%超過で満点
    else:
        deviation_score = 0
    # 減速スコア (最大25点): MACDヒスト減速幅
    deceleration = max(0, macd_hist_prev - macd_hist)  # 減少した分
    deceleration_score = min(25, deceleration * 25)
    # 出来高萎縮スコア (最大20点): 出来高が0.9倍以下、減るほど高得点
    shrinkage = max(0, 1.0 - volume_ratio)  # 0=平均、+0.5=半減
    shrinkage_score = min(20, shrinkage * 50)  # 出来高半減で満点
    return overheat_score + deviation_score + deceleration_score + shrinkage_score


async def _screen_single_ticker(ticker: str) -> Optional[ScreenerResult]:
    """
    1銘柄をスクリーニングする非同期関数 (v2.3 Triple Path)。
    Path A / B (LONG) または Path C (SHORT) いずれかを満たせば候補入り。
    エラー時は None を返す（ログなしでスキップ）。
    """
    try:
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=80)

        df = await fetch_bars(ticker, start, end)
        if df.empty or len(df) < 30:
            return None

        # 基本指標計算
        latest_close = float(df["close"].iloc[-1])
        latest_volume = float(df["volume"].iloc[-1])
        avg_volume = float(df["volume"].tail(20).mean())

        # ── Phase 1: 流動性フィルター ──────────────────────────────────
        if avg_volume < LIQUIDITY_MIN_AVG_VOLUME or latest_close < LIQUIDITY_MIN_PRICE:
            return None

        # ── テクニカル指標計算 ────────────────────────────────────────
        rsi_val = float(rsi(df)) if len(df) >= 15 else float("nan")
        sma20_val = float(sma(df, 20)) if len(df) >= 20 else float("nan")
        sma50_val = float(sma(df, 50)) if len(df) >= 50 else float("nan")

        macd_data = macd(df) if len(df) >= 26 else {}
        macd_hist = float(macd_data.get("histogram", 0))

        # 前日のヒストグラム
        macd_hist_prev = 0.0
        macd_crossed = False
        if len(df) >= 31:
            df_prev = df.iloc[:-1]
            prev_macd = macd(df_prev)
            if prev_macd:
                macd_hist_prev = float(prev_macd.get("histogram", 0))
                macd_crossed = (macd_hist_prev < 0 and macd_hist > 0)

        volume_ratio = latest_volume / avg_volume if avg_volume > 0 else 0

        # 直近3日の価格変動率 (Path A の押し目検知用)
        pullback_3d_pct = 0.0
        if len(df) >= 4:
            price_3d_ago = float(df["close"].iloc[-4])
            if price_3d_ago > 0:
                pullback_3d_pct = (latest_close - price_3d_ago) / price_3d_ago

        # ── Phase 2: 3経路トリプルパス評価 ───────────────────────────
        a_pass, a_reasons = _evaluate_path_a(
            rsi_val, latest_close, sma50_val, macd_hist, macd_crossed, pullback_3d_pct
        )
        b_pass, b_reasons = _evaluate_path_b(
            rsi_val, latest_close, sma20_val, sma50_val, volume_ratio
        )
        c_pass, c_reasons = _evaluate_path_c(
            rsi_val, latest_close, sma20_val, macd_hist, macd_hist_prev, volume_ratio
        )

        if not (a_pass or b_pass or c_pass):
            return None

        # 通過経路の組み合わせ
        path_chars = []
        if a_pass: path_chars.append("A")
        if b_pass: path_chars.append("B")
        if c_pass: path_chars.append("C")
        path: str = "".join(path_chars)

        # エントリー方向: Path A/B は LONG, Path C は SHORT
        # 両通過時は LONG/SHORT 矛盾なので C を優先しない (LONG 勝ち)
        if a_pass or b_pass:
            side: Literal["LONG", "SHORT"] = "LONG"
        else:
            side = "SHORT"

        # ── Phase 3: 経路別スコア計算 ─────────────────────────────────
        score_a = _score_path_a(
            rsi_val, volume_ratio, macd_hist, macd_crossed, pullback_3d_pct
        ) if a_pass else 0
        score_b = _score_path_b(
            rsi_val, latest_close, sma50_val, volume_ratio, macd_hist, macd_hist_prev
        ) if b_pass else 0
        score_c = _score_path_c(
            rsi_val, latest_close, sma20_val, volume_ratio, macd_hist, macd_hist_prev
        ) if c_pass else 0

        # 採用スコア: 通過した経路の最高値 + 複数通過ボーナス
        passed_scores = [s for s, p in [(score_a, a_pass), (score_b, b_pass), (score_c, c_pass)] if p]
        if not passed_scores:
            return None
        total_score = max(passed_scores)
        if len(path_chars) >= 2:
            total_score += 5 * (len(path_chars) - 1)  # 複数通過 +5点ずつ

        reasons = a_reasons + b_reasons + c_reasons

        return ScreenerResult(
            ticker=ticker,
            price=latest_close,
            volume_avg=avg_volume,
            volume_ratio=volume_ratio,
            rsi_value=rsi_val,
            sma20=sma20_val,
            sma50=sma50_val,
            macd_hist=macd_hist,
            macd_hist_prev=macd_hist_prev,
            macd_crossed=macd_crossed,
            pullback_3d_pct=pullback_3d_pct,
            score=total_score,
            phase1_pass=True,
            path=path,
            side=side,
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
    print(f"{'順位':<4} {'銘柄':<8} {'方向':<6} {'経路':<5} {'価格':<10} {'RSI':<6} {'スコア':<8} {'理由'}")
    print("-" * 100)
    for rank, r in enumerate(top, 1):
        side_label = "📈LONG" if r.side == "LONG" else "📉SHORT"
        print(
            f"{rank:<4} {r.ticker:<8} {side_label:<6} {r.path:<5} ${r.price:<9.2f} "
            f"{r.rsi_value:<6.1f} {r.score:<8.1f} "
            f"{', '.join(r.reasons)}"
        )

    return top


def format_screening_results(results: list[ScreenerResult]) -> str:
    """
    スクリーニング結果をエージェントに渡すテキスト形式に変換する。
    """
    if not results:
        return "スクリーニング通過銘柄なし: 現在の市場環境ではエントリー候補がありません。"

    lines = [f"## S&P500スクリーニング結果 — Top{len(results)}銘柄 (v2.3 Triple Path)\n"]
    for rank, r in enumerate(results, 1):
        side_label = "LONG (買い建て)" if r.side == "LONG" else "SHORT (空売り建て)"
        lines.append(
            f"### {rank}位: {r.ticker} [{side_label}, Path {r.path}]\n"
            f"- 株価: ${r.price:.2f}\n"
            f"- RSI(14): {r.rsi_value:.1f}\n"
            f"- SMA(20): ${r.sma20:.2f} | SMA(50): ${r.sma50:.2f}\n"
            f"- 直近3日変動: {r.pullback_3d_pct*100:+.2f}%\n"
            f"- MACDヒスト: {r.macd_hist:.4f} (前日 {r.macd_hist_prev:.4f}) "
            f"{'(正転換✓)' if r.macd_crossed else ''}\n"
            f"- 出来高比: {r.volume_ratio:.2f}x（20日平均比）\n"
            f"- スコア: {r.score:.1f}/100\n"
            f"- 通過条件: {', '.join(r.reasons)}\n"
        )
    return "\n".join(lines)
