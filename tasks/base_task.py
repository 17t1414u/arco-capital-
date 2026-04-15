"""
Task factory helper.

Wraps crewai.Task creation with automatic output directory setup.
All tasks should be created through make_task() to ensure output paths
resolve consistently regardless of the working directory.
"""

from pathlib import Path

from crewai import Task

from config.settings import settings


def make_task(
    description: str,
    expected_output: str,
    agent,
    output_file: str | None = None,
) -> Task:
    """
    Create a CrewAI Task.

    Args:
        description:     What the agent should do (markdown-friendly).
        expected_output: Format and content the task result must satisfy.
        agent:           The crewai.Agent instance responsible for this task.
        output_file:     Optional filename (not full path) to write the result.
                         Written under settings.output_dir automatically.
    """
    kwargs: dict = dict(
        description=description,
        expected_output=expected_output,
        agent=agent,
    )

    if output_file:
        path: Path = settings.output_dir / output_file
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        kwargs["output_file"] = str(path)

    return Task(**kwargs)
