"""
PositionReviewCrew — 既存ポジションのエグジット判断クルー

AutoCrew の STEP 0（スクリーニング前）で実行され、
保有銘柄を strategy.md のエグジット条件と照合して
HOLD / TRIM / SELL の決定と必要なら売却執行を行う。

2層構造:
  Layer A (Hard Rules):  -5% SL到達 / +10% TP到達 → 即決定
  Layer B (LLM Judge):   RSI/MACD/トレーリングストップ等のニュアンス判断

使用例:
    crew = PositionReviewCrew(live=False)  # ドライラン
    result = crew.run()
"""

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from crewai import Crew, Process, Task

from agents.trading.position_reviewer import PositionReviewerAgent
from config.settings import settings
from crews.base_crew import BaseCrew
from trading.harness.guardrails import load_current_strategy
from trading.harness.trade_log import log_trade_decision
from trading.tools.alpaca_tools import PHASE2_TOOLS
from trading.tools.market_data import fetch_bars
from trading.tools.indicators import rsi, macd


# ── データ構造 ───────────────────────────────────────────────────────────────

@dataclass
class PositionSnapshot:
    """
    1ポジションのスナップショット。

    qty の符号でロング/ショートを区別:
      - qty > 0: LONG (買い建て、クローズには SELL)
      - qty < 0: SHORT (売り建て、クローズには BUY)
    """
    ticker: str
    qty: float                  # 符号付き: LONG=正, SHORT=負
    entry_price: float
    current_price: float
    unrealized_pl: float
    unrealized_pl_pct: float    # SHORT は Alpaca API が符号反転済みで返す
    market_value: float

    @property
    def is_short(self) -> bool:
        """SHORT ポジション判定"""
        return self.qty < 0

    @property
    def abs_qty(self) -> float:
        """絶対値の数量（注文に使う）"""
        return abs(self.qty)


@dataclass
class ExitDecision:
    """1ポジションのエグジット判断結果"""
    ticker: str
    action: Literal["HOLD", "TRIM", "SELL"]
    reason: str
    layer: Literal["A_HARD", "B_LLM"]
    sell_qty: float = 0.0  # TRIM の場合は部分量、SELL の場合は全量
    executed: bool = False
    order_id: Optional[str] = None


# ── ハードルール（Layer A） — strategy.md v2.2 と同期 ──────────────────────

# strategy.md v2.2 より:
#   Layer A 即SELL条件:
#     [A-SL]  損切り: -7%（v2.1 -5% → v2.2 -7% に緩和、ノイズ吸収）
#     [A-TP+] 強制利確: +30%（v2.1 +20% → v2.2 +30% に緩和、ウィナーを伸ばす）
#   Layer B 判断範囲:
#     +12%（B-TP1）〜 +30%（A-TP+ 直前）でLLMが個別判断
HARD_STOP_LOSS_PCT = -0.07
HARD_TAKE_PROFIT_PCT = 0.30
LLM_TP_TARGET_PCT = 0.12   # この水準以上で Layer B が利確検討
LLM_TRIM_TARGET_PCT = 0.20  # +20%以上は TRIM(部分利確) のデフォルト候補


