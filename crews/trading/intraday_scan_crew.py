"""
IntradayScanCrew — 日中追加スキャン（コスト最適化版）

フロー:
  1. S&P500 を軽量スクリーニング（Python only、LLMコスト $0）
  2. 朝の Top10 状態ファイルと比較
  3. 新規候補 or 大幅スコア上昇銘柄のみ抽出
  4. 候補があれば AnalystCrew で1銘柄ずつ深層分析
  5. BUYシグナル強ければ自動発注

コスト想定:
  - 新規候補ナシ: $0
  - 1銘柄分析: ~$0.3-0.5 (Sonnet 4.5)
  - 2銘柄分析: ~$0.6-1.0
  - max_new_analyses でキャップ

使用例:
    crew = IntradayScanCrew(live=True)
    result = crew.run()
"""

import asyncio
from datetime import date, datetime
from typing import Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from config.settings import settings
from crews.base_crew import BaseCrew
from crews.trading.analyst_crew import AnalystCrew
from crews.trading.auto_crew import load_morning_top10
from trading.tools.screener_tools import run_sp500_screening
from trading.tools.sp500_universe import get_sp500_tickers


# ── パラメータ ───────────────────────────────────────────────────────────────

# 朝のTop10になかった銘柄でスコアがこれ以上なら新候補として昇格
NEW_CANDIDATE_MIN_SCORE = 35.0

# 朝にTop10入りしてたがスコアが大幅に上昇した場合も再分析対象
SCORE_UPGRADE_THRESHOLD = 10.0  # 朝比+10点以上の上昇


def get_current_positions_tickers() -> set[str]:
    """Alpaca から現在保有中の銘柄リストを取得"""
    client = TradingClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        paper=settings.is_paper_trading,
    )
    try:
        positions = client.get_all_positions()
        return {p.symbol for p in positions}
    except Exception:
        return set()


def identify_new_candidates(
    current_results: list,
    morning_state: dict,
    held_tickers: set[str],
) -> list:
    """
    日中のスクリーニング結果から「新候補」を抽出する。

    新候補の定義:
      - 朝のTop10になかった、かつスコア >= NEW_CANDIDATE_MIN_SCORE
      - OR 朝にTop10入りしてたがスコアが SCORE_UPGRADE_THRESHOLD 以上上昇
      - 既に保有中の銘柄は除外
    """
    morning_tickers = {
        r["ticker"]: r["score"] for r in morning_state.get("top10", [])
    }

    new_candidates = []
    for r in current_results[:10]:  # 現在のTop10のみ検討
        # 既に保有中はスキップ
        if r.ticker in held_tickers:
            continue

        morning_score = morning_tickers.get(r.ticker)
        if morning_score is None:
            # 朝になかった新顔
            if r.score >= NEW_CANDIDATE_MIN_SCORE:
                new_candidates.append((r, f"朝のTop10外 → 現在スコア{r.score:.1f}"))
        else:
            # 朝からあったがスコア上昇
            delta = r.score - morning_score
            if delta >= SCORE_UPGRADE_THRESHOLD:
                new_candidates.append(
                    (r, f"スコア上昇 {morning_score:.1f} → {r.score:.1f} (+{delta:.1f})")
                )
    return new_candidates


