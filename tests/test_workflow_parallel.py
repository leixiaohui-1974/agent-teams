from __future__ import annotations

import asyncio
import time

from agent_teams.agents.base import BaseAgent
from agent_teams.core.message import AgentResult, TaskContext
from agent_teams.workflows import base as workflow_base


class DummyAgent(BaseAgent):
    name = "dummy"

    async def execute(self, context: TaskContext, instruction: str) -> AgentResult:
        await asyncio.sleep(0.2)
        return AgentResult(agent_name=self.name, content=instruction, model_used="dummy-model")


async def _run_parallel_plan() -> tuple[TaskContext, float]:
    original = workflow_base.AGENT_REGISTRY.get("dummy")
    workflow_base.AGENT_REGISTRY["dummy"] = DummyAgent
    try:
        engine = workflow_base.WorkflowEngine()
        context = TaskContext(original_request="parallel test")
        plan = [
            {"stage": "shared", "agent": "dummy", "instruction": "first"},
            {"stage": "shared", "agent": "dummy", "instruction": "second"},
        ]
        started = time.perf_counter()
        await engine.run_plan(context, plan)
        elapsed = time.perf_counter() - started
        return context, elapsed
    finally:
        if original is None:
            workflow_base.AGENT_REGISTRY.pop("dummy", None)
        else:
            workflow_base.AGENT_REGISTRY["dummy"] = original


def test_same_stage_steps_run_in_parallel():
    context, elapsed = asyncio.run(_run_parallel_plan())

    assert "step_1_dummy" in context.artifacts
    assert "step_2_dummy" in context.artifacts
    assert elapsed < 0.35
