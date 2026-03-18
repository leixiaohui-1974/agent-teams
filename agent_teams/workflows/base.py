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

# Publishing specialists
from agent_teams.publishing.agents.specialists import (
    OutlineArchitectAgent, ContentWriterAgent, AcademicWriterAgent,
    WeChatWriterAgent, TechDocWriterAgent,
)
from agent_teams.publishing.review.reviewers import (
    ContentReviewerAgent, StructureReviewerAgent, LanguageReviewerAgent,
    ReferenceVerifierAgent,
)

# Coding specialists
from agent_teams.coding.agents.specialists import (
    SystemDesignerAgent, SeniorCoderAgent, TestEngineerAgent,
    CodeReviewerAgent, DevOpsEngineerAgent, DocWriterAgent,
)


AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    # General
    "architect": ArchitectAgent,
    "writer": WriterAgent,
    "coder": CoderAgent,
    "reviewer": ReviewerAgent,
    "researcher": ResearcherAgent,
    "imagegen": ImageGenAgent,
    # Publishing
    "outline_architect": OutlineArchitectAgent,
    "content_writer": ContentWriterAgent,
    "academic_writer": AcademicWriterAgent,
    "wechat_writer": WeChatWriterAgent,
    "tech_doc_writer": TechDocWriterAgent,
    "reference_verifier": ReferenceVerifierAgent,
    "content_reviewer": ContentReviewerAgent,
    "structure_reviewer": StructureReviewerAgent,
    "language_reviewer": LanguageReviewerAgent,
    "figure_generator": ImageGenAgent,
    # Coding
    "system_designer": SystemDesignerAgent,
    "senior_coder": SeniorCoderAgent,
    "test_engineer": TestEngineerAgent,
    "code_reviewer": CodeReviewerAgent,
    "devops_engineer": DevOpsEngineerAgent,
    "doc_writer": DocWriterAgent,
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

            # Substitute {step_N_agentname} placeholders with actual artifact content
            instruction = raw_instruction
            for key, val in context.artifacts.items():
                placeholder = f"{{{key}}}"
                if placeholder in instruction:
                    instruction = instruction.replace(placeholder, str(val))

            # If any unresolved placeholders remain, inject full context summary
            if context.artifacts and "{step_" in instruction:
                instruction += f"\n\nPrevious work context:\n{context.summary()}"

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
