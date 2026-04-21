"""Monitoring dashboard report generator for Arco Capital.

Phase 1 ゲート(2026-04-25) の CTO 拘束条件「監視ダッシュボード稼働」を満たす v0.1 実装。
3指標 (エラー率 / DM応答SLO / コスト) を JSON Lines ログから集計し、
``ArcoCapital/経営陣/監視レポート/YYYY-MM-DD.md`` に Markdown レポートを書き出す。

設計書: ``ArcoCapital/経営陣/監視ダッシュボード設計書.md`` v0.1

データソース:
    - ``operations/budget_log.jsonl``   — BudgetTracker が記録 (必須)
    - ``operations/incident_log.jsonl`` — Kill-switch / 誤投稿インシデント (必須)
    - ``operations/dm_log.csv``          — 手動 DM 応答記録 (存在すれば読む)

CLI:
    python -m operations.dashboard_report --date 2026-04-22
    python -m operations.dashboard_report --date today
    python -m operations.dashboard_report --date today --stdout   # 書き出さず標準出力のみ

終了コード:
    0  全指標 Green
    1  Amber が1件以上(Red なし)
    2  Red が1件以上
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from operations.guardrails_loader import Guardrails, load_guardrails

# ──────────────────────────────────────────────────────────────
# 定数
# ──────────────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))

BASE_DIR = Path(__file__).resolve().parent
BUDGET_LOG = BASE_DIR / "budget_log.jsonl"
INCIDENT_LOG = BASE_DIR / "incident_log.jsonl"
DM_LOG = BASE_DIR / "dm_log.csv"

DEFAULT_REPORT_DIR = (
    BASE_DIR.parent / "ArcoCapital" / "経営陣" / "監視レポート"
)

# 設計書 §1 で合意された閾値
ERROR_AMBER_RATIO = 0.05
ERROR_RED_RATIO = 0.10
DM_AMBER_HOURS = 20.0
DM_RED_HOURS = 24.0
COST_AMBER_RATIO = 0.70
COST_RED_RATIO = 0.90

# ステータス表記 (Markdown で視認性を担保)
STATUS_GREEN = "Green ✅"
STATUS_AMBER = "Amber ⚠"
STATUS_RED = "Red 🛑"
STATUS_UNKNOWN = "N/A (データ不足)"


# ──────────────────────────────────────────────────────────────
# 結果構造体
# ──────────────────────────────────────────────────────────────


@dataclass
class MetricResult:
    """単一指標の集計結果。"""

    label: str
    status: str
    lines: list[str] = field(default_factory=list)

    @property
    def is_red(self) -> bool:
        return self.status == STATUS_RED

    @property
    def is_amber(self) -> bool:
        return self.status == STATUS_AMBER

    @property
    def is_unknown(self) -> bool:
        return self.status == STATUS_UNKNOWN


# ──────────────────────────────────────────────────────────────
# 分類ヘルパ
# ──────────────────────────────────────────────────────────────


def classify_ratio(ratio: float, amber: float, red: float) -> str:
    """閾値を超過した順に Red/Amber/Green を返す。"""
    if ratio >= red:
        return STATUS_RED
    if ratio >= amber:
        return STATUS_AMBER
    return STATUS_GREEN


def classify_hours(hours: float, amber: float, red: float) -> str:
    """DM応答時間用の分類 (時間が長いほど悪化)。"""
    if hours >= red:
        return STATUS_RED
    if hours >= amber:
        return STATUS_AMBER
    return STATUS_GREEN


# ──────────────────────────────────────────────────────────────
# 日付フィルタ
# ──────────────────────────────────────────────────────────────


def _parse_jst_date(iso_ts: str) -> date | None:
    """ISO8601 文字列 (タイムゾーン付き) を JST の date に変換。"""
    try:
        dt = datetime.fromisoformat(iso_ts)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(JST).date()


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    """JSON Lines を1行ずつ辞書で返す。ファイル欠落は空イテレータ。"""
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # 破損行は黙って飛ばさず stderr に警告する (RULE-04 準拠)
                sys.stderr.write(
                    f"[dashboard_report] malformed JSONL line in {path.name}: "
                    f"{line[:120]!r}\n"
                )


# ──────────────────────────────────────────────────────────────
# コスト指標 (budget_log.jsonl → ¥消費/予算比)
# ──────────────────────────────────────────────────────────────


def collect_cost(
    target_date: date, guardrails: Guardrails, log_path: Path = BUDGET_LOG
) -> MetricResult:
    """コスト指標を集計。

    API は日次、Renoise は ISO 週次という bucket 仕様に合わせて
    period_key を判定する。
    """
    lines: list[str] = []
    worst = STATUS_GREEN

    buckets = (
        ("anthropic_api", _period_key_for_bucket("anthropic_api", target_date)),
        ("renoise_credits", _period_key_for_bucket("renoise_credits", target_date)),
    )

    for bucket, period_key in buckets:
        cfg = guardrails.budget(bucket)
        limit = int(cfg.get("daily_limit_jpy") or cfg.get("weekly_limit_jpy") or 0)

        used = 0
        for entry in _iter_jsonl(log_path):
            if entry.get("level") == "WARN":
                # WARN 行は原本の複製なので二重計上しない
                continue
            if entry.get("bucket") != bucket:
                continue
            if entry.get("period") != period_key:
                continue
            used += int(entry.get("added_jpy", 0))

        ratio = (used / limit) if limit else 0.0
        status = classify_ratio(ratio, COST_AMBER_RATIO, COST_RED_RATIO)
        worst = _worse(worst, status)

        label_ja = "Anthropic API (日次)" if bucket == "anthropic_api" else "Renoise (週次)"
        pct = f"{ratio * 100:.0f}%"
        lines.append(
            f"- **{label_ja}** ({period_key}): "
            f"¥{used:,} / ¥{limit:,} ({pct}) — {status}"
        )

    return MetricResult(label="コスト", status=worst, lines=lines)


def _period_key_for_bucket(bucket: str, target_date: date) -> str:
    if bucket == "renoise_credits":
        iso = target_date.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return target_date.isoformat()


# ──────────────────────────────────────────────────────────────
# DM応答SLO (dm_log.csv)
# ──────────────────────────────────────────────────────────────


def collect_slo(target_date: date, csv_path: Path = DM_LOG) -> MetricResult:
    """DM応答時間の中央値と P95 を集計。

    CSV フォーマット (ヘッダ必須):
        received_at, responded_at
        2026-04-22T09:15:00+09:00, 2026-04-22T11:40:00+09:00
    """
    if not csv_path.exists():
        return MetricResult(
            label="DM応答SLO",
            status=STATUS_UNKNOWN,
            lines=[
                f"- データソース `{csv_path.name}` が未配置。"
                "オーナーが日次で DM 応答時間を記録する CSV を作成してください。",
                f"- 対象日: {target_date.isoformat()}",
            ],
        )

    durations_h: list[float] = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"received_at", "responded_at"}
        if not required.issubset(set(reader.fieldnames or [])):
            return MetricResult(
                label="DM応答SLO",
                status=STATUS_UNKNOWN,
                lines=[
                    f"- `{csv_path.name}` のヘッダが不正。"
                    f"必須列: {sorted(required)}"
                ],
            )
        for row in reader:
            recv = _parse_iso(row.get("received_at", ""))
            resp = _parse_iso(row.get("responded_at", ""))
            if not recv or not resp:
                continue
            if recv.astimezone(JST).date() != target_date:
                continue
            durations_h.append((resp - recv).total_seconds() / 3600.0)

    if not durations_h:
        return MetricResult(
            label="DM応答SLO",
            status=STATUS_UNKNOWN,
            lines=[
                f"- 対象日 ({target_date.isoformat()}) に該当する DM エントリなし。",
            ],
        )

    median_h = statistics.median(durations_h)
    p95_h = _percentile(durations_h, 0.95)
    status = classify_hours(p95_h, DM_AMBER_HOURS, DM_RED_HOURS)

    lines = [
        f"- 対象 DM: {len(durations_h)} 件",
        f"- 中央値: {median_h:.1f}h",
        f"- P95: {p95_h:.1f}h — {status}",
    ]
    return MetricResult(label="DM応答SLO", status=status, lines=lines)


def _parse_iso(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt


def _percentile(values: list[float], pct: float) -> float:
    """簡易パーセンタイル (線形補間)。values は空でない前提。"""
    if len(values) == 1:
        return values[0]
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * pct
    f_idx = int(k)
    c_idx = min(f_idx + 1, len(sorted_vals) - 1)
    if f_idx == c_idx:
        return sorted_vals[f_idx]
    return sorted_vals[f_idx] + (sorted_vals[c_idx] - sorted_vals[f_idx]) * (k - f_idx)


# ──────────────────────────────────────────────────────────────
# エラー率 / インシデント (incident_log.jsonl)
# ──────────────────────────────────────────────────────────────


def collect_errors(
    target_date: date, log_path: Path = INCIDENT_LOG
) -> MetricResult:
    """エラー率とインシデント発火数を集計。

    v0.1 は incident_log.jsonl の件数をベースに、以下のポリシーで判定:
        0 件               → Green
        1 件(Amber 系)     → Amber
        manual/budget/炎上 → Red
    """
    incidents_today: list[dict[str, Any]] = []
    for entry in _iter_jsonl(log_path):
        ts = entry.get("ts", "")
        if _parse_jst_date(ts) == target_date:
            incidents_today.append(entry)

    if not incidents_today:
        return MetricResult(
            label="エラー率 / インシデント",
            status=STATUS_GREEN,
            lines=[
                f"- 対象日: {target_date.isoformat()}",
                "- Kill-switch 発火: 0 件",
                "- 誤投稿 / 炎上報告: 0 件",
            ],
        )

    # trigger 別に集計
    red_triggers = {"budget_breach", "flaming_incident_reported", "misfire_detected"}
    red_count = sum(
        1 for i in incidents_today if i.get("trigger") in red_triggers
    )
    manual_count = sum(1 for i in incidents_today if i.get("trigger") == "manual")

    status = STATUS_RED if red_count else STATUS_AMBER
    lines = [
        f"- 対象日: {target_date.isoformat()}",
        f"- Kill-switch 発火総数: {len(incidents_today)} 件",
        f"  - 致命的トリガ(budget/flaming/misfire): {red_count} 件",
        f"  - 手動発火: {manual_count} 件",
    ]
    # 直近3件の詳細を同梱
    lines.append("- 発火詳細 (最大3件):")
    for i in incidents_today[:3]:
        lines.append(
            f"  - `{i.get('ts', '?')}` trigger=`{i.get('trigger', '?')}` "
            f"reason={_truncate(i.get('reason', ''), 60)}"
        )
    return MetricResult(label="エラー率 / インシデント", status=status, lines=lines)


def _truncate(s: str, n: int) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


# ──────────────────────────────────────────────────────────────
# Markdown レンダリング
# ──────────────────────────────────────────────────────────────


def render_markdown(
    target_date: date,
    *,
    cost: MetricResult,
    slo: MetricResult,
    errors: MetricResult,
    active_mode: str,
) -> str:
    overall = _overall_status([cost, slo, errors])
    title_date = target_date.isoformat()
    lines: list[str] = []
    lines.append(f"# 監視レポート {title_date}")
    lines.append("")
    lines.append(f"**生成時刻**: {datetime.now(JST).strftime('%Y-%m-%d %H:%M %Z')}")
    lines.append(f"**運用モード**: {active_mode}")
    lines.append(f"**総合ステータス**: **{overall}**")
    lines.append("")
    lines.append("---")
    lines.append("")
    for metric in (errors, slo, cost):
        lines.append(f"## {metric.label} — {metric.status}")
        lines.append("")
        lines.extend(metric.lines)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 次アクション")
    lines.append("")
    lines.extend(_action_lines(cost, slo, errors))
    lines.append("")
    lines.append(
        "_本レポートは `operations/dashboard_report.py` により自動生成。"
        "Phase 1 ゲート (4/25) の CTO 拘束条件『監視ダッシュボード稼働』を満たす v0.1 実装。_"
    )
    lines.append("")
    return "\n".join(lines)


def _overall_status(metrics: list[MetricResult]) -> str:
    if any(m.is_red for m in metrics):
        return STATUS_RED
    if any(m.is_amber for m in metrics):
        return STATUS_AMBER
    if all(m.status == STATUS_GREEN for m in metrics):
        return STATUS_GREEN
    return STATUS_UNKNOWN


def _action_lines(*metrics: MetricResult) -> list[str]:
    actions: list[str] = []
    for m in metrics:
        if m.is_red:
            actions.append(
                f"- 🛑 **{m.label}**: Red 到達。Kill-switch 発火 or 該当 Director を Mode A 降格すること。"
            )
        elif m.is_amber:
            actions.append(
                f"- ⚠ **{m.label}**: Amber。次回取締役会で議題化。"
            )
        elif m.is_unknown:
            actions.append(
                f"- ❔ **{m.label}**: データソース未整備。運用担当が入力 IF を整えること。"
            )
    if not actions:
        actions.append("- ✅ 全指標 Green。本日のオーナー対応は不要。")
    return actions


def _worse(a: str, b: str) -> str:
    """2つのステータスのうち厳しい方を返す。"""
    order = [STATUS_GREEN, STATUS_UNKNOWN, STATUS_AMBER, STATUS_RED]
    return a if order.index(a) >= order.index(b) else b


# ──────────────────────────────────────────────────────────────
# 書き出し
# ──────────────────────────────────────────────────────────────


def write_report(
    target_date: date, body: str, outdir: Path = DEFAULT_REPORT_DIR
) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{target_date.isoformat()}.md"
    out.write_text(body, encoding="utf-8")
    return out


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────


def _resolve_date(value: str) -> date:
    if value == "today":
        return datetime.now(JST).date()
    if value == "yesterday":
        return (datetime.now(JST) - timedelta(days=1)).date()
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"--date は YYYY-MM-DD / today / yesterday を指定 (got {value!r})"
        ) from e


def _exit_code(metrics: list[MetricResult]) -> int:
    if any(m.is_red for m in metrics):
        return 2
    if any(m.is_amber for m in metrics):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Arco Capital 監視ダッシュボード (v0.1 Markdown レポート)"
    )
    ap.add_argument(
        "--date",
        type=_resolve_date,
        default=_resolve_date("today"),
        help="対象日 (YYYY-MM-DD / today / yesterday, 既定: today)",
    )
    ap.add_argument(
        "--stdout",
        action="store_true",
        help="ファイルに書き出さず標準出力のみ",
    )
    ap.add_argument(
        "--outdir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="レポート出力ディレクトリ",
    )
    args = ap.parse_args(argv)

    # Windows の cmd.exe 既定 (cp932) だと UTF-8 文字で UnicodeEncodeError になる。
    # PYTHONIOENCODING=utf-8 の .bat ラッパでは問題にならないが、生の呼び出し時も
    # 壊れないように stdout/stderr を UTF-8 に reconfigure しておく。
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.encoding and stream.encoding.lower() != "utf-8":
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    guardrails = load_guardrails()
    cost = collect_cost(args.date, guardrails)
    slo = collect_slo(args.date)
    errors = collect_errors(args.date)

    body = render_markdown(
        args.date,
        cost=cost,
        slo=slo,
        errors=errors,
        active_mode=f"{guardrails.active_mode} ({guardrails.mode_config()['label']})",
    )

    if args.stdout:
        sys.stdout.write(body)
    else:
        out = write_report(args.date, body, outdir=args.outdir)
        sys.stderr.write(f"[dashboard_report] wrote {out}\n")

    return _exit_code([cost, slo, errors])


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
