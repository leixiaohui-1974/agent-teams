"""Rich console output for agent teams."""
from __future__ import annotations

import io
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from agent_teams.core.message import AgentResult

# Force UTF-8 output on Windows to avoid GBK encoding errors
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

console = Console(force_terminal=True)

AGENT_COLORS = {
    "coordinator": "bright_yellow",
    "architect": "bright_cyan",
    "writer": "bright_green",
    "coder": "bright_blue",
    "reviewer": "bright_magenta",
    "researcher": "bright_white",
    "imagegen": "bright_red",
}


def print_header(title: str) -> None:
    console.print()
    console.print(Panel(
        Text(title, style="bold white", justify="center"),
        style="bright_cyan",
        expand=True,
    ))
    console.print()


def print_step_start(step_num: int, total: int, agent_name: str, instruction: str) -> None:
    color = AGENT_COLORS.get(agent_name, "white")
    console.print()
    console.rule(f"[{color}]Step {step_num}/{total}: {agent_name.upper()}[/{color}]")
    console.print(f"  [dim]{instruction[:120]}{'...' if len(instruction) > 120 else ''}[/dim]")
    console.print()


def print_step_output(step_num: int, agent_name: str, result: AgentResult) -> None:
    color = AGENT_COLORS.get(agent_name, "white")
    content = result.content
    # Truncate very long outputs for display
    if len(content) > 3000:
        content = content[:3000] + "\n\n... [truncated for display]"
    console.print(Panel(
        Markdown(content),
        title=f"[{color}]{agent_name}[/{color}] ({result.model_used})",
        border_style=color,
        padding=(1, 2),
    ))


def print_final_result(context) -> None:
    console.print()
    console.print(Panel(
        Text("TASK COMPLETE", style="bold bright_green", justify="center"),
        style="bright_green",
    ))

    # Show the last artifact as the final output
    if context.artifacts:
        last_key = list(context.artifacts.keys())[-1]
        last_value = str(context.artifacts[last_key])
        console.print()
        console.print(Panel(
            Markdown(last_value),
            title="[bright_green]Final Output[/bright_green]",
            border_style="bright_green",
            padding=(1, 2),
        ))

    # Show image paths if any
    if context.image_paths:
        console.print()
        for path in context.image_paths:
            console.print(f"  [bright_red]Image:[/bright_red] {path}")

    # Show agent execution summary
    print_summary(context)


def print_summary(context) -> None:
    """Print a structured summary of agent/model contributions."""
    from collections import defaultdict
    if not context.agent_log:
        return

    console.print()

    # Group by agent
    agent_models: dict[str, list[str]] = defaultdict(list)
    model_tasks: dict[str, list[str]] = defaultdict(list)

    for action in context.agent_log:
        agent_models[action.agent_name].append(action.model)
        model_tasks[action.model].append(action.agent_name)

    # Summary table
    from rich.table import Table
    table = Table(title="Execution Summary", border_style="dim", expand=True)
    table.add_column("Agent", style="bold")
    table.add_column("Model", style="cyan")
    table.add_column("Task", style="dim")

    for action in context.agent_log:
        color = AGENT_COLORS.get(action.agent_name, "white")
        table.add_row(
            f"[{color}]{action.agent_name}[/{color}]",
            action.model,
            action.output_summary[:80] + ("..." if len(action.output_summary) > 80 else ""),
        )

    console.print(table)

    # Model usage stats
    providers = {"claude": 0, "gemini": 0, "gpt": 0}
    for action in context.agent_log:
        m = action.model.lower()
        if "claude" in m:
            providers["claude"] += 1
        elif "gemini" in m:
            providers["gemini"] += 1
        elif "gpt" in m:
            providers["gpt"] += 1

    total = sum(providers.values()) or 1
    stats = " | ".join(
        f"[{'bright_blue' if k == 'claude' else 'bright_yellow' if k == 'gemini' else 'bright_green'}]"
        f"{k}: {v} ({v*100//total}%)[/]"
        for k, v in providers.items() if v > 0
    )
    console.print(f"\n  Model usage: {stats}")


def print_models(models: list[str]) -> None:
    console.print()
    console.print(Panel("Available Models", style="bright_cyan"))
    for m in sorted(models):
        console.print(f"  - {m}")
    console.print(f"\n  [dim]Total: {len(models)} models[/dim]")


def print_error(msg: str) -> None:
    console.print(f"\n[bold red]Error:[/bold red] {msg}\n")
