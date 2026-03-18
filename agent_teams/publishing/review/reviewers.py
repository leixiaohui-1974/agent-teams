"""Multi-round review pipeline with specialized reviewers."""
from __future__ import annotations

import json
from agent_teams.agents.base import BaseAgent
from agent_teams.core.client import get_client
from agent_teams.core.message import AgentAction, AgentResult, TaskContext


class ContentReviewerAgent(BaseAgent):
    """Pass 1: Factual accuracy, completeness, citation validity."""
    name = "content_reviewer"
    role_description = """You are a rigorous content reviewer. Review the document for:

1. **Factual accuracy**: Are all claims correct? Any factual errors?
2. **Completeness**: Are there gaps in coverage? Missing key points?
3. **Citation validity**: Are all [@references] properly used? Any unsupported claims?
4. **Technical correctness**: Are formulas, code, data accurate?
5. **Logical consistency**: Do arguments follow logically? Any contradictions?

Output your review as JSON:
```json
{
  "approved": false,
  "issues": [
    {"severity": "critical|major|minor", "location": "section title or ID", "issue": "description", "suggestion": "fix"}
  ],
  "summary": "overall assessment"
}
```
Be thorough but fair. Note what's done well alongside problems."""


class StructureReviewerAgent(BaseAgent):
    """Pass 2: Structure, flow, section balance."""
    name = "structure_reviewer"
    role_description = """You are an editorial structure reviewer. Review the document for:

1. **Section balance**: Are sections proportional in depth? Any too long/short?
2. **Logical progression**: Does the narrative flow naturally?
3. **Transitions**: Are section transitions smooth? Any jarring jumps?
4. **Heading hierarchy**: Are headings properly nested and descriptive?
5. **Introduction-conclusion alignment**: Does the conclusion address the intro's promises?
6. **Figure/table placement**: Are they near their first reference?
7. **Reader journey**: Will the target audience follow this path?

Output your review as JSON:
```json
{
  "approved": false,
  "issues": [
    {"severity": "critical|major|minor", "location": "section title or ID", "issue": "description", "suggestion": "fix"}
  ],
  "summary": "overall assessment"
}
```"""


class LanguageReviewerAgent(BaseAgent):
    """Pass 3: Language polish, style, readability."""
    name = "language_reviewer"
    role_description = """You are a professional language editor. Review the document for:

1. **Clarity**: Is every sentence easy to understand?
2. **Conciseness**: Remove redundancy, tighten prose
3. **Tone consistency**: Is the tone appropriate and consistent throughout?
4. **Grammar & punctuation**: Any errors? (Consider the document's language)
5. **Readability**: Sentence variety, paragraph length, jargon level
6. **Word choice**: Are terms precise? Any clichés or vague language?
7. **Style**: Does it match the document type (academic, casual, professional)?

Output your review as JSON:
```json
{
  "approved": false,
  "issues": [
    {"severity": "critical|major|minor", "location": "section title or ID", "issue": "description", "suggestion": "fix"}
  ],
  "summary": "overall assessment"
}
```"""


class ReviewPipeline:
    """Orchestrates 3-pass review with revision loops."""

    PASSES = [
        ("content_accuracy", ContentReviewerAgent),
        ("structure_flow", StructureReviewerAgent),
        ("language_polish", LanguageReviewerAgent),
    ]

    def __init__(self, max_iterations: int = 2, on_review=None, on_revision=None):
        self.max_iterations = max_iterations
        self.on_review = on_review
        self.on_revision = on_revision

    async def run(
        self,
        context: TaskContext,
        content_key: str,
        writer_agent: BaseAgent,
    ) -> TaskContext:
        """Run all review passes on the artifact at content_key."""
        for pass_idx, (pass_name, reviewer_cls) in enumerate(self.PASSES):
            reviewer = reviewer_cls()

            for iteration in range(self.max_iterations):
                current_content = context.get_artifact(content_key, "")

                # Review
                review_instruction = (
                    f"Review the following document (Pass: {pass_name}, "
                    f"iteration {iteration + 1}):\n\n{current_content}"
                )
                review_result = await reviewer.execute(context, review_instruction)

                if self.on_review:
                    await self.on_review(pass_name, iteration + 1, review_result)

                # Parse review
                issues = self._parse_review(review_result.content)
                critical_count = sum(1 for i in issues if i.get("severity") == "critical")
                major_count = sum(1 for i in issues if i.get("severity") == "major")

                # Store review
                context.add_artifact(
                    f"review_{pass_name}_{iteration + 1}",
                    review_result.content,
                )

                # If no critical/major issues, pass is done
                if critical_count == 0 and major_count == 0:
                    break

                # Revise
                revision_instruction = (
                    f"Revise the document based on this {pass_name} review feedback:\n\n"
                    f"REVIEW FEEDBACK:\n{review_result.content}\n\n"
                    f"CURRENT DOCUMENT:\n{current_content}\n\n"
                    f"Address all critical and major issues. Output the complete revised document."
                )
                revision_result = await writer_agent.execute(context, revision_instruction)

                if self.on_revision:
                    await self.on_revision(pass_name, iteration + 1, revision_result)

                context.add_artifact(content_key, revision_result.content)

        return context

    def _parse_review(self, review_text: str) -> list[dict]:
        """Extract issues from review JSON."""
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
