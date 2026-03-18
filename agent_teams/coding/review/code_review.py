"""Multi-pass code review pipeline."""
from __future__ import annotations

import json
from agent_teams.agents.base import BaseAgent
from agent_teams.core.message import AgentResult, TaskContext


class CodeReviewPipeline:
    """3-pass code review: correctness → security → quality."""

    PASSES = [
        ("correctness", "Review for correctness: logic errors, edge cases, error handling, race conditions."),
        ("security", "Review for security: injection vulnerabilities, auth issues, secrets exposure, OWASP top 10."),
        ("quality", "Review for quality: readability, naming, SOLID principles, performance, test coverage."),
    ]

    def __init__(self, reviewer_agent: BaseAgent, coder_agent: BaseAgent,
                 max_iterations: int = 2, on_review=None, on_fix=None):
        self.reviewer = reviewer_agent
        self.coder = coder_agent
        self.max_iterations = max_iterations
        self.on_review = on_review
        self.on_fix = on_fix

    async def run(self, context: TaskContext, code_key: str) -> TaskContext:
        """Run all review passes on the code artifact."""
        for pass_name, focus in self.PASSES:
            for iteration in range(self.max_iterations):
                current_code = context.get_artifact(code_key, "")

                review_instruction = (
                    f"Code Review Pass: {pass_name} (iteration {iteration + 1})\n"
                    f"Focus: {focus}\n\n"
                    f"CODE TO REVIEW:\n{current_code}"
                )
                review_result = await self.reviewer.execute(context, review_instruction)

                if self.on_review:
                    await self.on_review(pass_name, iteration + 1, review_result)

                context.add_artifact(f"review_{pass_name}_{iteration + 1}", review_result.content)

                issues = self._parse_issues(review_result.content)
                critical = sum(1 for i in issues if i.get("severity") == "critical")
                major = sum(1 for i in issues if i.get("severity") == "major")

                if critical == 0 and major == 0:
                    break

                fix_instruction = (
                    f"Fix the following code review issues ({pass_name}):\n\n"
                    f"REVIEW FEEDBACK:\n{review_result.content}\n\n"
                    f"CURRENT CODE:\n{current_code}\n\n"
                    f"Output the complete fixed code."
                )
                fix_result = await self.coder.execute(context, fix_instruction)

                if self.on_fix:
                    await self.on_fix(pass_name, iteration + 1, fix_result)

                context.add_artifact(code_key, fix_result.content)

        return context

    def _parse_issues(self, review_text: str) -> list[dict]:
        try:
            text = review_text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            data = json.loads(text)
            return data.get("issues", [])
        except (json.JSONDecodeError, IndexError):
            return []
