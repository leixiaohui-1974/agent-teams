"""Data models for messages, contexts, and agent results."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TaskType(str, Enum):
    WRITING = "writing"
    CODING = "coding"
    GENERAL = "general"
    IMAGE = "image"


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    role: Role
    content: str
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    agent_name: str
    content: str
    model_used: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AgentAction:
    agent_name: str
    action: str
    model: str
    input_summary: str
    output_summary: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TaskContext:
    """Shared blackboard for agent communication."""
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    original_request: str = ""
    task_type: TaskType = TaskType.GENERAL
    artifacts: dict[str, Any] = field(default_factory=dict)
    conversation: list[Message] = field(default_factory=list)
    agent_log: list[AgentAction] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    image_paths: list[str] = field(default_factory=list)

    def add_artifact(self, key: str, value: Any) -> None:
        self.artifacts[key] = value

    def get_artifact(self, key: str, default: Any = None) -> Any:
        return self.artifacts.get(key, default)

    def summary(self) -> str:
        """Get a compact summary of current artifacts for context injection."""
        parts = []
        for key, val in self.artifacts.items():
            text = str(val)
            if len(text) > 500:
                text = text[:500] + "..."
            parts.append(f"[{key}]:\n{text}")
        return "\n\n".join(parts)