def evaluate_hard_rules(snap: PositionSnapshot) -> Optional[ExitDecision]:
    """
    Layer A: 決定論的なハードルール判定 (strategy.md v2.2)。
    SL/TP 到達時は LLM を介さず即決定する。

    Returns:
        ExitDecision: 該当する場合
        None: ハードルールに該当しない場合（Layer B へ送る）
    """
    pct = snap.unrealized_pl_pct

    side_label = "SHORT" if snap.is_short else "LONG"

    # [A-SL] 損切り: -7% 以下 → 即SELL（絶対遵守）
    # LONG/SHORT 共通: unrealized_pl_pct は Alpaca が常に「ポジション保有者から見た損益率」
    # で返すため、-7% は LONG なら株価下落、SHORT なら株価上昇を意味する
    if pct <= HARD_STOP_LOSS_PCT:
        return ExitDecision(
            ticker=snap.ticker,
            action="SELL",
            reason=(
                f"[HARD-SL/{side_label}] -7%損切りライン到達: P&L={pct*100:+.2f}% "
                f"(エントリー${snap.entry_price:.2f} → 現在${snap.current_price:.2f})"
            ),
            layer="A_HARD",
            sell_qty=snap.abs_qty,  # 注文用の絶対値
        )

    # [A-TP+] 強制利確: +30% 以上の含み益 → 即SELL（過剰利益確定）
    if pct >= HARD_TAKE_PROFIT_PCT:
        return ExitDecision(
            ticker=snap.ticker,
            action="SELL",
            reason=(
                f"[HARD-TP+/{side_label}] +30%超の含み益確定: P&L={pct*100:+.2f}% "
                f"(エントリー${snap.entry_price:.2f} → 現在${snap.current_price:.2f})"
            ),
            layer="A_HARD",
            sell_qty=snap.abs_qty,
        )

    return None  # Layer B へ


# ── ポジション取得 ───────────────────────────────────────────────────────────

def get_position_snapshots() -> list[PositionSnapshot]:
    """Alpaca から現在の全ポジションを取得し、スナップショット化する"""
    client = TradingClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        paper=settings.is_paper_trading,
    )
    positions = client.get_all_positions()

    return [
        PositionSnapshot(
            ticker=p.symbol,
            qty=float(p.qty),
            entry_price=float(p.avg_entry_price),
            current_price=float(p.current_price),
            unrealized_pl=float(p.unrealized_pl),
            unrealized_pl_pct=float(p.unrealized_plpc),
            market_value=float(p.market_value),
        )
        for p in positions
    ]


# ── ポジションクローズ執行 ───────────────────────────────────────────────────

def execute_sell(
    decision: ExitDecision,
    paper: bool = True,
    snapshot: Optional["PositionSnapshot"] = None,
) -> ExitDecision:
    """
    SELL/TRIM 判定の決定を Alpaca へ発注し、trade_log.jsonl に記録する。

    LONG/SHORT 両対応:
      - LONG をクローズ → OrderSide.SELL（持ち株を売却）
      - SHORT をクローズ → OrderSide.BUY（買い戻し）

    snapshot.is_short によって発注サイドを自動判定する。
    snapshot が None の場合は LONG とみなして SELL を発注（後方互換）。

    Args:
        decision: ExitDecision (SELL/TRIM/HOLD)
        paper: paper trading mode
        snapshot: 当該ポジションの PositionSnapshot（必須に近い）
    """
    if decision.action == "HOLD":
        return decision
    if decision.sell_qty <= 0:
        return decision

    client = TradingClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        paper=paper,
    )

    # SHORT ならクローズに BUY、LONG なら SELL
    is_short = snapshot is not None and snapshot.is_short
    close_side = OrderSide.BUY if is_short else OrderSide.SELL
    side_label = "SHORT→BUY" if is_short else "LONG→SELL"

    req = MarketOrderRequest(
        symbol=decision.ticker,
        qty=decision.sell_qty,
        side=close_side,
        time_in_force=TimeInForce.DAY,
    )
    try:
        order = client.submit_order(req)
        decision.executed = True
        decision.order_id = str(order.id)
        decision.reason += f" | クローズ方向={side_label}"
    except Exception as exc:
        decision.reason += f" | ⚠️ 発注失敗 ({side_label}): {exc}"

    # ── trade_log.jsonl への SELL/TRIM 決定ログ ─────────────────────────────
    # AGENTS.md RULE-10: ログなしでの取引は禁止
    try:
        signals = {
            "layer": decision.layer,
            "sell_qty": decision.sell_qty,
            "executed": decision.executed,
            "order_id": decision.order_id,
        }
        if snapshot is not None:
            signals.update({
                "entry_price": snapshot.entry_price,
                "current_price": snapshot.current_price,
                "unrealized_pl_pct": snapshot.unrealized_pl_pct,
                "unrealized_pl_usd": snapshot.unrealized_pl,
                "qty_held": snapshot.qty,
            })

        log_trade_decision(
            ticker=decision.ticker,
            action=decision.action,  # "SELL" / "TRIM"
            entry_price=snapshot.entry_price if snapshot else None,
            position_size_pct=0.0,  # exit decision なのでポジションサイズは関係なし
            signals=signals,
            bull_thesis="(N/A — exit decision)",
            bear_thesis=decision.reason,  # exit 理由を bear thesis 欄に
            risk_approved=True,  # Layer A はハードルール、Layer B は LLM 承認済
            fund_manager_reasoning=decision.reason,
            strategy_version="v1.0",
            session_id=decision.order_id or f"exit-{decision.ticker}",
        )
    except Exception as exc:
        # ログ失敗は注文の成否に影響させない
        print(f"  ⚠️ trade_log 記録失敗 ({decision.ticker}): {exc}")

    return decision


