"""
KnowledgeDivisionCrew — ナレッジ連携事業部の階層型クルー。

Process.hierarchical:
  manager_agent: KnowledgeDirector (allow_delegation=True)
  agents:        [KnowledgeCurator, SynthesisAnalyst, TemplateAuthor]
"""

from __future__ import annotations

from crewai import Crew, Process

from agents.knowledge import (
    KnowledgeCuratorAgent,
    KnowledgeDirectorAgent,
    SynthesisAnalystAgent,
    TemplateAuthorAgent,
)
from crews.base_crew import BaseCrew
from operations.guardrails_loader import ModeManager, load_guardrails
from tasks.knowledge.weekly_tasks import build_knowledge_week1_tasks


class KnowledgeDivisionCrew(BaseCrew):
    """ナレッジ連携事業部 Week1 階層型クルー。

    Parameters
    ----------
    pack_title:
        商品化するテンプレパックのタイトル (note 販売ページで使用)
    price_jpy:
        テンプレパックの販売価格 (既定 ¥2,980)
    """

    DIVISION_KEY = "knowledge"

    def __init__(
        self,
        pack_title: str = "Obsidian × Claude Code 外部脳スターターキット v1.0",
        price_jpy: int = 2_980,
    ) -> None:
        self.pack_title = pack_title
        self.price_jpy = price_jpy
        self._guardrails = load_guardrails()
        self._mode_manager = ModeManager(self._guardrails)

        mode = self._mode_manager.division_mode(self.DIVISION_KEY)
        if mode == "A":
            print(
                f"[{self.DIVISION_KEY}] Mode A (Dry-run) — note 公開は無効化されます。"
            )
        elif mode == "B":
            print(
                f"[{self.DIVISION_KEY}] Mode B (Semi-live) — "
                "note LP 公開前にオーナー承認が必要です (4/23 期限厳守)。"
            )
        elif mode == "C":
            print(f"[{self.DIVISION_KEY}] Mode C (Full-live) — 自動実行モード。")

    def build(self) -> Crew:
        director = KnowledgeDirectorAgent.build()
        curator = KnowledgeCuratorAgent.build()
        analyst = SynthesisAnalystAgent.build()
        author = TemplateAuthorAgent.build()

        api_cfg = self._guardrails.budget("anthropic_api")

        tasks = build_knowledge_week1_tasks(
            director=director,
            curator=curator,
            analyst=analyst,
            author=author,
            pack_title=self.pack_title,
            price_jpy=self.price_jpy,
            api_daily_cap_jpy=int(api_cfg["daily_limit_jpy"]),
        )

        return Crew(
            agents=[curator, analyst, author],
            tasks=tasks,
            process=Process.hierarchical,
            manager_agent=director,
            memory=True,
            verbose=True,
        )


if __name__ == "__main__":  # pragma: no cover
    crew = KnowledgeDivisionCrew()
    print(crew.run())
