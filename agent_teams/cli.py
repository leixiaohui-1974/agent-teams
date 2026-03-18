"""CLI interface for Agent Teams."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click

from agent_teams.config import load_settings
from agent_teams.core.client import get_client
from agent_teams.core.message import TaskContext
from agent_teams.agents.coordinator import CoordinatorAgent
from agent_teams.workflows.base import WorkflowEngine
from agent_teams.output.console import (
    console,
    print_error,
    print_final_result,
    print_header,
    print_models,
    print_step_output,
    print_step_start,
    print_summary,
)
from agent_teams.output.files import save_result
from agent_teams.integrations.github import AutoGit


# -- shared git helper --
def _get_git(auto_push: bool = True, auto_init: bool = False) -> AutoGit:
    """Create AutoGit scoped to user's current working directory."""
    return AutoGit(cwd=str(Path.cwd()), auto_push=auto_push, auto_init=auto_init)


# -- core runners --

async def _run_task(
    task: str,
    output_file: str | None,
    config_path: str | None,
    auto_commit: bool = False,
) -> None:
    load_settings(config_path)
    client = get_client()

    print_header("Agent Teams")
    console.print(f"[dim]Task:[/dim] {task}\n")

    console.print("[bright_yellow]Coordinator analyzing task...[/bright_yellow]")
    context = TaskContext(original_request=task)
    coordinator = CoordinatorAgent()
    plan = await coordinator.plan(context)

    console.print(f"[bright_yellow]Task type:[/bright_yellow] {context.task_type.value}")
    console.print(f"[bright_yellow]Summary:[/bright_yellow] {plan.get('summary', 'N/A')}")
    console.print(f"[bright_yellow]Steps:[/bright_yellow] {len(plan.get('plan', []))}")

    async def on_start(step_num, total, agent_name, instruction):
        print_step_start(step_num, total, agent_name, instruction)

    async def on_output(step_num, agent_name, result):
        print_step_output(step_num, agent_name, result)

    engine = WorkflowEngine(on_step_start=on_start, on_step_output=on_output)
    await engine.run_plan(context, plan.get("plan", []))

    print_final_result(context)

    # Save output
    if output_file:
        path = save_result(context, output_file)
    else:
        path = save_result(context)
    console.print(f"\n[dim]Saved to:[/dim] {path}")

    # Auto commit
    if auto_commit:
        git = _get_git()
        git.init()
        short = task[:50].replace('"', "'")
        msg = git.checkpoint(f"{context.task_type.value}: {short}")
        console.print(f"[bright_cyan]Git:[/bright_cyan] {msg}")

    await client.close()


async def _pilot(tasks: list[str], config_path: str | None) -> None:
    """Autonomous pilot mode: run multiple tasks, auto-commit each."""
    load_settings(config_path)
    client = get_client()
    git = _get_git(auto_init=True)
    status = git.init()
    console.print(f"[bright_cyan]Git:[/bright_cyan] {status}")

    print_header("Agent Teams - Pilot Mode")
    console.print(f"[dim]Tasks queued: {len(tasks)}[/dim]\n")

    for i, task in enumerate(tasks):
        console.rule(f"[bold bright_yellow]Task {i+1}/{len(tasks)}[/bold bright_yellow]")
        console.print(f"[dim]{task}[/dim]\n")

        context = TaskContext(original_request=task)
        coordinator = CoordinatorAgent()
        plan = await coordinator.plan(context)

        console.print(f"[dim]Type: {context.task_type.value} | Steps: {len(plan.get('plan', []))}[/dim]")

        async def on_start(step_num, total, agent_name, instruction):
            print_step_start(step_num, total, agent_name, instruction)

        async def on_output(step_num, agent_name, result):
            print_step_output(step_num, agent_name, result)

        engine = WorkflowEngine(on_step_start=on_start, on_step_output=on_output)
        await engine.run_plan(context, plan.get("plan", []))

        print_final_result(context)
        path = save_result(context)
        console.print(f"[dim]Saved to: {path}[/dim]")

        # Auto commit after each task
        short = task[:50].replace('"', "'")
        msg = git.checkpoint(f"task {i+1}: {short}")
        console.print(f"[bright_cyan]Git:[/bright_cyan] {msg}\n")

    # Final summary push
    console.print(Panel(
        Text(f"Pilot complete: {len(tasks)} tasks", style="bold bright_green", justify="center"),
        style="bright_green",
    ))

    await client.close()


