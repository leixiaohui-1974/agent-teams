"""File output utilities."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from agent_teams.core.message import TaskContext


def save_result(context: TaskContext, filename: str | None = None, output_dir: str | None = None) -> Path:
    """Save the final result to a file.

    output_dir defaults to ./output relative to cwd (the user's project directory).
    """
    if output_dir:
        out = Path(output_dir)
    else:
        out = Path.cwd() / "output"
    out.mkdir(parents=True, exist_ok=True)

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = ".py" if context.task_type.value == "coding" else ".md"
        filename = f"{context.task_type.value}_{timestamp}{ext}"

    path = out / filename

    if context.artifacts:
        last_key = list(context.artifacts.keys())[-1]
        content = str(context.artifacts[last_key])
    else:
        content = "No output generated."

    path.write_text(content, encoding="utf-8")
    return path
