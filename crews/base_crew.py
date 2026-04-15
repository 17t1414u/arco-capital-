"""
BaseCrew — abstract wrapper around crewai.Crew.

All crew classes inherit from BaseCrew and implement build().
Callers use run() and never touch CrewAI internals directly.
"""

from crewai import Crew


class BaseCrew:
    """
    Base class for all crews.

    Subclass and implement build() to return a configured crewai.Crew.
    Use run() to execute the crew and receive the plain-text result.
    """

    def build(self) -> Crew:
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement build()."
        )

    def run(self) -> str:
        """Kick off the crew and return the final result as a plain string."""
        crew = self.build()
        result = crew.kickoff()
        return result.raw