async def _interactive(config_path: str | None, auto_commit: bool = False) -> None:
    load_settings(config_path)
    client = get_client()

    git = None
    if auto_commit:
        git = _get_git()
        git.init()

    print_header("Agent Teams - Interactive")
    console.print("[dim]Enter task, 'q' to quit.[/dim]\n")

    task_count = 0
    while True:
        try:
            task = console.input("[bright_cyan]> [/bright_cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not task or task.lower() in ("quit", "exit", "q"):
            break

        task_count += 1
        context = TaskContext(original_request=task)
        coordinator = CoordinatorAgent()

        console.print("\n[bright_yellow]Planning...[/bright_yellow]")
        plan = await coordinator.plan(context)
        console.print(f"[dim]Type: {context.task_type.value} | Steps: {len(plan.get('plan', []))}[/dim]")

        async def on_start(step_num, total, agent_name, instruction):
            print_step_start(step_num, total, agent_name, instruction)

        async def on_output(step_num, agent_name, result):
            print_step_output(step_num, agent_name, result)

        engine = WorkflowEngine(on_step_start=on_start, on_step_output=on_output)
        await engine.run_plan(context, plan.get("plan", []))
        print_final_result(context)

        path = save_result(context)
        console.print(f"[dim]Saved to: {path}[/dim]")

        if git:
            short = task[:50].replace('"', "'")
            msg = git.checkpoint(f"chat #{task_count}: {short}")
            console.print(f"[bright_cyan]Git:[/bright_cyan] {msg}")
        console.print()

    console.print("\n[dim]Bye![/dim]")
    await client.close()


async def _list_models(config_path: str | None) -> None:
    load_settings(config_path)
    client = get_client()
    models = await client.list_models()
    if models:
        print_models(models)
    else:
        print_error("Could not fetch models. Is CLIProxyAPI running?")
    await client.close()


async def _gen_image(desc: str, output: str | None, config_path: str | None) -> None:
    load_settings(config_path)
    from agent_teams.agents.imagegen import ImageGenAgent
    client = get_client()
    print_header("Nano Banana")
    context = TaskContext(original_request=desc)
    agent = ImageGenAgent()
    console.print("[bright_red]Generating...[/bright_red]")
    result = await agent.execute(context, desc)
    print_step_output(1, "imagegen", result)
    print_final_result(context)
    await client.close()


# -- Imports for Panel/Text used in pilot --
from rich.panel import Panel
from rich.text import Text


# -- CLI --

class DefaultGroup(click.Group):
    """No subcommand? Treat args as a 'run' task."""

    def parse_args(self, ctx, args):
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            args = ["run"] + args
        return super().parse_args(ctx, args)


@click.group(cls=DefaultGroup, invoke_without_command=True)
@click.option("--config", "-c", default=None, hidden=True)
@click.pass_context
def main(ctx, config):
    """ai - Multi-model Agent Teams.\n
    \b
    ai 写一篇关于AI的博客          Run a task
    ai -g img 赛博朋克城市         Generate image
    ai chat                         Interactive mode
    ai chat --git                   Interactive + auto git
    ai pilot "task1" "task2"        Autonomous batch mode
    ai models                       List models"""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("task", nargs=-1, required=True)
@click.option("-o", default=None, help="Output filename")
@click.option("--git", is_flag=True, help="Auto commit+push to GitHub")
@click.pass_context
def run(ctx, task, o, git):
    """Run a task with the agent team."""
    asyncio.run(_run_task(" ".join(task), o, ctx.obj["config"], auto_commit=git))


@main.command()
@click.option("--git", is_flag=True, help="Auto commit+push after each task")
@click.pass_context
def chat(ctx, git):
    """Interactive chat mode."""
    asyncio.run(_interactive(ctx.obj["config"], auto_commit=git))


@main.command()
@click.argument("tasks", nargs=-1, required=True)
@click.pass_context
def pilot(ctx, tasks):
    """Autonomous batch: run tasks sequentially, auto commit+push each."""
    asyncio.run(_pilot(list(tasks), ctx.obj["config"]))


@main.command()
@click.pass_context
def models(ctx):
    """List available models."""
    asyncio.run(_list_models(ctx.obj["config"]))


@main.command()
@click.argument("description", nargs=-1, required=True)
@click.option("-o", default=None, help="Output filename")
@click.pass_context
def img(ctx, description, o):
    """Generate image via Nano Banana."""
    asyncio.run(_gen_image(" ".join(description), o, ctx.obj["config"]))


if __name__ == "__main__":
    main()
