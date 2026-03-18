"""Coordinator agent - task decomposition and workflow routing."""
from __future__ import annotations

import json

from agent_teams.agents.base import BaseAgent
from agent_teams.core.message import AgentResult, TaskContext, TaskType


COORDINATOR_PROMPT = """You are the Coordinator of an AI agent team. Your job is to:
1. Analyze the user's request
2. Classify the task type
3. Create a step-by-step plan for the team

You have these team members:
- **Researcher** (Gemini): Great at gathering info, research, summarization
- **Architect** (Claude): System design, planning, structure, outlines
- **Writer** (GPT): Creative writing, articles, reports, polishing prose
- **Coder** (Claude): Code generation, implementation, debugging
- **Reviewer** (Gemini): Code review, writing review, quality analysis
- **ImageGen** (Nano Banana/Gemini): High-quality image generation

Respond ONLY with valid JSON in this exact format:
{
    "task_type": "writing|coding|general|image",
    "plan": [
        {"agent": "researcher|architect|writer|coder|reviewer|imagegen", "instruction": "what to do"},
        ...
    ],
    "summary": "brief description of the task"
}

Guidelines:
- For writing tasks: researcher -> architect (outline) -> writer (draft) -> reviewer -> writer (polish)
- For coding tasks: architect (design) -> coder (implement) -> reviewer -> coder (fix)
- For image tasks: include imagegen step with detailed description
- For general: use minimal agents needed
- Keep instructions specific and actionable
"""


class CoordinatorAgent(BaseAgent):
    name = "coordinator"
    role_description = COORDINATOR_PROMPT

    async def plan(self, context: TaskContext) -> dict:
        """Analyze the request and create an execution plan."""
        result = await self.execute(context, context.original_request)
        try:
            # Extract JSON from the response
            text = result.content.strip()
            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            plan = json.loads(text)
        except (json.JSONDecodeError, IndexError):
            # Fallback: simple single-agent plan
            plan = {
                "task_type": "general",
                "plan": [{"agent": "writer", "instruction": context.original_request}],
                "summary": context.original_request[:100],
            }

        # Set task type on context
        task_type_str = plan.get("task_type", "general")
        try:
            context.task_type = TaskType(task_type_str)
        except ValueError:
            context.task_type = TaskType.GENERAL

        context.add_artifact("plan", plan)
        return plan
