"""Budget tracking for Arco Capital operations.

予算消費を ``operations/budget_status.json`` に追記し、
ハードキャップ超過時は ``BudgetBreach`` を送出して ``kill_switch`` を発火する。

RULE-04 (サイレントフォールバック禁止) の実装:
    - 閾値超過は絶対に続行しない
    - 全記録は JSON Lines で永続化
    - 致命的例外は kill_switch に委譲
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from operations.guardrails_loader import Guardrails, load_guardrails

STATE_PATH = Path(__file__).resolve().parent / "budget_status.json"
LOG_PATH = Path(__file__).resolve().parent / "budget_log.jsonl"

JST = timezone(timedelta(hours=9))


class BudgetBreach(RuntimeError):
    """予算ハードキャップ超過時に送出される致命的例外。

    捕捉せず、kill_switch に伝播させること (RULE-04)。
    """

    def __init__(self, bucket: str, used_jpy: int, limit_jpy: int, message: str):
        super().__init__(message)
        self.bucket = bucket
        self.used_jpy = used_jpy
        self.limit_jpy = limit_jpy


@dataclass
class BudgetTracker:
    """予算消費の記録・警告・Kill-switch 発火。

    Parameters
    ----------
    guardrails:
        ``load_guardrails()`` の結果。
    state_path:
        消費状態の永続化先 (JSON)。
    log_path:
        全記録の追記先 (JSON Lines)。
    """

    guardrails: Guardrails
    state_path: Path = STATE_PATH
    log_path: Path = LOG_PATH

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _append_log(self, entry: dict[str, Any]) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ---- public API ------------------------------------------------------

    def record_usage(
        self, bucket: str, jpy: int, *, source: str = "unknown"
    ) -> dict[str, Any]:
        """消費を記録し、閾値超過なら ``BudgetBreach`` を送出する。

        Parameters
        ----------
        bucket:
            ``anthropic_api`` / ``renoise_credits`` など guardrails.yaml と一致するキー
        jpy:
            消費額 (円)。負の値は許容しない。
        source:
            発生源 (例: ``sns_video_director``)
        """
        if jpy < 0:
            raise ValueError(f"jpy must be non-negative, got {jpy}")

        cfg = self.guardrails.budget(bucket)
        period_key = self._period_key(bucket)
        state = self._load_state()
        bucket_state = state.setdefault(bucket, {})
        current = int(bucket_state.get(period_key, 0)) + int(jpy)
        bucket_state[period_key] = current
        # ローテーション (古い period は保持、breach 判定は現在 period のみ)
        state[bucket] = bucket_state

        limit = int(cfg["daily_limit_jpy"]) if "daily_limit_jpy" in cfg else int(cfg["weekly_limit_jpy"])
        alert = int(limit * float(cfg["alert_threshold_ratio"]))

        self._save_state(state)
        entry = {
            "ts": datetime.now(JST).isoformat(),
            "bucket": bucket,
            "period": period_key,
            "used_jpy_this_period": current,
            "added_jpy": jpy,
            "limit_jpy": limit,
            "source": source,
        }
        self._append_log(entry)

        if current >= limit:
            if cfg.get("on_breach") == "kill_switch":
                # 致命的。呼び出し側で kill_switch を発火させる。
                raise BudgetBreach(
                    bucket=bucket,
                    used_jpy=current,
                    limit_jpy=limit,
                    message=(
                        f"[BUDGET BREACH] {bucket} で ¥{current:,}/¥{limit:,} 消費。"
                        f" RULE-04 に従い自動停止します。"
                    ),
                )
        if current >= alert:
            entry["warning"] = f"Alert threshold {alert} reached"
            self._append_log({"level": "WARN", **entry})
        return entry

    def snapshot(self) -> dict[str, Any]:
        """現在の消費状況のスナップショット。"""
        return self._load_state()

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _period_key(bucket: str) -> str:
        """Anthropic API は日次、Renoise は週次 (ISO week)。"""
        now = datetime.now(JST)
        if bucket == "anthropic_api":
            return now.date().isoformat()  # YYYY-MM-DD
        if bucket == "renoise_credits":
            y, w, _ = now.isocalendar()
            return f"{y}-W{w:02d}"
        # 未知 bucket は年月日で保守的に
        return now.date().isoformat()


def current_tracker() -> BudgetTracker:
    """デフォルト設定の ``BudgetTracker``。CLI/スクリプト向け。"""
    return BudgetTracker(guardrails=load_guardrails())


if __name__ == "__main__":  # pragma: no cover
    # 簡易スナップショット表示
    tracker = current_tracker()
    snapshot = tracker.snapshot()
    if not snapshot:
        print("(budget_status.json is empty — no usage recorded yet)")
    else:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
