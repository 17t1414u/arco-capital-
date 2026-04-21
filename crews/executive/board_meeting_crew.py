"""
BoardMeetingCrew — 6役員の階層型クルー

CEO を manager_agent、CFO/CTO/COO/CMO/CPO を worker agents として配置する。
division_scanner で ArcoCapital/ 配下の事業部現状を自動注入し、
議事録を outputs/board_meeting_minutes.md → ArcoCapital/経営陣/取締役会議事録/
にリネームしてコピーする。
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from crewai import Crew, Process

from agents.executive.ceo import CEOAgent
from agents.executive.cfo import CFOAgent
from agents.executive.cmo import CMOAgent
from agents.executive.coo import COOAgent
from agents.executive.cpo import CPOAgent
from agents.executive.cto import CTOAgent
from config.settings import settings
from crews.base_crew import BaseCrew
from crews.executive.division_scanner import build_company_snapshot
from tasks.executive.board_meeting_tasks import build_board_meeting_tasks

BOARD_ARCHIVE_DIR = Path("ArcoCapital/経営陣/取締役会議事録")


def _slugify_topic(topic: str) -> str:
    """Filesystem-safe topic slug (keeps Japanese, strips path-breakers)."""
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "", topic).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or "取締役会"


class BoardMeetingCrew(BaseCrew):
    """6役員による取締役会 — 階層型クルー。"""

    def __init__(
        self,
        topic: str = "月次KPI設定と週次レビュー",
        revenue_target_jpy: int = 100_000,
        horizon_weeks: int = 4,
    ) -> None:
        self.topic = topic
        self.revenue_target_jpy = revenue_target_jpy
        self.horizon_weeks = horizon_weeks

    def build(self) -> Crew:
        ceo = CEOAgent.build()
        cfo = CFOAgent.build()
        cto = CTOAgent.build()
        coo = COOAgent.build()
        cmo = CMOAgent.build()
        cpo = CPOAgent.build()

        snapshot = build_company_snapshot()

        tasks = build_board_meeting_tasks(
            ceo_agent=ceo,
            cfo_agent=cfo,
            cto_agent=cto,
            coo_agent=coo,
            cmo_agent=cmo,
            cpo_agent=cpo,
            company_snapshot=snapshot,
            revenue_target_jpy=self.revenue_target_jpy,
            horizon_weeks=self.horizon_weeks,
        )

        return Crew(
            agents=[cfo, cto, coo, cmo, cpo],  # Workers — manager は含めない
            tasks=tasks,
            process=Process.hierarchical,
            manager_agent=ceo,
            memory=True,
            verbose=True,
        )

    def run(self) -> str:
        """
        Execute the meeting, then archive the minutes under
        ArcoCapital/経営陣/取締役会議事録/YYYY-MM-DD_<議題>.md
        """
        result = super().run()

        src = settings.output_dir / "board_meeting_minutes.md"
        if src.exists():
            date_prefix = datetime.now().strftime("%Y-%m-%d")
            filename = f"{date_prefix}_{_slugify_topic(self.topic)}.md"
            BOARD_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            dest = BOARD_ARCHIVE_DIR / filename
            shutil.copy2(src, dest)
            print(f"[board] 議事録をアーカイブしました: {dest}")

        return result


if __name__ == "__main__":
    crew = BoardMeetingCrew()
    print(crew.run())
