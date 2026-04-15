"""
trading/harness/ — 決定論的制御層（ハーネスエンジニアリング）

Components:
  strategy.md   — 現行売買戦略の唯一の真実の情報源
  trade_log.py  — 構造化取引ログ（JSONL形式）
  guardrails.py — 実行時安全制約（ポジション/ドローダウン/サーキットブレーカー）
"""

from trading.harness.trade_log import (
    log_trade_decision,
    update_trade_outcome,
    get_recent_logs,
    get_performance_summary,
    format_logs_for_optimizer,
)
from trading.harness.guardrails import (
    run_pre_trade_checks,
    validate_position_size,
    validate_stop_loss,
    check_portfolio_drawdown,
    check_circuit_breaker,
    record_error,
    load_current_strategy,
)

__all__ = [
    "log_trade_decision",
    "update_trade_outcome",
    "get_recent_logs",
    "get_performance_summary",
    "format_logs_for_optimizer",
    "run_pre_trade_checks",
    "validate_position_size",
    "validate_stop_loss",
    "check_portfolio_drawdown",
    "check_circuit_breaker",
    "record_error",
    "load_current_strategy",
]
