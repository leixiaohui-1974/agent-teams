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

    succeeded, failed = 0, 0
    for i, task in enumerate(tasks):
        console.rule(f"[bold bright_yellow]Task {i+1}/{len(tasks)}[/bold bright_yellow]")
        console.print(f"[dim]{task}[/dim]\n")

        try:
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

            short = task[:50].replace('"', "'")
            msg = git.checkpoint(f"task {i+1}: {short}")
            console.print(f"[bright_cyan]Git:[/bright_cyan] {msg}\n")
            succeeded += 1

        except Exception as e:
            console.print(f"[bold red]Task {i+1} failed: {e}[/bold red]\n")
            failed += 1
            continue  # keep going with next task

    console.print(Panel(
        Text(f"Pilot complete: {succeeded} succeeded, {failed} failed / {len(tasks)} total",
             style="bold bright_green", justify="center"),
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


# -- Publishing runner --

async def _write_doc(
    doc_type: str, topic: str, formats: list[str],
    lang: str, config_path: str | None, auto_commit: bool = False,
) -> None:
    load_settings(config_path)
    client = get_client()

    from agent_teams.publishing.models import DocType, OutputFormat
    from agent_teams.publishing.workflows.all_workflows import WORKFLOWS
    from agent_teams.publishing.review.reviewers import ReviewPipeline
    from agent_teams.publishing.formats.converter import FormatConverter

    dtype = DocType(doc_type)
    print_header(f"Publishing: {dtype.value}")
    console.print(f"[dim]Topic:[/dim] {topic}")
    console.print(f"[dim]Formats:[/dim] {', '.join(formats) or 'md'}\n")

    workflow_steps = WORKFLOWS.get(dtype, WORKFLOWS[DocType.ARTICLE])
    context = TaskContext(original_request=topic)

    # Fill template variables
    filled_steps = []
    for step in workflow_steps:
        inst = step["instruction"]
        inst = inst.replace("{topic}", topic)
        inst = inst.replace("{language}", lang)
        inst = inst.replace("{audience}", "general")
        inst = inst.replace("{stack}", "")
        inst = inst.replace("{context}", "")
        inst = inst.replace("{book_context}", topic)
        inst = inst.replace("{chapter_number}", "1")
        filled_steps.append({"agent": step["agent"], "instruction": inst})

    # Run workflow
    async def on_start(step_num, total, agent_name, instruction):
        print_step_start(step_num, total, agent_name, instruction)

    async def on_output(step_num, agent_name, result):
        print_step_output(step_num, agent_name, result)

    engine = WorkflowEngine(on_step_start=on_start, on_step_output=on_output)
    await engine.run_plan(context, filled_steps)

    # Multi-round review
    console.print()
    console.rule("[bright_magenta]Review Pipeline (4 passes)[/bright_magenta]")

    # Find the main content artifact
    content_key = None
    for key in reversed(list(context.artifacts.keys())):
        if any(w in key for w in ["writer", "content", "wechat", "academic", "tech_doc"]):
            content_key = key
            break
    if not content_key:
        content_key = list(context.artifacts.keys())[-1]

    # Pick the appropriate writer for revisions
    writer_map = {
        DocType.WECHAT: "wechat_writer",
        DocType.PAPER: "academic_writer",
        DocType.TECH_DOC: "tech_doc_writer",
    }
    writer_name = writer_map.get(dtype, "content_writer")
    writer_agent = engine._get_agent(writer_name)

    async def on_review(pass_name, iteration, result):
        console.print(f"\n[bright_magenta]Review: {pass_name} (iter {iteration})[/bright_magenta]")
        print_step_output(0, result.agent_name, result)

    async def on_revision(pass_name, iteration, result):
        console.print(f"[bright_green]Revision: {pass_name} (iter {iteration})[/bright_green]")

    pipeline = ReviewPipeline(max_iterations=2, on_review=on_review, on_revision=on_revision)
    await pipeline.run(context, content_key, writer_agent)

    print_final_result(context)

    # Post-processing: auto-numbering + reference resolution
    from agent_teams.publishing.content.rich_content import ContentPostProcessor
    from agent_teams.publishing.models import DocumentSpec

    console.print("\n[dim]Post-processing: numbering, references...[/dim]")
    processor = ContentPostProcessor(lang=lang)
    final_content = str(context.get_artifact(content_key, ""))
    final_content = processor.process(final_content)
    context.add_artifact(content_key, final_content)

    # Format conversion
    doc = DocumentSpec(doc_type=dtype, title=topic, language=lang)
    converter = FormatConverter()
    output_dir = Path.cwd() / "output"
    target_formats = [OutputFormat(f) for f in formats] if formats else [OutputFormat.MARKDOWN]

    for fmt in target_formats:
        path = converter.convert(final_content, doc, fmt, output_dir)
        console.print(f"[bright_green]Output:[/bright_green] {path}")

    if auto_commit:
        git = _get_git()
        git.init()
        msg = git.checkpoint(f"write {doc_type}: {topic[:40]}")
        console.print(f"[bright_cyan]Git:[/bright_cyan] {msg}")

    await client.close()


# -- Coding runner --

async def _code_task(
    workflow_type: str, topic: str, stack: str,
    config_path: str | None, auto_commit: bool = False,
) -> None:
    load_settings(config_path)
    client = get_client()

    from agent_teams.coding.workflows.all_workflows import CODING_WORKFLOWS
    from agent_teams.coding.review.code_review import CodeReviewPipeline

    print_header(f"Coding: {workflow_type}")
    console.print(f"[dim]Task:[/dim] {topic}")
    console.print(f"[dim]Stack:[/dim] {stack or 'auto'}\n")

    workflow_steps = CODING_WORKFLOWS.get(workflow_type, CODING_WORKFLOWS["project"])
    context = TaskContext(original_request=topic)

    # Fill template variables
    filled_steps = []
    for step in workflow_steps:
        inst = step["instruction"]
        inst = inst.replace("{topic}", topic)
        inst = inst.replace("{stack}", stack or "best practices for the task")
        inst = inst.replace("{context}", "")
        filled_steps.append({"agent": step["agent"], "instruction": inst})

    async def on_start(step_num, total, agent_name, instruction):
        print_step_start(step_num, total, agent_name, instruction)

    async def on_output(step_num, agent_name, result):
        print_step_output(step_num, agent_name, result)

    engine = WorkflowEngine(on_step_start=on_start, on_step_output=on_output)
    await engine.run_plan(context, filled_steps)

    # Code review pipeline
    console.print()
    console.rule("[bright_magenta]Code Review Pipeline (4 passes)[/bright_magenta]")

    code_key = None
    for key in reversed(list(context.artifacts.keys())):
        if any(w in key for w in ["coder", "senior"]):
            code_key = key
            break
    if not code_key:
        code_key = list(context.artifacts.keys())[-1]

    reviewer = engine._get_agent("code_reviewer")
    coder = engine._get_agent("senior_coder")

    async def on_review(pass_name, iteration, result):
        console.print(f"\n[bright_magenta]Review: {pass_name} (iter {iteration})[/bright_magenta]")
        print_step_output(0, result.agent_name, result)

    async def on_fix(pass_name, iteration, result):
        console.print(f"[bright_green]Fix: {pass_name} (iter {iteration})[/bright_green]")

    review_pipeline = CodeReviewPipeline(
        reviewer, coder, max_iterations=2, on_review=on_review, on_fix=on_fix,
    )
    await review_pipeline.run(context, code_key)

    print_final_result(context)
    path = save_result(context)
    console.print(f"\n[dim]Saved to:[/dim] {path}")

    if auto_commit:
        git = _get_git()
        git.init()
        msg = git.checkpoint(f"code {workflow_type}: {topic[:40]}")
        console.print(f"[bright_cyan]Git:[/bright_cyan] {msg}")

    await client.close()


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
    ai 任务描述                         Quick task
    ai write article 量子计算入门       Publication-grade writing
    ai write wechat AI改变教育          WeChat article
    ai write paper Transformer综述      Academic paper
    ai code project 用Go写HTTP框架      Full project
    ai code api 用户认证REST API        API development
    ai code bugfix 修复内存泄漏         Bug fixing
    ai img 赛博朋克城市                 Image generation
    ai chat --git                       Interactive + auto git
    ai pilot "task1" "task2"            Autonomous batch"""
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


@main.command()
@click.argument("doc_type", type=click.Choice(["article", "wechat", "paper", "book", "tech_doc", "report"]))
@click.argument("topic", nargs=-1, required=True)
@click.option("-f", "--fmt", multiple=True, type=click.Choice(["md", "latex", "html", "pdf"]),
              help="Output formats (repeatable)")
@click.option("--lang", default="zh-CN", help="Language (default: zh-CN)")
@click.option("--git", is_flag=True, help="Auto commit+push")
@click.pass_context
def write(ctx, doc_type, topic, fmt, lang, git):
    """Publication-grade writing with 3-pass review.

    \b
    ai write article 量子计算入门 -f md -f pdf
    ai write wechat AI如何改变教育 -f html
    ai write paper Transformer架构综述 -f latex -f pdf
    ai write book Python深度学习 -f md
    ai write report Q1销售分析 -f pdf"""
    asyncio.run(_write_doc(doc_type, " ".join(topic), list(fmt), lang, ctx.obj["config"], git))


@main.command()
@click.argument("workflow", type=click.Choice(["project", "feature", "bugfix", "refactor", "api"]))
@click.argument("topic", nargs=-1, required=True)
@click.option("--stack", default="", help="Tech stack (e.g. 'Python FastAPI PostgreSQL')")
@click.option("--git", is_flag=True, help="Auto commit+push")
@click.pass_context
def code(ctx, workflow, topic, stack, git):
    """Professional coding with 3-pass code review.

    \b
    ai code project 用Go写一个HTTP框架 --stack "Go chi PostgreSQL"
    ai code api 用户认证系统 --stack "Python FastAPI"
    ai code feature 添加WebSocket支持
    ai code bugfix 修复数据库连接池泄漏
    ai code refactor 重构用户模块"""
    asyncio.run(_code_task(workflow, " ".join(topic), stack, ctx.obj["config"], git))


if __name__ == "__main__":
    main()
