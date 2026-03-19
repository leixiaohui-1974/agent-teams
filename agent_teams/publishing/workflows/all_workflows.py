"""Publishing workflows for all document types."""
from __future__ import annotations

from agent_teams.publishing.models import DocType


# Each workflow is a list of steps: {"agent": name, "instruction": template}
# The PublishingCoordinator picks the right workflow based on DocType.

ARTICLE_WORKFLOW = [
    {"stage": "research", "agent": "researcher", "instruction":
        "Research the topic: {topic}. Gather key points, recent developments, "
        "data, expert opinions. Output organized research notes."},
    {"stage": "outline", "agent": "outline_architect", "instruction":
        "Create a detailed article outline for: {topic}\n"
        "Target audience: {audience}. Language: {language}.\n"
        "Based on research:\n{step_1_researcher}"},
    {"stage": "draft", "agent": "content_writer", "instruction":
        "Write the complete article following this outline:\n{step_2_outline_architect}\n\n"
        "Research notes:\n{step_1_researcher}\n\n"
        "Rules: Use proper heading hierarchy. Mark figures as ![caption](fig:id). "
        "Mark equations as $$LaTeX$$. Include [@references] where appropriate."},
    {"stage": "assets", "agent": "figure_generator", "instruction":
        "Based on the article, generate illustration descriptions for any figures mentioned:\n"
        "{step_3_content_writer}\n\nOutput a detailed image prompt for each figure."},
    # Review pipeline is injected automatically
]

WECHAT_WORKFLOW = [
    {"stage": "research", "agent": "researcher", "instruction":
        "Research trending angles for 公众号 article on: {topic}. "
        "Find compelling data points, relatable examples, recent hot topics related to this."},
    {"stage": "outline", "agent": "outline_architect", "instruction":
        "Create a 公众号 article outline for: {topic}\n"
        "Structure: hook opening → 3-4 body sections → CTA closing\n"
        "Target 2000-4000 Chinese characters.\nResearch:\n{step_1_researcher}"},
    {"stage": "draft", "agent": "wechat_writer", "instruction":
        "Write the complete 公众号 article following this outline:\n{step_2_outline_architect}\n\n"
        "Research:\n{step_1_researcher}\n\n"
        "Remember 公众号 conventions: bold hook opening, short paragraphs, "
        "bold key phrases, engaging tone, CTA closing. Write entirely in Chinese."},
    {"stage": "assets", "agent": "figure_generator", "instruction":
        "Design a cover image and 2-3 inline illustrations for this 公众号 article:\n"
        "{step_3_wechat_writer}\n\nOutput detailed image prompts."},
]

PAPER_WORKFLOW = [
    {"stage": "research", "agent": "researcher", "instruction":
        "Conduct a literature review on: {topic}. Identify key papers, methodologies, "
        "research gaps, and positioning for a new contribution."},
    {"stage": "outline", "agent": "outline_architect", "instruction":
        "Design an academic paper structure for: {topic}\n"
        "Sections: Abstract, Introduction, Related Work, Method, Experiments, "
        "Results, Discussion, Conclusion.\n"
        "Include figure/table/equation placeholders.\nLiterature:\n{step_1_researcher}"},
    {"stage": "draft", "agent": "academic_writer", "instruction":
        "Write the complete academic paper following this structure:\n{step_2_outline_architect}\n\n"
        "Literature review:\n{step_1_researcher}\n\n"
        "Use LaTeX math notation: $$formula$$. Use [@cite_key] for citations. "
        "Include proper theorem/proof environments if needed."},
    {"stage": "polish", "agent": "academic_writer", "instruction":
        "Review and add: (1) all missing LaTeX formulas, (2) proper table formatting, "
        "(3) algorithm pseudocode, (4) complete bibliography entries.\n"
        "Current paper:\n{step_3_academic_writer}"},
]

BOOK_CHAPTER_WORKFLOW = [
    {"stage": "research", "agent": "researcher", "instruction":
        "Research for book chapter on: {topic}\nBook context: {book_context}\n"
        "Gather comprehensive material for this chapter."},
    {"stage": "outline", "agent": "outline_architect", "instruction":
        "Create a detailed chapter outline for: {topic}\n"
        "Book context: {book_context}\nChapter position in book: {chapter_number}\n"
        "Research:\n{step_1_researcher}"},
    {"stage": "draft", "agent": "content_writer", "instruction":
        "Write the complete chapter following this outline:\n{step_2_outline_architect}\n\n"
        "Research:\n{step_1_researcher}\n\n"
        "Maintain consistent tone with the book. Include figures, tables, equations as needed."},
]

TECH_DOC_WORKFLOW = [
    {"stage": "research", "agent": "researcher", "instruction":
        "Analyze the technical subject: {topic}. Identify key concepts, APIs, "
        "configurations, common use cases, and potential pitfalls."},
    {"stage": "outline", "agent": "outline_architect", "instruction":
        "Design technical documentation structure for: {topic}\n"
        "Include: Overview, Getting Started, Core Concepts, API Reference, "
        "Examples, Troubleshooting.\nResearch:\n{step_1_researcher}"},
    {"stage": "draft", "agent": "tech_doc_writer", "instruction":
        "Write the complete technical documentation:\n{step_2_outline_architect}\n\n"
        "Research:\n{step_1_researcher}\n\n"
        "Include runnable code examples, command-line snippets, and parameter tables."},
    {"stage": "verification", "agent": "coder", "instruction":
        "Validate and improve all code examples in the documentation. "
        "Ensure they are complete, runnable, and follow best practices:\n"
        "{step_3_tech_doc_writer}"},
]

REPORT_WORKFLOW = [
    {"stage": "research", "agent": "researcher", "instruction":
        "Gather data and analysis for report on: {topic}. "
        "Include statistics, trends, comparisons, and key findings."},
    {"stage": "outline", "agent": "outline_architect", "instruction":
        "Design report structure: Executive Summary, Background, Findings, "
        "Analysis, Recommendations, Appendix.\n"
        "Data:\n{step_1_researcher}"},
    {"stage": "draft", "agent": "content_writer", "instruction":
        "Write the complete report:\n{step_2_outline_architect}\n\n"
        "Data:\n{step_1_researcher}\n\n"
        "Include tables for data, charts descriptions, and actionable recommendations."},
]

WORKFLOWS = {
    DocType.ARTICLE: ARTICLE_WORKFLOW,
    DocType.WECHAT: WECHAT_WORKFLOW,
    DocType.PAPER: PAPER_WORKFLOW,
    DocType.BOOK: BOOK_CHAPTER_WORKFLOW,
    DocType.TECH_DOC: TECH_DOC_WORKFLOW,
    DocType.REPORT: REPORT_WORKFLOW,
}
