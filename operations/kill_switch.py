"""Emergency Kill-switch for Arco Capital operations.

ボードルーム決議 (2026-04-21) CTO 拘束条件:
    「Director→配下クルー実装完了前のFull-live禁止、Renoise例外処理設計書PR化、
      監視ダッシュボード稼働、Kill-switch明文化」

本モジュールはこれを満たす最低限の Kill-switch:
    1. 全事業部を Mode A (Dry-run) へ強制ダウングレード (guardrails.yaml 書き換え)
    2. incident_log.jsonl に発火理由を追記
    3. 標準出力に手順ガイドを表示

CLI:
    python -m operations.kill_switch --trigger manual --reason "オーナー判断"
    python -m operations.kill_switch --trigger budget_breach --bucket anthropic_api
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import yaml
except ImportError as e:  # pragma: no cover
    raise RuntimeError("PyYAML が必要です。pip install pyyaml を実行してください。") from e


GUARDRAILS_PATH = Path(__file__).resolve().parent / "guardrails.yaml"
INCIDENT_LOG = Path(__file__).resolve().parent / "incident_log.jsonl"
JST = timezone(timedelta(hours=9))

VALID_TRIGGERS = {
    "budget_breach",
    "flaming_incident_reported",
    "misfire_detected",
    "manual",
}


def _append_incident(entry: dict) -> None:
    with INCIDENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _downgrade_all_divisions() -> list[str]:
    data = yaml.safe_load(GUARDRAILS_PATH.read_text(encoding="utf-8"))
    changed: list[str] = []
    for key, div in data.get("divisions", {}).items():
        if div.get("mode") != "A":
            div["mode"] = "A"
            changed.append(key)
    data["active_mode"] = "A"
    GUARDRAILS_PATH.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return changed


def fire(trigger: str, *, reason: str, **kwargs: object) -> dict:
    """Kill-switch を発火させる。呼び出し元は終了コード 2 で止まること。"""
    if trigger not in VALID_TRIGGERS:
        raise ValueError(
            f"Invalid trigger {trigger!r}. Valid: {sorted(VALID_TRIGGERS)}"
        )
    changed = _downgrade_all_divisions()
    entry = {
        "ts": datetime.now(JST).isoformat(),
        "trigger": trigger,
        "reason": reason,
        "downgraded_divisions": changed,
        **kwargs,
    }
    _append_incident(entry)
    sys.stderr.write(
        "\n[KILL-SWITCH FIRED] trigger={trig} reason={r}\n"
        "- 全事業部を Mode A (Dry-run) に差し戻しました。\n"
        "- incident_log.jsonl に記録しました: {log}\n"
        "- 対応手順: ArcoCapital/経営陣/Kill-Switch設計書.md を参照\n".format(
            trig=trigger, r=reason, log=INCIDENT_LOG
        )
    )
    return entry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Arco Capital Kill-switch")
    ap.add_argument("--trigger", required=True, choices=sorted(VALID_TRIGGERS))
    ap.add_argument("--reason", required=True, help="発火理由 (人間可読)")
    ap.add_argument("--bucket", default=None, help="budget_breach の場合の該当 bucket")
    args = ap.parse_args(argv)

    extra = {}
    if args.bucket:
        extra["bucket"] = args.bucket

    fire(args.trigger, reason=args.reason, **extra)
    return 2  # 呼び出し元プロセスに異常終了を伝える


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
