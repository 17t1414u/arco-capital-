"""
Division scanner — reads the ArcoCapital/ tree to build a compact
"current state of each division" snapshot for injection into the
board meeting prompt.

Used by BoardMeetingCrew so that the CEO and other executives can
reason over the real, current state of the company instead of
working from stale hand-written summaries.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta
from pathlib import Path

ARCO_ROOT = Path("ArcoCapital")

# Divisions under ArcoCapital/ that the board treats as business units.
# HP is a supporting asset, not a revenue-bearing division, so it is
# summarised briefly rather than asked for KPIs.
KNOWN_DIVISIONS: list[str] = [
    "資産運用事業部",
    "SNS動画運用事業部",
    "ナレッジ連携事業部",
    "HP",
]


def _read_if_exists(path: Path, max_chars: int = 2000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...（省略）"
    return text


def _list_files(dir_path: Path, max_items: int = 20) -> list[str]:
    if not dir_path.exists() or not dir_path.is_dir():
        return []
    items: list[str] = []
    for child in sorted(dir_path.rglob("*")):
        if child.is_file():
            items.append(str(child.relative_to(dir_path)).replace("\\", "/"))
        if len(items) >= max_items:
            items.append("...（以下省略）")
            break
    return items


def scan_division(name: str) -> str:
    """Build a markdown snapshot for a single division."""
    div_dir = ARCO_ROOT / name
    if not div_dir.exists():
        return f"### {name}\n（ディレクトリ未作成）\n"

    claude_md = _read_if_exists(div_dir / "CLAUDE.md")
    index_md = _read_if_exists(div_dir / "index.md")
    files = _list_files(div_dir)

    parts: list[str] = [f"### {name}"]
    if claude_md:
        parts.append("**CLAUDE.md 抜粋**:\n```\n" + claude_md + "\n```")
    if index_md and not claude_md:
        parts.append("**index.md 抜粋**:\n```\n" + index_md + "\n```")
    if files:
        parts.append("**現在のファイル一覧** (最大20件):\n- " + "\n- ".join(files))
    if not (claude_md or index_md or files):
        parts.append("（中身なし — 未着手）")
    return "\n\n".join(parts) + "\n"


def _recent_commits(since_days: int = 7) -> str:
    """Return recent git log messages for activity context."""
    try:
        since = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d")
        out = subprocess.check_output(
            ["git", "log", f"--since={since}", "--pretty=format:%h %s (%ad)", "--date=short"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip() or "（直近コミットなし）"
    except Exception as e:  # noqa: BLE001
        return f"（git log 取得失敗: {e}）"


def build_company_snapshot() -> str:
    """
    Build the full markdown snapshot injected into board meeting prompts.

    Sections:
      - 会社全体のディレクトリ構造
      - 事業部ごとの現状
      - 直近1週間のコミットログ
    """
    today = datetime.now().strftime("%Y-%m-%d")
    lines: list[str] = [
        f"# ArcoCapital 会社スナップショット ({today})\n",
        "## 事業部の現状\n",
    ]
    for div in KNOWN_DIVISIONS:
        lines.append(scan_division(div))

    lines.append("## 直近1週間の開発コミット\n")
    lines.append("```\n" + _recent_commits(7) + "\n```\n")
    return "\n".join(lines)


if __name__ == "__main__":
    print(build_company_snapshot())
