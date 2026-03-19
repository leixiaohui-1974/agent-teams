"""Base agent class."""
from __future__ import annotations

from abc import ABC
from typing import AsyncIterator

import httpx

from agent_teams.config import get_settings
from agent_teams.core.client import get_client
from agent_teams.core.message import AgentAction, AgentResult, TaskContext
from agent_teams.core.streaming import collect_stream
from agent_teams.routing.strategy import get_temperature_for_role, pick_model_for_role


class BaseAgent(ABC):
    """Abstract base for all agents."""

    name: str = "base"
    role_description: str = "A helpful AI assistant."

    @property
    def system_prompt(self) -> str:
        return self.role_description

    async def get_model(self) -> str:
        return await pick_model_for_role(self.name)

    async def get_fallback_models(self) -> list[str]:
        """Get all configured model preferences for this agent role."""
        settings = get_settings()
        agent_cfg = settings.agents.get(self.name)
        return agent_cfg.models if agent_cfg else []

    def get_temperature(self) -> float:
        return get_temperature_for_role(self.name)

    def build_messages(self, context: TaskContext, instruction: str) -> list[dict[str, str]]:
        """Build message array for the LLM call."""
        messages = [{"role": "system", "content": self.system_prompt}]

        # Add context summary if there are artifacts
        if context.artifacts:
            messages.append({
                "role": "user",
                "content": f"Here is the current work context:\n\n{context.summary()}",
            })
            messages.append({
                "role": "assistant",
                "content": "Understood. I have reviewed the current work context. Please provide your instruction.",
            })

        messages.append({"role": "user", "content": instruction})
        return messages

    async def execute(self, context: TaskContext, instruction: str) -> AgentResult:
        """Execute this agent with automatic model fallback on rate limits."""
        models = await self.get_fallback_models()
        primary = await self.get_model()
        # Ensure primary is first, then add remaining models
        all_models = [primary] + [m for m in models if m != primary]
        # Add universal fallbacks
        for fb in ["gemini-2.5-flash", "claude-sonnet-4-20250514", "gemini-2.5-pro"]:
            if fb not in all_models:
                all_models.append(fb)

        messages = self.build_messages(context, instruction)
        client = get_client()
        last_error = None

        for model in all_models:
            try:
                resp = await client.chat(
                    messages=messages,
                    model=model,
                    temperature=self.get_temperature(),
                )
                content = resp["choices"][0]["message"]["content"]
                route_used = resp.get("_route", "")

                context.agent_log.append(AgentAction(
                    agent_name=self.name,
                    action="execute",
                    model=model,
                    input_summary=instruction[:200],
                    output_summary=content[:200],
                ))
                return AgentResult(
                    agent_name=self.name,
                    content=content,
                    model_used=model,
                    metadata={"route": route_used} if route_used else {},
                )

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (429, 500, 502, 503):
                    continue  # try next model
                raise
            except Exception as e:
                last_error = e
                continue

        raise last_error  # all models exhausted

    async def stream_execute(self, context: TaskContext, instruction: str) -> AsyncIterator[str]:
        """Execute with streaming output."""
        model = await self.get_model()
        messages = self.build_messages(context, instruction)
        client = get_client()

        full_content_parts: list[str] = []
        async for chunk in client.chat_stream(
            messages=messages,
            model=model,
            temperature=self.get_temperature(),
        ):
            full_content_parts.append(chunk)
            yield chunk

        full_content = "".join(full_content_parts)
        context.agent_log.append(AgentAction(
            agent_name=self.name,
            action="stream_execute",
            model=model,
            input_summary=instruction[:200],
            output_summary=full_content[:200],
        ))

    async def execute_streaming(self, context: TaskContext, instruction: str) -> AgentResult:
        """Execute with streaming, but collect and return full result."""
        model = await self.get_model()
        messages = self.build_messages(context, instruction)
        client = get_client()

        content = await collect_stream(
            client.chat_stream(messages=messages, model=model, temperature=self.get_temperature())
        )

        context.agent_log.append(AgentAction(
            agent_name=self.name,
            action="execute_streaming",
            model=model,
            input_summary=instruction[:200],
            output_summary=content[:200],
        ))

        return AgentResult(agent_name=self.name, content=content, model_used=model)
