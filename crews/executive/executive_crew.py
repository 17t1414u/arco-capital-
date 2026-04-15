"""
ExecutiveCrew — Phase 1 crew.

CEO acts as the hierarchical manager agent.
CTO is the worker agent.

Execution flow:
  kickoff()
    → CEO (manager) assigns cto_analysis_task to CTO
    → CTO produces 3 business domain candidates
    → CEO receives CTO's output as context, runs ceo_decision_task
    → CEO's decision written to outputs/discussion_result.md

IMPORTANT: In Process.hierarchical, the manager_agent must NOT appear
in the agents=[] list. Adding it to both causes a CrewAI runtime error.
"""

from crewai import Crew, Process

from agents.executive.ceo import CEOAgent
from agents.executive.cto import CTOAgent
from crews.base_crew import BaseCrew
from tasks.executive.strategy_tasks import build_strategy_tasks


class ExecutiveCrew(BaseCrew):
    """CEO + CTO strategy discussion crew."""

    def build(self) -> Crew:
        ceo_agent = CEOAgent.build()
        cto_agent = CTOAgent.build()

        tasks = build_strategy_tasks(ceo_agent, cto_agent)

        return Crew(
            agents=[cto_agent],           # Workers only — NOT the manager
            tasks=tasks,
            process=Process.hierarchical,
            manager_agent=ceo_agent,      # CEO orchestrates the crew
            memory=True,                  # Enable short-term + long-term memory
            verbose=True,
        )
