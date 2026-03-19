"""Coding workflows for different development scenarios."""
from __future__ import annotations


# -- Workflow Templates --
# Each step: {"agent": name, "instruction": template with {placeholders}}

FULL_PROJECT_WORKFLOW = [
    {"stage": "discovery", "agent": "researcher", "instruction":
        "Research best practices, libraries, and architecture patterns for: {topic}\n"
        "Language/stack preference: {stack}. Identify the optimal approach."},
    {"stage": "design", "agent": "system_designer", "instruction":
        "Design the complete system architecture for: {topic}\n"
        "Stack: {stack}\nResearch:\n{step_1_researcher}\n"
        "Output: architecture, file structure, interfaces, tech decisions."},
    {"stage": "build", "agent": "senior_coder", "instruction":
        "Implement the complete project based on this design:\n{step_2_system_designer}\n\n"
        "Output ALL files with complete, runnable code. No placeholders.\n"
        "Format each file as: ```filepath:path/to/file.ext\\ncode```"},
    {"stage": "build", "agent": "devops_engineer", "instruction":
        "Create deployment and CI/CD configuration for:\n{step_2_system_designer}\n\n"
        "Include: Dockerfile, docker-compose.yml, GitHub Actions CI, Makefile, .env.example"},
    {"stage": "build", "agent": "doc_writer", "instruction":
        "Write project documentation:\n"
        "Design:\n{step_2_system_designer}\n\n"
        "Include: README.md (overview, quick start, architecture), API docs, CONTRIBUTING.md"},
    {"stage": "verification", "agent": "test_engineer", "instruction":
        "Write comprehensive tests for this implementation:\n{step_3_senior_coder}\n\n"
        "Design:\n{step_2_system_designer}\n\n"
        "Cover: unit tests, integration tests, edge cases. Aim for >80% coverage."},
]

FEATURE_WORKFLOW = [
    {"stage": "design", "agent": "system_designer", "instruction":
        "Design the feature: {topic}\n"
        "Existing codebase context: {context}\n"
        "Output: components needed, interfaces, data flow, affected files."},
    {"stage": "build", "agent": "senior_coder", "instruction":
        "Implement the feature based on this design:\n{step_1_system_designer}\n\n"
        "Output complete file contents for all new/modified files."},
    {"stage": "verification", "agent": "test_engineer", "instruction":
        "Write tests for this feature:\n{step_2_senior_coder}\n\n"
        "Design:\n{step_1_system_designer}"},
]

BUGFIX_WORKFLOW = [
    {"stage": "analysis", "agent": "researcher", "instruction":
        "Analyze this bug: {topic}\n"
        "Identify root cause, affected components, and potential fixes."},
    {"stage": "fix", "agent": "senior_coder", "instruction":
        "Fix the bug based on this analysis:\n{step_1_researcher}\n\n"
        "Output the complete fixed files. Explain each change."},
    {"stage": "verification", "agent": "test_engineer", "instruction":
        "Write regression tests for this bug fix:\n{step_2_senior_coder}\n\n"
        "Analysis:\n{step_1_researcher}\n\n"
        "Tests must: (1) reproduce the original bug, (2) verify the fix, (3) prevent regression."},
]

REFACTOR_WORKFLOW = [
    {"stage": "analysis", "agent": "code_reviewer", "instruction":
        "Analyze the code for refactoring opportunities: {topic}\n"
        "Identify: code smells, duplication, complexity, SOLID violations."},
    {"stage": "design", "agent": "system_designer", "instruction":
        "Design the refactoring plan based on this review:\n{step_1_code_reviewer}\n\n"
        "Prioritize changes. Ensure backward compatibility."},
    {"stage": "build", "agent": "senior_coder", "instruction":
        "Execute the refactoring plan:\n{step_2_system_designer}\n\n"
        "Output complete refactored files. Maintain all existing functionality."},
    {"stage": "verification", "agent": "test_engineer", "instruction":
        "Verify refactoring didn't break anything. Write/update tests:\n{step_3_senior_coder}\n\n"
        "Original review:\n{step_1_code_reviewer}"},
]

API_WORKFLOW = [
    {"stage": "design", "agent": "system_designer", "instruction":
        "Design the API: {topic}\n"
        "Include: endpoints, request/response schemas, auth, error codes, rate limiting."},
    {"stage": "build", "agent": "senior_coder", "instruction":
        "Implement the API based on this design:\n{step_1_system_designer}\n\n"
        "Include: routes, handlers, middleware, models, validation, error handling."},
    {"stage": "verification", "agent": "test_engineer", "instruction":
        "Write API tests:\n{step_2_senior_coder}\n\n"
        "Cover: happy paths, validation errors, auth, edge cases, load hints."},
    {"stage": "verification", "agent": "doc_writer", "instruction":
        "Write API documentation:\n{step_1_system_designer}\n\n"
        "Implementation:\n{step_2_senior_coder}\n\n"
        "Include: endpoint reference, examples with curl/httpie, error codes table."},
]

CODING_WORKFLOWS = {
    "project": FULL_PROJECT_WORKFLOW,
    "feature": FEATURE_WORKFLOW,
    "bugfix": BUGFIX_WORKFLOW,
    "refactor": REFACTOR_WORKFLOW,
    "api": API_WORKFLOW,
}
