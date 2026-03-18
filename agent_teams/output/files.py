"""File output utilities."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from agent_teams.config import get_settings
from agent_teams.core.message import TaskContext


def save_result(context: TaskContext, filename: str | None = None) -> Path:
    """Save the final result to a file."""
    settings = get_settings()
    output_dir = Path(settings.output.default_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = ".py" if context.task_type.value == "coding" else ".md"
        filename = f"{context.task_type.value}_{timestamp}{ext}"

    path = output_dir / filename

    # Get the last artifact as final output
    if context.artifacts:
        last_key = list(context.artifacts.keys())[-1]
        content = str(context.artifacts[last_key])
    else:
        content = "No output generated."

    path.write_text(content, encoding="utf-8")
    return path
