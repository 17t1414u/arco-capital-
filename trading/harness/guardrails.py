"""
guardrails.py — 決定論的ガードレール（ハーネス制御層）

AGENTS.md の安全制約を実行時に強制する。
エージェントの確率的な判断ミスを決定論的ルールで防ぐ。

制御パターン:
  - Capability-limiting: 危険操作の物理的排除
  - Approval Gate: 執行前の必須検証
  - Circuit Breaker: 連続エラー検知と強制停止
  - Structural Tests: ポジション・ドローダウン違反検知
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config.settings import settings


# ── 検証結果 ──────────────────────────────────────────────────────────────────

@dataclass
class GuardResult:
    approved: bool
    reason: str
    adjusted_size_pct: Optional[float] = None  # サイズ縮小提案がある場合


# ── ポジションサイズ検証 ───────────────────────────────────────────────────────

def validate_position_size(
    requested_pct: float,
    current_positions: dict[str, float],  # {ticker: size_pct}
    ticker: str,
) -> GuardResult:
    """
    AGENTS.md RULE-03: 1銘柄10%制限 + 同時保有5銘柄制限を検証する。

    Args:
        requested_pct:    要求されたポジションサイズ（例: 0.08 = 8%）
        current_positions: 現在の保有ポジション辞書
        ticker:           対象銘柄

    Returns:
        GuardResult: 承認/否認 + 理由
    """
    max_pos = settings.max_position_pct  # デフォルト 0.10

    # 1銘柄制限チェック
    if requested_pct > max_pos:
        return GuardResult(
            approved=False,
            reason=f"ポジションサイズ超過: {requested_pct*100:.1f}% > 上限{max_pos*100:.0f}%",
            adjusted_size_pct=max_pos,
        )

    # 最大銘柄数チェック（同一銘柄の追加は許可）
    active_tickers = [t for t, s in current_positions.items() if s > 0 and t != ticker]
    if len(active_tickers) >= 5:
        return GuardResult(
            approved=False,
            reason=f"最大保有銘柄数超過: {len(active_tickers)+1}銘柄 > 上限5銘柄",
        )

    return GuardResult(approved=True, reason="ポジションサイズ検証OK")


def validate_stop_loss(stop_loss_price: Optional[float], entry_price: float) -> GuardResult:
    """
    ストップロスが設定されているかつ合理的範囲内か検証する。
    """
    if stop_loss_price is None:
        return GuardResult(
            approved=False,
            reason="ストップロス未設定: すべての注文にストップロスが必須",
        )

    loss_pct = (entry_price - stop_loss_price) / entry_price
    max_stop = settings.stop_loss_pct * 2  # 設定値の2倍を上限（デフォルト: 10%）

    if loss_pct > max_stop:
        return GuardResult(
            approved=False,
            reason=f"ストップロスが広すぎます: -{loss_pct*100:.1f}% > 上限-{max_stop*100:.0f}%",
        )

    return GuardResult(approved=True, reason="ストップロス検証OK")


# ── ドローダウン監視 ──────────────────────────────────────────────────────────

def check_portfolio_drawdown(
    current_value: float,
    peak_value: float,
) -> GuardResult:
    """
    ポートフォリオの最大ドローダウン制限（-10%）を監視する。
    """
    if peak_value <= 0:
        return GuardResult(approved=True, reason="ピーク値が未設定")

    drawdown = (current_value - peak_value) / peak_value

    if drawdown <= -0.10:  # -10% 以下
        return GuardResult(
            approved=False,
            reason=f"最大ドローダウン到達: {drawdown*100:.1f}% ≤ -10% | 全ポジションを検討してください",
        )

    if drawdown <= -0.07:  # -7% で警告
        return GuardResult(
            approved=True,
            reason=f"⚠️ ドローダウン警告: {drawdown*100:.1f}% | 新規エントリーは慎重に",
        )

    return GuardResult(approved=True, reason=f"ドローダウン正常: {drawdown*100:.1f}%")


# ── サーキットブレーカー ───────────────────────────────────────────────────────

_consecutive_errors: dict[str, int] = {}  # {context_key: count}
CIRCUIT_BREAKER_THRESHOLD = 3


def check_circuit_breaker(context_key: str, reset: bool = False) -> GuardResult:
    """
    同一コンテキストで連続エラーが3回以上発生した場合にシステムを停止する。
    AGENTS.md の「Doom-loop」防止機能。

    Args:
        context_key: エラーカウントのキー（例: "alpaca_api", "analyst_crew"）
        reset:       エラーカウントをリセットする場合は True
    """
    if reset:
        _consecutive_errors[context_key] = 0
        return GuardResult(approved=True, reason="サーキットブレーカーをリセット")

    count = _consecutive_errors.get(context_key, 0)

    if count >= CIRCUIT_BREAKER_THRESHOLD:
        return GuardResult(
            approved=False,
            reason=(
                f"🚨 サーキットブレーカー発動: {context_key} で{count}回連続エラー。"
                f"システムを停止します。手動で原因を確認してください。"
            ),
        )

    return GuardResult(approved=True, reason=f"サーキットブレーカー正常 ({count}回)")


def record_error(context_key: str) -> int:
    """エラーを記録してカウントを返す。"""
    _consecutive_errors[context_key] = _consecutive_errors.get(context_key, 0) + 1
    return _consecutive_errors[context_key]


# ── 取引前総合チェック ────────────────────────────────────────────────────────

def run_pre_trade_checks(
    ticker: str,
    action: str,
    entry_price: float,
    position_size_pct: float,
    stop_loss_price: Optional[float],
    current_positions: dict[str, float],
    portfolio_current_value: float,
    portfolio_peak_value: float,
) -> tuple[bool, list[str]]:
    """
    取引執行前にすべてのガードレールを一括チェックする。

    Returns:
        tuple[bool, list[str]]: (全チェック通過か, 問題リスト)
    """
    issues = []

    # HOLDは検証不要
    if action == "HOLD":
        return True, []

    # 1. ポジションサイズ検証
    pos_result = validate_position_size(position_size_pct, current_positions, ticker)
    if not pos_result.approved:
        issues.append(f"[ポジション] {pos_result.reason}")

    # 2. ストップロス検証（BUYのみ）
    if action == "BUY":
        sl_result = validate_stop_loss(stop_loss_price, entry_price)
        if not sl_result.approved:
            issues.append(f"[ストップロス] {sl_result.reason}")

    # 3. ドローダウン検証
    dd_result = check_portfolio_drawdown(portfolio_current_value, portfolio_peak_value)
    if not dd_result.approved:
        issues.append(f"[ドローダウン] {dd_result.reason}")

    # 4. サーキットブレーカー
    cb_result = check_circuit_breaker("pre_trade")
    if not cb_result.approved:
        issues.append(f"[サーキットブレーカー] {cb_result.reason}")

    all_passed = len(issues) == 0
    return all_passed, issues


# ── strategy.md 読み込み ──────────────────────────────────────────────────────

def load_current_strategy() -> str:
    """
    trading/harness/strategy.md の内容を読み込む。
    エージェントへのコンテキスト提供用。
    """
    strategy_path = Path(__file__).parent / "strategy.md"
    if not strategy_path.exists():
        return "⚠️ strategy.md が見つかりません。trading/harness/strategy.md を確認してください。"
    return strategy_path.read_text(encoding="utf-8")
