"""
trade_log.py — 構造化取引ログシステム

すべての取引決定をJSONL形式で記録する。
AGENTS.md RULE-10: ログなしでの取引実行は禁止。

ログファイル: trading/harness/logs/trade_log.jsonl
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

# ログ保存先
LOG_DIR = Path(__file__).parent / "logs"
TRADE_LOG_PATH = LOG_DIR / "trade_log.jsonl"


def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_trade_decision(
    ticker: str,
    action: str,  # "BUY" | "SELL" | "HOLD"
    entry_price: Optional[float],
    position_size_pct: float,
    signals: dict,
    bull_thesis: str,
    bear_thesis: str,
    risk_approved: bool,
    fund_manager_reasoning: str,
    strategy_version: str = "v1.0",
    session_id: Optional[str] = None,
) -> str:
    """
    取引決定をJSONLファイルに記録する。

    Returns:
        str: 生成されたログエントリのID
    """
    _ensure_log_dir()

    entry_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{ticker}"

    record = {
        "id": entry_id,
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id or entry_id,
        "ticker": ticker,
        "action": action,
        "entry_price": entry_price,
        "position_size_pct": position_size_pct,
        "strategy_version": strategy_version,
        "signals": signals,  # {fundamentals, sentiment, news, technical}
        "bull_thesis": bull_thesis,
        "bear_thesis": bear_thesis,
        "risk_approved": risk_approved,
        "fund_manager_reasoning": fund_manager_reasoning,
        # 事後に更新するフィールド
        "exit_price": None,
        "exit_timestamp": None,
        "pnl_pct": None,
        "outcome": None,        # "WIN" | "LOSS" | "HOLD_CORRECT" | "HOLD_MISSED"
        "quality_score": None,  # 1〜5 (Optimizerが評価)
    }

    with open(TRADE_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return entry_id


def update_trade_outcome(
    entry_id: str,
    exit_price: float,
    pnl_pct: float,
    outcome: str,  # "WIN" | "LOSS"
    quality_score: int,  # 1〜5
) -> bool:
    """
    ポジションクローズ後に取引結果を更新する。

    Returns:
        bool: 更新成功なら True
    """
    _ensure_log_dir()

    if not TRADE_LOG_PATH.exists():
        return False

    lines = TRADE_LOG_PATH.read_text(encoding="utf-8").strip().split("\n")
    updated = False

    new_lines = []
    for line in lines:
        if not line:
            continue
        record = json.loads(line)
        if record["id"] == entry_id:
            record["exit_price"] = exit_price
            record["exit_timestamp"] = datetime.now().isoformat()
            record["pnl_pct"] = pnl_pct
            record["outcome"] = outcome
            record["quality_score"] = quality_score
            updated = True
        new_lines.append(json.dumps(record, ensure_ascii=False))

    if updated:
        TRADE_LOG_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return updated


def get_recent_logs(n: int = 50) -> list[dict]:
    """直近N件の取引ログを取得する（Optimizer用）"""
    _ensure_log_dir()

    if not TRADE_LOG_PATH.exists():
        return []

    lines = TRADE_LOG_PATH.read_text(encoding="utf-8").strip().split("\n")
    records = [json.loads(line) for line in lines if line]
    return records[-n:]


def get_performance_summary(n: int = 50) -> dict:
    """
    直近N件のパフォーマンスサマリーを計算する。

    Returns:
        dict: {total, wins, losses, win_rate, avg_pnl, avg_quality_score,
               profit_factor, max_drawdown}
    """
    logs = get_recent_logs(n)
    closed = [r for r in logs if r.get("outcome") in ("WIN", "LOSS")]

    if not closed:
        return {"message": "クローズ済み取引がありません", "total": 0}

    wins = [r for r in closed if r["outcome"] == "WIN"]
    losses = [r for r in closed if r["outcome"] == "LOSS"]

    win_pnls = [r["pnl_pct"] for r in wins if r["pnl_pct"] is not None]
    loss_pnls = [abs(r["pnl_pct"]) for r in losses if r["pnl_pct"] is not None]

    avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0
    avg_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0
    profit_factor = avg_win / avg_loss if avg_loss > 0 else float("inf")

    quality_scores = [r["quality_score"] for r in closed if r["quality_score"]]
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

    return {
        "total": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(closed) * 100,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "profit_factor": profit_factor,
        "avg_quality_score": avg_quality,
    }


def format_logs_for_optimizer(n: int = 50) -> str:
    """
    Optimizerエージェントに渡すためのログテキストを生成する。
    """
    logs = get_recent_logs(n)
    if not logs:
        return "取引ログがありません。まだ取引を実行していないか、ログファイルが存在しません。"

    summary = get_performance_summary(n)
    lines = [f"## 直近{n}件の取引ログ\n"]

    if isinstance(summary, dict) and "win_rate" in summary:
        lines.append(f"### パフォーマンスサマリー")
        lines.append(f"- 取引数: {summary['total']}")
        lines.append(f"- 勝率: {summary['win_rate']:.1f}%")
        lines.append(f"- 平均利益: +{summary['avg_win_pct']:.2f}%")
        lines.append(f"- 平均損失: -{summary['avg_loss_pct']:.2f}%")
        lines.append(f"- プロフィットファクター: {summary['profit_factor']:.2f}")
        lines.append(f"- 平均品質スコア: {summary['avg_quality_score']:.1f}/5.0\n")

    lines.append("### 個別取引ログ")
    for log in logs[-20:]:  # 最新20件のみ詳細表示
        lines.append(
            f"[{log['timestamp'][:10]}] {log['ticker']} {log['action']} "
            f"| 結果: {log.get('outcome', '未クローズ')} "
            f"| PnL: {log.get('pnl_pct', 'N/A')} "
            f"| スコア: {log.get('quality_score', 'N/A')}/5"
        )

    return "\n".join(lines)