# ── クルー本体 ───────────────────────────────────────────────────────────────

class PositionReviewCrew(BaseCrew):
    """
    既存保有ポジションを評価し、HOLD/TRIM/SELL を判断する。

    Args:
        live: True で実発注、False でドライラン（判断のみ）
    """

    def __init__(self, live: bool = False):
        self.live = live

    def build_llm_task(
        self,
        snapshots: list[PositionSnapshot],
        strategy_md: str,
    ) -> tuple[Crew, list[PositionSnapshot]]:
        """
        Layer B 用のLLM評価タスクを構築する。
        ハードルール非該当のポジションのみが対象。
        """
        # ハードルールに該当しなかったポジションだけリスト化
        # LONG/SHORT を明示してエージェントが誤判断しないようにする
        ticker_lines = []
        for s in snapshots:
            side = "SHORT" if s.is_short else "LONG"
            ticker_lines.append(
                f"  - {s.ticker} [{side}]: {s.qty}株 @ ${s.entry_price:.2f} → "
                f"現在${s.current_price:.2f} (P&L {s.unrealized_pl_pct*100:+.2f}%, "
                f"含み損益${s.unrealized_pl:+.2f})"
            )
        positions_text = "\n".join(ticker_lines)

        agent = PositionReviewerAgent.build()
        agent.tools = PHASE2_TOOLS

        task_description = f"""
以下の既存ポジションを strategy.md v2.2 のエグジット条件と照合し、
各銘柄について HOLD / TRIM / SELL の判断を下してください。

【現在のポジション】
{positions_text}

【strategy.md（抜粋）】
{strategy_md[:3000]}

【v2.2 Layer B 判断ルール】
※ Layer A (-7% SL / +30% TP+) はガードレールで処理済み。
   このタスクでは Layer B のみを判断します。

各銘柄について以下を順に評価:

  1. get_indicators ツールで最新 RSI(14) / MACD / SMA を取得
  2. get_bars ツールで30日OHLCVを取得し直近高値を確認

  3. 売却ルール（優先順位順）:
     [B-OVERHEAT] 過熱SELL — 全条件満たす場合のみ SELL
       - RSI(14) > 78（v2.1の72から厳格化）
       - MACDデッドクロス（直近5日以内）
       - 出来高が20日平均を下回る（息切れ確認）
       → 3条件揃って初めて SELL

     [B-TRAIL] トレーリングSELL —
       - 直近30日高値から -10% 以上下落かつ
       - 反転シグナル（RSI低下＋MACD弱体化）が明確
       → SELL

     [B-TRIM] 部分利確 —
       - +20% 以上の含み益かつ過熱気味（RSI>70）
       → TRIM（保有数量の50%売却）

     [B-TP1] 利確検討 —
       - +12% 以上の含み益かつトレンド鈍化シグナル
         （MACDヒスト減少、出来高減少）
       → SELL or TRIM をLLMが選択

  4. 上記いずれにも該当しない → HOLD

【重要な原則】
- 「単発のRSI上昇」だけでは売らない（v2.1の悪癖を解消）
- 「上昇トレンド継続中の含み益」は粘る（ウィナーを伸ばす）
- 含み損は -7% まで耐える（Layer A が処理）

【SHORT ポジション (qty<0) の判定】
- LONG と同じく unrealized_pl_pct で判定する（Alpaca が符号反転済みで返す）
- ただしテクニカルの解釈は逆になることに注意:
   * SHORT で含み益 = 株価下落中（カバー検討は RSI<25 過売り反転シグナル）
   * SHORT で含み損 = 株価上昇中（-7%超は Layer A で機械的にクローズ済み）
- 出力フォーマットの「売却数量」はクローズ数量（絶対値）として記載すること

【出力フォーマット】（必ずこの形式で銘柄ごとに出力）
銘柄名: {{TICKER}}
判定: HOLD / TRIM / SELL
売却数量: {{数値}}株 (HOLD なら 0、TRIM なら保有量×0.5)
理由: {{適用ルール(B-XXX)＋RSI/MACD/出来高の数値根拠＋含み益水準への言及}}
---
"""

        task = Task(
            description=task_description,
            agent=agent,
            expected_output="各銘柄について HOLD/TRIM/SELL の判定と売却数量、根拠",
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )
        return crew, snapshots

    def run(self) -> str:
        """
        全ポジション評価のメインループ。

        Returns:
            str: 評価結果のレポート文字列
        """
        print(f"\n{'='*65}")
        print(f"  PositionReviewCrew 起動")
        print(f"  モード: {'⚠️ 実発注' if self.live else 'ドライラン（判断のみ）'}")
        print(f"{'='*65}\n")

        # 1. ポジション取得
        snapshots = get_position_snapshots()
        if not snapshots:
            msg = "📦 既存ポジションなし — レビュー対象なし"
            print(msg)
            return msg

        print(f"📦 評価対象: {len(snapshots)}ポジション\n")
        for s in snapshots:
            print(
                f"  - {s.ticker}: {s.qty}株 @ ${s.entry_price:.2f} → "
                f"${s.current_price:.2f} (P&L {s.unrealized_pl_pct*100:+.2f}%)"
            )

        # 2. Layer A: ハードルール判定
        decisions: list[ExitDecision] = []
        layer_b_targets: list[PositionSnapshot] = []

        print(f"\n🔒 Layer A: ハードルール判定中...")
        for snap in snapshots:
            hard_decision = evaluate_hard_rules(snap)
            if hard_decision:
                print(f"  ✓ {snap.ticker}: {hard_decision.action} ({hard_decision.reason})")
                decisions.append(hard_decision)
            else:
                layer_b_targets.append(snap)

        # 3. Layer B: LLM判定
        if layer_b_targets:
            print(f"\n🤖 Layer B: LLM 詳細判定中... ({len(layer_b_targets)}銘柄)")
            strategy_md = load_current_strategy()
            crew, _ = self.build_llm_task(layer_b_targets, strategy_md)
            llm_result = crew.kickoff()
            llm_text = llm_result.raw if hasattr(llm_result, "raw") else str(llm_result)

            # LLMの出力をパース
            llm_decisions = _parse_llm_decisions(llm_text, layer_b_targets)
            decisions.extend(llm_decisions)
        else:
            print(f"\n🤖 Layer B: 評価対象なし（全銘柄が Layer A で確定）")

        # 4. 売却執行（live モードのみ）+ trade_log.jsonl 記録
        snapshot_by_ticker = {s.ticker: s for s in snapshots}
        if self.live:
            print(f"\n💰 売却執行中（LIVEモード）...")
            for d in decisions:
                if d.action in ("SELL", "TRIM"):
                    d = execute_sell(
                        d,
                        paper=settings.is_paper_trading,
                        snapshot=snapshot_by_ticker.get(d.ticker),
                    )
                    status = "✅ 発注成功" if d.executed else "❌ 発注失敗"
                    print(f"  {d.ticker} {d.action} {d.sell_qty}株: {status}")
        else:
            print(f"\n💤 ドライラン: 売却は執行しません（trade_log にも記録しない）")

        # 5. レポート生成
        report = _build_review_report(snapshots, decisions, self.live)
        print(f"\n{report}\n")
        return report


