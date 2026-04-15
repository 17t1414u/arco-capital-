"""
LLM factory.
Returns a configured crewai.LLM instance backed by Anthropic Claude.

Call chain: CrewAI Agent → crewai.LLM → LiteLLM → Anthropic API

The model string uses LiteLLM's provider-prefixed format:
  "anthropic/<model-id>"
LiteLLM resolves ANTHROPIC_API_KEY from the environment automatically,
but we pass it explicitly for clarity.
"""

from crewai import LLM

from config.settings import settings


def get_llm() -> LLM:
    """Return a fresh LLM instance with settings from environment."""
    return LLM(
        model=settings.model_name,
        api_key=settings.anthropic_api_key,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,  # Required for Anthropic API
    )
