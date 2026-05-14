"""
SNSVideoDivisionCrew — SNS動画運用事業部の階層型クルー。

Process.hierarchical:
  manager_agent: SNSVideoDirector (allow_delegation=True)
  agents:        [VideoPlanner, VideoGenerator, VideoEditor, SalesAgent]

ガードレール (operations.guardrails_loader) を読み込み、
モード B 未満 (= Dry-run) の場合は外部送信を無効化する。
モード B 以上 (= Semi-live or Full-live) でのみ Renoise の有料生成が走る。
"""

from __future__ import annotations

from crewai import Crew, Process

from agents.sns_video import (
    SalesAgent,
    SNSVideoDirectorAgent,
    VideoEditorAgent,
    VideoGeneratorAgent,
    VideoPlannerAgent,
)
from crews.base_crew import BaseCrew
from operations.guardrails_loader import ModeManager, load_guardrails
from tasks.sns_video.weekly_tasks import build_sns_video_week1_tasks


class SNSVideoDivisionCrew(BaseCrew):
    """SNS動画事業部 Week1 階層型クルー。

    Parameters
    ----------
    project_slug:
        対象プロジェクト slug (既定: ``cinematic-everyday-01``、Phase 1 ゲート条件)
    """

    DIVISION_KEY = "sns_video"

    def __init__(self, project_slug: str = "cinematic-everyday-01") -> None:
        self.project_slug = project_slug
        self._guardrails = load_guardrails()
        self._mode_manager = ModeManager(self._guardrails)

        mode = self._mode_manager.division_mode(self.DIVISION_KEY)
        if mode == "A":
            print(
                f"[{self.DIVISION_KEY}] Mode A (Dry-run) — "
                "外部送信・有料クレジット消費は無効化されます。"
            )
        elif mode == "B":
            print(
                f"[{self.DIVISION_KEY}] Mode B (Semi-live) — "
                "最終納品前にオーナー承認が必要です。"
            )
        elif mode == "C":
            print(f"[{self.DIVISION_KEY}] Mode C (Full-live) — 自動実行モード。")

    def build(self) -> Crew:
        director = SNSVideoDirectorAgent.build()
        planner = VideoPlannerAgent.build()
        generator = VideoGeneratorAgent.build()
        editor = VideoEditorAgent.build()
        sales = SalesAgent.build()

        budget_cfg = self._guardrails.budget("renoise_credits")
        api_cfg = self._guardrails.budget("anthropic_api")

        tasks = build_sns_video_week1_tasks(
            director=director,
            planner=planner,
            generator=generator,
            editor=editor,
            sales=sales,
            project_slug=self.project_slug,
            renoise_weekly_cap_jpy=int(budget_cfg["weekly_limit_jpy"]),
            api_daily_cap_jpy=int(api_cfg["daily_limit_jpy"]),
        )

        return Crew(
            agents=[planner, generator, editor, sales],
            tasks=tasks,
            process=Process.hierarchical,
            manager_agent=director,
            memory=True,
            verbose=True,
        )


if __name__ == "__main__":  # pragma: no cover
    crew = SNSVideoDivisionCrew()
    print(crew.run())
