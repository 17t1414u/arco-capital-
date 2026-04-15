"""
Base class for all company agents.

Every agent in the virtual company inherits from BaseAgent and overrides
class-level attributes. Calling `.build()` returns a fresh crewai.Agent
instance. A new instance is created per crew run to avoid state bleed
between executions.
"""

from crewai import Agent

from config.llm import get_llm


class BaseAgent:
    """
    Abstract base for all agents.

    Subclass and set class attributes:
        role       — job title shown to other agents
        goal       — primary objective driving this agent's behavior
        backstory  — expertise context injected into the system prompt
        allow_delegation — whether this agent can assign subtasks to others
    """

    role: str = ""
    goal: str = ""
    backstory: str = ""
    allow_delegation: bool = False

    @classmethod
    def build(cls) -> Agent:
        if not cls.role:
            raise NotImplementedError(
                f"{cls.__name__} must define a non-empty `role`."
            )
        return Agent(
            role=cls.role,
            goal=cls.goal,
            backstory=cls.backstory,
            llm=get_llm(),
            allow_delegation=cls.allow_delegation,
            verbose=True,
        )
