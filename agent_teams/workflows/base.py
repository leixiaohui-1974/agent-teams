"""Base workflow engine."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agent_teams.agents.architect import ArchitectAgent
from agent_teams.agents.coder import CoderAgent
from agent_teams.agents.imagegen import ImageGenAgent
from agent_teams.agents.researcher import ResearcherAgent
from agent_teams.agents.reviewer import ReviewerAgent
from agent_teams.agents.writer import WriterAgent
from agent_teams.agents.base import BaseAgent
from agent_teams.core.message import AgentResult, TaskContext


AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "architect": ArchitectAgent,
    "writer": WriterAgent,
    "coder": CoderAgent,
    "reviewer": ReviewerAgent,
    "researcher": ResearcherAgent,
    "imagegen": ImageGenAgent,
}


@dataclass
class WorkflowStep:
    agent_name: str
    instruction_template: str
    output_key: str


class WorkflowEngine:
    """Executes a sequence of agent steps."""

    def __init__(self, on_step_start=None, on_step_output=None):
        self.on_step_start: Callable | None = on_step_start
        self.on_step_output: Callable | None = on_step_output
        self._agents: dict[str, BaseAgent] = {}

    def _get_agent(self, name: str) -> BaseAgent:
        if name not in self._agents:
            cls = AGENT_REGISTRY.get(name)
            if cls is None:
                raise ValueError(f"Unknown agent: {name}")
            self._agents[name] = cls()
        return self._agents[name]

    async def run_plan(self, context: TaskContext, plan: list[dict]) -> TaskContext:
        """Execute a plan from the Coordinator."""
        for i, step in enumerate(plan):
            agent_name = step["agent"]
            raw_instruction = step["instruction"]

            # Inject previous artifacts into instruction
            instruction = raw_instruction
            if context.artifacts:
                instruction = (
                    f"{raw_instruction}\n\n"
                    f"Previous work so far:\n{context.summary()}"
                )

            if self.on_step_start:
                await self.on_step_start(i + 1, len(plan), agent_name, raw_instruction)

            agent = self._get_agent(agent_name)
            result: AgentResult = await agent.execute(context, instruction)

            output_key = f"step_{i+1}_{agent_name}"
            context.add_artifact(output_key, result.content)

            if self.on_step_output:
                await self.on_step_output(i + 1, agent_name, result)

        return context

    async def run_steps(self, context: TaskContext, steps: list[WorkflowStep]) -> TaskContext:
        """Execute predefined workflow steps."""
        for i, step in enumerate(steps):
            instruction = step.instruction_template
            # Substitute artifact references
            for key, val in context.artifacts.items():
                placeholder = f"{{{key}}}"
                if placeholder in instruction:
                    instruction = instruction.replace(placeholder, str(val))

            if self.on_step_start:
                await self.on_step_start(i + 1, len(steps), step.agent_name, instruction[:100])

            agent = self._get_agent(step.agent_name)
            result = await agent.execute(context, instruction)
            context.add_artifact(step.output_key, result.content)

            if self.on_step_output:
                await self.on_step_output(i + 1, step.agent_name, result)

        return context