class IntradayScanCrew(BaseCrew):
    """
    日中の軽量スキャン + 新候補のみ深層分析クルー。

    Args:
        live:                True で実発注、False でドライラン
        max_new_analyses:    1回の実行で深層分析する最大銘柄数（コスト上限）
    """

    def __init__(self, live: bool = False, max_new_analyses: int = 2):
        self.live = live
        self.max_new_analyses = max_new_analyses

    def run(self) -> str:
        now = datetime.now().strftime("%H:%M")
        mode = "⚠️ 実発注" if self.live else "ドライラン"

        print(f"\n{'='*65}")
        print(f"  IntradayScanCrew 起動 — {now} JST")
        print(f"  モード: {mode}")
        print(f"{'='*65}\n")

        # 1. 朝のTop10状態読み込み
        morning_state = load_morning_top10()
        if not morning_state:
            print("⚠️  朝の状態ファイルが見つかりません（朝のバッチが走っていない？）")
            print("   日中単独ではベース比較できないので、全てのTop10を新候補とみなします")

        # 2. 現在の保有銘柄取得
        held = get_current_positions_tickers()
        print(f"📦 現在保有銘柄: {len(held)}銘柄 ({', '.join(sorted(held)) if held else 'なし'})\n")

        # 3. S&P500軽量スクリーニング（Python only、無料）
        print("🔍 S&P500 軽量スクリーニング中（Python only、LLMコスト $0）...\n")
        tickers = get_sp500_tickers()
        screening_results = asyncio.run(
            run_sp500_screening(tickers, top_n=10)
        )
        if not screening_results:
            msg = "スクリーニング通過銘柄なし — 日中スキャン終了"
            print(msg)
            return msg

        print(f"   → {len(screening_results)}銘柄通過、現在のTop10:")
        for i, r in enumerate(screening_results[:10], 1):
            morning_score = next(
                (m["score"] for m in morning_state.get("top10", []) if m["ticker"] == r.ticker),
                None
            )
            tag = ""
            if morning_score is None:
                tag = "🆕 NEW"
            elif r.score - morning_score >= SCORE_UPGRADE_THRESHOLD:
                tag = f"📈 +{r.score - morning_score:.1f}"
            held_tag = "[保有中]" if r.ticker in held else ""
            print(f"   {i:2d}. {r.ticker:5s} スコア{r.score:.1f} RSI{r.rsi_value:.1f} {tag} {held_tag}")

        # 4. 新候補の抽出
        new_candidates = identify_new_candidates(
            screening_results, morning_state, held
        )

        if not new_candidates:
            msg = "\n✅ 新候補なし — 朝のTop10から状況に大きな変化なし。LLMコスト $0"
            print(msg)
            return msg

        # キャップ適用
        targets = new_candidates[: self.max_new_analyses]
        print(f"\n🎯 新候補 {len(new_candidates)}銘柄発見 → Top{len(targets)}を深層分析\n")

        # 5. AnalystCrewで各候補を分析
        analysis_results = []
        executed_tickers = []

        for rank, (candidate, reason) in enumerate(targets, 1):
            ticker = candidate.ticker
            print(f"\n--- {rank}/{len(targets)}: {ticker} 分析中 ({reason}) ---\n")

            try:
                context = (
                    f"{reason} | "
                    f"スクリーニングスコア: {candidate.score:.1f}/100 | "
                    f"RSI: {candidate.rsi_value:.1f} | "
                    f"条件: {', '.join(candidate.reasons)}"
                )
                analyst_crew = AnalystCrew(ticker=ticker, context=context)
                result = analyst_crew.run()
                analysis_results.append({
                    "ticker": ticker,
                    "score": candidate.score,
                    "reason": reason,
                    "result": result,
                })

                # BUYシグナル判定 → 自動発注
                if self.live and self._should_execute(result):
                    order_id = self._execute_buy(ticker, candidate)
                    if order_id:
                        executed_tickers.append(ticker)
                        print(f"   ✅ {ticker} 発注成功: ID={order_id}")
                else:
                    print(f"   💤 {ticker}: BUYシグナルに満たず or ドライラン")

            except Exception as e:
                print(f"   ⚠️ {ticker} 分析エラー: {e}")
                analysis_results.append({
                    "ticker": ticker,
                    "score": candidate.score,
                    "reason": reason,
                    "result": f"エラー: {e}",
                })

        # 6. レポート生成
        report = self._build_report(
            morning_state, screening_results, new_candidates, analysis_results, executed_tickers
        )
        print(f"\n{report}\n")
        return report

    def _should_execute(self, analyst_result: str) -> bool:
        """AnalystCrewの結果からBUY発注するか判断"""
        text = analyst_result.upper()
        # ざっくりルール: BUY シグナルが明示 AND BEARISH が含まれない
        has_buy = "BUY" in text or "BULLISH" in text
        has_block = "BEARISH" in text or "BEAR " in text or "EXTREME_GREED" in text
        return has_buy and not has_block

    def _execute_buy(self, ticker: str, candidate) -> Optional[str]:
        """簡易BUY発注（strategy.md 最大ポジション10%ルール遵守）"""
        client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=settings.is_paper_trading,
        )
        try:
            account = client.get_account()
            portfolio_value = float(account.portfolio_value)
            # ポジションサイズ = 総資産の5%（新規エントリーは控えめに）
            position_usd = portfolio_value * 0.05
            qty = int(position_usd / candidate.price)
            if qty < 1:
                print(f"   ⚠️  {ticker}: 1株分の資金不足でスキップ")
                return None

            req = MarketOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )
            order = client.submit_order(req)
            return str(order.id)
        except Exception as exc:
            print(f"   ❌ {ticker} 発注失敗: {exc}")
            return None

    def _build_report(
        self,
        morning_state: dict,
        current_results,
        new_candidates: list,
        analysis_results: list[dict],
        executed_tickers: list[str],
    ) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M JST")
        morning_date = morning_state.get("date", "なし")

        lines = [
            f"## 📊 日中スキャン結果 — {now}",
            f"",
            f"### サマリー",
            f"- 朝のTop10ベース日付: {morning_date}",
            f"- 現在のTop10: {len(current_results)}銘柄",
            f"- 新候補検出: {len(new_candidates)}銘柄",
            f"- 深層分析実施: {len(analysis_results)}銘柄",
            f"- 発注執行: {len(executed_tickers)}銘柄 ({', '.join(executed_tickers) if executed_tickers else 'なし'})",
            f"",
        ]

        if new_candidates:
            lines.append("### 新候補の詳細")
            for candidate, reason in new_candidates:
                tag = "🎯" if candidate.ticker in executed_tickers else "📋"
                lines.append(
                    f"- {tag} **{candidate.ticker}** スコア{candidate.score:.1f} "
                    f"RSI{candidate.rsi_value:.1f} — {reason}"
                )

        if analysis_results:
            lines.append("")
            lines.append("### 深層分析結果（抜粋）")
            for ar in analysis_results:
                lines.append(f"**{ar['ticker']}** (スコア{ar['score']:.1f})")
                snippet = ar["result"][:400].replace("\n", " ") + "..."
                lines.append(f"> {snippet}")

        return "\n".join(lines)