# ── LLM出力パーサー ──────────────────────────────────────────────────────────

def _parse_llm_decisions(
    llm_text: str,
    targets: list[PositionSnapshot],
) -> list[ExitDecision]:
    """
    LLMの出力テキストから各銘柄の判定をパースする。
    フォールバック: パース失敗時は HOLD として扱う。
    """
    decisions: list[ExitDecision] = []
    target_map = {s.ticker: s for s in targets}

    for snap in targets:
        # 銘柄名で該当ブロックを探す
        ticker = snap.ticker
        action: Literal["HOLD", "TRIM", "SELL"] = "HOLD"
        sell_qty = 0.0
        reason = "LLMからの明示的判断なし → HOLD"

        # シンプルなパターンマッチ
        upper = llm_text.upper()
        if f"銘柄名: {ticker}" in llm_text or f"銘柄: {ticker}" in llm_text or f"{ticker}:" in llm_text:
            # 該当銘柄のセクションを抽出
            idx = llm_text.find(ticker)
            section = llm_text[idx:idx + 1000]

            if "判定: SELL" in section or "判定:SELL" in section:
                action = "SELL"
                sell_qty = snap.abs_qty  # SHORT/LONG 両対応で絶対値
                reason = _extract_reason(section)
            elif "判定: TRIM" in section or "判定:TRIM" in section:
                action = "TRIM"
                sell_qty = round(snap.abs_qty * 0.5, 0) or 1.0  # 半分（最低1株）
                reason = _extract_reason(section)
            else:
                action = "HOLD"
                reason = _extract_reason(section)

        decisions.append(
            ExitDecision(
                ticker=ticker,
                action=action,
                reason=reason,
                layer="B_LLM",
                sell_qty=sell_qty,
            )
        )
    return decisions


def _extract_reason(section: str) -> str:
    """セクションから「理由:」以降を抽出する"""
    if "理由:" in section:
        idx = section.find("理由:") + 3
        end = section.find("---", idx)
        if end == -1:
            end = idx + 500
        return section[idx:end].strip()
    return section[:300].strip()


# ── レポート生成 ─────────────────────────────────────────────────────────────

def _build_review_report(
    snapshots: list[PositionSnapshot],
    decisions: list[ExitDecision],
    live: bool,
) -> str:
    """評価結果をMarkdownレポート化"""
    mode = "LIVE実発注" if live else "ドライラン"
    sells = [d for d in decisions if d.action == "SELL"]
    trims = [d for d in decisions if d.action == "TRIM"]
    holds = [d for d in decisions if d.action == "HOLD"]

    lines = [
        f"## 📦 ポジションレビュー結果（モード: {mode}）",
        f"",
        f"### サマリー",
        f"| 判定 | 件数 |",
        f"|------|------|",
        f"| SELL | {len(sells)}銘柄 |",
        f"| TRIM | {len(trims)}銘柄 |",
        f"| HOLD | {len(holds)}銘柄 |",
        f"",
        f"### 判定詳細",
    ]
    for d in decisions:
        emoji = {"SELL": "🔴", "TRIM": "🟡", "HOLD": "🟢"}.get(d.action, "⚪")
        snap = next((s for s in snapshots if s.ticker == d.ticker), None)
        pl_str = f" P&L {snap.unrealized_pl_pct*100:+.2f}%" if snap else ""
        lines.append(
            f"- {emoji} **{d.ticker}** [{d.layer}] {d.action} "
            f"({d.sell_qty:.0f}株){pl_str}"
        )
        lines.append(f"  - {d.reason}")
        if live and d.executed:
            lines.append(f"  - ✅ 発注ID: {d.order_id}")
    return "\n".join(lines)
